#!/usr/bin/env python3
"""
Style-archetype assignment: loads the trained per-position K-means
(cached in-process), assigns a player to their nearest cluster. No
heuristic fallback - an untrained position group returns None.
"""

import os
import sys

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend import config
from ml.style_clustering.features import build_features, center_on_own_mean, dampen_negative, l2_normalize
from ml.style_clustering.train import model_path
from backend.scoring.composite import style_category_matrix

_MODEL_CACHE = {}
_MODEL_CACHE_LOADED = set()


def load_model(pos):
    """The trained {'model', 'feature_cols', 'clusters', 'meta'} bundle
    for this position group, or None if untrained. Cached per-position -
    call reload_model() after retraining."""
    if pos in _MODEL_CACHE_LOADED:
        return _MODEL_CACHE.get(pos)
    path = model_path(pos)
    if os.path.exists(path):
        import joblib
        _MODEL_CACHE[pos] = joblib.load(path)
    _MODEL_CACHE_LOADED.add(pos)
    return _MODEL_CACHE.get(pos)


def reload_model(pos=None):
    """Drop the in-process cache so the next load_model(pos) call re-reads
    from disk. pos=None clears every position group's cache; pass a
    specific position to clear just that one."""
    if pos is None:
        _MODEL_CACHE.clear()
        _MODEL_CACHE_LOADED.clear()
    else:
        _MODEL_CACHE.pop(pos, None)
        _MODEL_CACHE_LOADED.discard(pos)


def list_archetypes(pos):
    """Every trained archetype for this position group - [{cluster, label,
    blurb, top_categories, size}], or None if untrained. `size` is the
    TRAINING pool's cluster size, not a live roster count."""
    bundle = load_model(pos)
    if bundle is None:
        return None
    return bundle['clusters']


def predict_bulk(pos_df, pos, style_categories):
    """Nearest-archetype label for every row of pos_df at once - one bulk
    KMeans.predict() call, not one per row. `pos_df` must already be the
    candidate pool the caller wants scored, no re-filtering here."""
    if pos_df.empty:
        return pd.Series(dtype=object)

    bundle = load_model(pos)
    if bundle is None:
        return pd.Series([None] * len(pos_df), index=pos_df.index, dtype=object)

    cols = bundle['feature_cols']
    cat_matrix = style_category_matrix(pos_df, pos, style_categories).reindex(columns=cols).fillna(50.0)
    cat_matrix = center_on_own_mean(cat_matrix)
    X = cat_matrix.to_numpy(dtype=float)
    neg_weight = config.STYLE_CLUSTER_NEGATIVE_WEIGHT.get(pos)
    if neg_weight is not None:
        X = dampen_negative(X, neg_weight)
    if config.STYLE_CLUSTER_DISTANCE_METRIC.get(pos) == 'cosine':
        X = l2_normalize(X)
    cluster_ids = bundle['model'].predict(X)
    label_by_cluster = {c['cluster']: c['label'] for c in bundle['clusters']}
    return pd.Series([label_by_cluster.get(int(cid)) for cid in cluster_ids], index=pos_df.index)


def predict(category_scores, pos, style_categories):
    """Nearest style archetype for one player - {'cluster', 'label',
    'blurb', 'top_categories', 'distance_to_centroid'}, or None if
    untrained. NOTE: distance_to_centroid is bounded (0-2) for cosine positions, unbounded for Euclidean - never compare across metrics."""
    bundle = load_model(pos)
    if bundle is None:
        return None

    model = bundle['model']
    clusters = bundle['clusters']

    x = np.array([build_features(category_scores, pos, style_categories)], dtype=float)
    neg_weight = config.STYLE_CLUSTER_NEGATIVE_WEIGHT.get(pos)
    if neg_weight is not None:
        x = dampen_negative(x, neg_weight)
    if config.STYLE_CLUSTER_DISTANCE_METRIC.get(pos) == 'cosine':
        x = l2_normalize(x)
    cluster_idx = int(model.predict(x)[0])
    centroid = model.cluster_centers_[cluster_idx]
    distance = float(np.linalg.norm(x[0] - centroid))

    info = next((c for c in clusters if c['cluster'] == cluster_idx), None)
    if info is None:
        return None

    return {
        'cluster': cluster_idx,
        'label': info['label'],
        'blurb': info['blurb'],
        'top_categories': info['top_categories'],
        'distance_to_centroid': round(distance, 2),
    }


if __name__ == '__main__':
    # Smoke-test with a plausible aerial target-man forward profile: high
    # Aerial & Heading / Finishing, low creation/dribbling.
    sample = {
        'Finishing & Clinical': 78, 'Expected Goals (xG) & Efficiency': 70,
        'Creativity & Assists': 40, 'Expected Assists (xA)': 35,
        'Dribbling & 1v1 Skills': 30, 'Ball Control & Touch': 45,
        'Progressive Play & Carries': 25, 'Aerial & Heading': 92,
        'Link-Up & Passing': 55, 'Defensive Work': 20, 'Discipline': 50,
    }
    from backend.scoring.composite import get_playing_style_categories
    result = predict(sample, 'FW', get_playing_style_categories())
    print(f"model loaded: {load_model('FW') is not None}")
    print(result)
