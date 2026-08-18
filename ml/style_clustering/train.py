#!/usr/bin/env python3
"""
Style-archetype clustering: fits a separate K-means per broad position
group over composite.py's style-category percentiles, K chosen by
silhouette. IMPORTANT: unsupervised, no labeled ground truth - report face-validity spot checks, don't present labels as empirically validated.
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data import loader
from data.loader import load_all_leagues_data, load_meta
from backend.scoring.composite import get_playing_style_categories
from backend import config
from ml.style_clustering.features import (
    POSITION_GROUPS, build_position_group_matrix, center_on_own_mean, cluster_feature_columns,
    dampen_negative, l2_normalize,
)
from ml.style_clustering.label import label_clusters

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'artifacts')
ARTIFACTS_DIR = os.path.normpath(ARTIFACTS_DIR)

# Minimum training rows per K tried, so a tiny position-group pool
# doesn't get "clustered" into groups of one or two players that are
# really just sampling noise.
MIN_ROWS_PER_K = 5


def model_path(pos):
    return os.path.join(ARTIFACTS_DIR, f'style_clusters_{pos.lower()}.joblib')


def meta_path(pos):
    return os.path.join(ARTIFACTS_DIR, f'style_clusters_{pos.lower()}_meta.json')


def _all_seasons():
    """Every season present on file, oldest first - no "next season"
    pairing needed (clustering has no label), so every season with performance data is usable."""
    meta = load_meta()
    if meta.empty:
        return ()
    return tuple(sorted(meta['season'].astype(str).unique(), key=lambda s: int(str(s).split('-')[0])))


def build_pooled_matrix(pos, seasons, style_categories, min_minutes):
    """Every (season, position group) player-row's style-category
    percentile vector, pooled across seasons (each within its own
    season's pool). Returns (labels_df, X_abs, X_centered) - X_centered is what K-means fits on."""
    cols = cluster_feature_columns(pos, style_categories)
    info_parts, matrix_parts = [], []
    for season in seasons:
        d = load_all_leagues_data(season)
        if d.empty:
            continue
        pos_df, cat_df = build_position_group_matrix(d, pos, style_categories, min_minutes=min_minutes)
        if pos_df.empty:
            continue
        info = pos_df[['player', 'team', 'league']].copy()
        info['season'] = season
        info_parts.append(info)
        matrix_parts.append(cat_df)

    if not info_parts:
        empty = np.empty((0, len(cols)))
        return pd.DataFrame(), empty, empty

    labels_df = pd.concat(info_parts, ignore_index=True)
    abs_df = pd.concat(matrix_parts, ignore_index=True)[cols]
    X_abs = abs_df.to_numpy(dtype=float)
    X_centered = center_on_own_mean(abs_df).to_numpy(dtype=float)
    return labels_df, X_abs, X_centered


def _select_k(X, k_range, random_state, forced_k=None):
    """Fit K-means for every K in k_range, score by silhouette, return
    (best_k, fitted KMeans, {k: silhouette}). `forced_k` still runs the
    full search but returns that K's fitted model - a recorded override, not a different procedure."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    scores, fitted = {}, {}
    for k in k_range:
        if k >= len(X):
            continue
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = km.fit_predict(X)
        if len(set(labels)) < 2:
            continue
        scores[k] = float(silhouette_score(X, labels))
        fitted[k] = km

    if not scores:
        return None, None, {}
    if forced_k is not None and forced_k in fitted:
        return forced_k, fitted[forced_k], scores
    best_k = max(scores, key=scores.get)
    return best_k, fitted[best_k], scores


def train_style_clusters(seasons=None, min_minutes=config.STYLE_CLUSTER_MIN_MINUTES,
                          k_range=config.STYLE_CLUSTER_K_RANGE,
                          random_state=config.STYLE_CLUSTER_RANDOM_STATE):
    """Fit one K-means per POSITION_GROUPS entry, select K by silhouette,
    generate archetype labels (ml.style_clustering.label), persist to
    ml/artifacts/style_clusters_<pos>.joblib. Returns {pos: meta_dict}."""
    import joblib

    if seasons is None:
        seasons = _all_seasons()
    if not seasons:
        return {'error': 'no seasons on file'}

    k_range = list(k_range)
    style_cats = get_playing_style_categories()
    results = {}
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    for pos in POSITION_GROUPS:
        labels_df, X_abs, X = build_pooled_matrix(pos, seasons, style_cats, min_minutes)
        min_rows = max(k_range) * MIN_ROWS_PER_K
        if len(X) < min_rows:
            results[pos] = {'error': f'not enough {pos} player-seasons ({len(X)}) to cluster reliably '
                                      f'(need >= {min_rows} for K up to {max(k_range)})'}
            continue

        # STYLE_CLUSTER_NEGATIVE_WEIGHT down-weights deficiencies before
        # normalizing (must happen before l2_normalize). `X` stays the
        # real, undampened matrix throughout - what label_clusters uses for real-scale percentiles.
        metric = config.STYLE_CLUSTER_DISTANCE_METRIC.get(pos, 'euclidean')
        neg_weight = config.STYLE_CLUSTER_NEGATIVE_WEIGHT.get(pos)
        X_fit = dampen_negative(X, neg_weight) if neg_weight is not None else X
        X_fit = l2_normalize(X_fit) if metric == 'cosine' else X_fit

        forced_k = config.STYLE_CLUSTER_K_OVERRIDE.get(pos)
        best_k, km, silhouette_by_k = _select_k(X_fit, k_range, random_state, forced_k=forced_k)
        if best_k is None:
            results[pos] = {'error': 'silhouette search found no viable K'}
            continue
        argmax_k = max(silhouette_by_k, key=silhouette_by_k.get)

        cols = cluster_feature_columns(pos, style_cats)
        clusters = label_clusters(km, cols, X, X_abs, pos)

        meta = {
            'position': pos,
            'n': int(len(X)),
            'n_players': int(labels_df['player'].nunique()),
            'seasons': list(seasons),
            'min_minutes': min_minutes,
            'distance_metric': metric,
            'negative_weight': neg_weight,
            'k_range_tried': k_range,
            'silhouette_by_k': {str(k): round(v, 4) for k, v in silhouette_by_k.items()},
            'k': int(best_k),
            'silhouette': round(silhouette_by_k[best_k], 4),
            'k_selection': (
                'silhouette_argmax' if best_k == argmax_k else
                f'manual_override (silhouette argmax was K={argmax_k}, '
                f'{round(silhouette_by_k[argmax_k], 4)}) - see config.STYLE_CLUSTER_K_OVERRIDE'
            ),
            'feature_cols': cols,
            'clusters': clusters,
            'validation_note': (
                "Unsupervised - no labeled ground truth to backtest against. K was "
                "chosen by silhouette score (internal cluster separation), which says "
                "nothing about whether a cluster matches real scouting intuition. The "
                "only real validation is a manual face-validity spot check (known "
                "players against obvious real-world archetypes) - report that check's "
                "actual results, do not present these labels as empirically validated "
                "the way the supervised models (market value, sell-high risk) are."
            ),
            'trained_at': datetime.now().isoformat(timespec='seconds'),
        }
        print(f"[{pos}] n={meta['n']} ({meta['n_players']} distinct players)  "
              f"K={best_k} (silhouette={meta['silhouette']})  "
              f"tried: {meta['silhouette_by_k']}")
        for c in clusters:
            print(f"    cluster {c['cluster']} (n={c['size']}): {c['label']} - {c['blurb']}")

        joblib.dump({'model': km, 'feature_cols': cols, 'clusters': clusters, 'meta': meta}, model_path(pos))
        with open(meta_path(pos), 'w') as f:
            json.dump(meta, f, indent=2)
        results[pos] = meta

    return results


if __name__ == '__main__':
    # Standalone run: seed the in-memory store from data/data_files/ first -
    # normally main.py does this at boot, but a manual training pass
    # doesn't go through it.
    loader.boot()
    result = train_style_clusters()
    print(json.dumps(result, indent=2, default=str))
