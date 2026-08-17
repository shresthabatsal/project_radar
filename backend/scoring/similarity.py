#!/usr/bin/env python3
"""
Similar-players search: distance over the position's full raw per-90
metric set (20-40 columns, not the collapsed category percentile scores).
Four selectable distance methods (SIMILARITY_METHODS below); mahalanobis is the default.
"""

import os
import sys

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import MinCovDet
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances, manhattan_distances
from scipy.spatial.distance import mahalanobis as mahalanobis_dist

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import _num_series


# Frontend-facing reasoning for each method, kept here so the "why pick
# this" copy has one source of truth. GET /similarity-methods serves this verbatim.
SIMILARITY_METHODS = {
    'cosine': {
        'label': 'Cosine',
        'description': "Measures the ANGLE between two players' statistical profiles, "
                        "ignoring overall magnitude.",
        'best_for': 'Comparing playing STYLE/SHAPE independent of volume - e.g. a squad '
                    'rotation player and a first-choice starter with a similar per-90 '
                    'profile but very different total minutes.',
    },
    'euclidean': {
        'label': 'Euclidean',
        'description': 'Straight-line distance treating every metric equally, with no '
                        'adjustment for how metrics relate to each other.',
        'best_for': 'A simple, intuitive "closest overall stat-line" comparison when you '
                    'want an easy-to-explain baseline rather than a statistically '
                    'adjusted one.',
    },
    'manhattan': {
        'label': 'Manhattan',
        'description': "Sums absolute differences across metrics rather than squaring "
                        "them, so it's less dominated by any single large difference.",
        'best_for': "A comparison that's robust to one metric being an outlier while the "
                    'rest of the profile is genuinely close.',
    },
    'mahalanobis': {
        'label': 'Mahalanobis',
        'description': 'Accounts for the correlation structure between metrics via a '
                        "robust covariance estimate, so correlated skills (e.g. goals and "
                        "xG, tackles and interceptions) aren't double-counted.",
        'best_for': 'The statistically rigorous default for football data, where metrics '
                    'are heavily inter-correlated - recommended unless you have a '
                    'specific reason to compare style-only (cosine) or want a simpler, '
                    'unadjusted baseline (euclidean/manhattan).',
    },
}

DEFAULT_SIMILARITY_METHOD = 'mahalanobis'


def position_pool(df, position):
    """Rows for players who play OR can play `position` - primary position
    match, plus secondary position so versatile players are included."""
    if 'primary_position' not in df.columns:
        return df.copy()
    mask = df['primary_position'] == position
    if 'secondary_position' in df.columns:
        mask = mask | (df['secondary_position'] == position)
    return df[mask].copy()


def _metric_universe(position, style_categories, columns):
    """Deduplicated, ordered list of every metric across all of the position's
    style categories that's present in the data - the full raw per-90 metric
    set the distance is computed over, not the collapsed category scores."""
    cats = style_categories.get(position, {})
    keys = []
    for metrics in cats.values():
        for m in metrics:
            if m in columns and m not in keys:
                keys.append(m)
    return keys


def find_similar(pos_df, player_ref, position, style_categories, method=DEFAULT_SIMILARITY_METHOD):
    """Rank pos_df by distance to player_ref, over the position's full raw
    per-90 metric set. Returns None if fewer than 2 usable metrics exist,
    else a dict with 'pos_df' (possibly narrowed), 'sims', 'match', 'rank', 'pool_size', 'method'."""
    metric_keys = _metric_universe(position, style_categories, set(pos_df.columns))
    if len(metric_keys) < 2:
        return None

    pos_df = pos_df.reset_index(drop=True)
    target_row = player_ref if isinstance(player_ref, dict) else player_ref.to_dict()

    combined = pd.concat([pos_df, pd.DataFrame([target_row])], ignore_index=True)
    raw_matrix = pd.DataFrame(
        {m: _num_series(combined[m]) for m in metric_keys}, index=combined.index)

    target_vec = raw_matrix.iloc[-1]
    pool_matrix = raw_matrix.iloc[:-1].reset_index(drop=True)

    # Coverage guard: drop candidates missing more than half their raw
    # metrics - too thin a profile to compare, would be dominated by the
    # pool-mean imputation below.
    coverage = pool_matrix.notna().mean(axis=1)
    keep = coverage >= 0.5
    if keep.sum() >= 10:
        pos_df = pos_df[keep.values].reset_index(drop=True)
        pool_matrix = pool_matrix[keep.values].reset_index(drop=True)

    # A metric can still be entirely absent (all-NaN) for this specific pool
    # even though the column exists - drop those before imputing/scaling so
    # the pool mean isn't itself NaN.
    pool_means = pool_matrix.mean(axis=0)
    usable = [m for m in metric_keys if pd.notna(pool_means.get(m))]
    if len(usable) < 2:
        return None
    pool_matrix = pool_matrix[usable]
    pool_means = pool_means[usable]
    target_vec = target_vec[usable]

    # Pool-mean imputation for missing values (computed AFTER the coverage
    # filter, so a handful of thin profiles don't drag the mean off).
    X_pool = pool_matrix.fillna(pool_means).to_numpy(dtype=float)
    x_target = target_vec.fillna(pool_means).to_numpy(dtype=float).reshape(1, -1)

    # Scale - Mahalanobis is scale-sensitive, and StandardScaler keeps every
    # metric on a comparable footing (raw counts vs. per-90 rates vs. %)
    # before the covariance estimate.
    try:
        scaler = StandardScaler()
        pool_scaled = scaler.fit_transform(X_pool)
        target_scaled = scaler.transform(x_target)
    except Exception:
        pool_scaled = X_pool
        target_scaled = x_target

    method = method if method in SIMILARITY_METHODS else DEFAULT_SIMILARITY_METHOD

    if method == 'cosine':
        # [-1, 1] -> [0, 1] before the shared min-max match-score step -
        # that step is affine-invariant so this shift doesn't change final
        # scores, but keeps "higher = closer" meaningful if `sims` is read directly.
        sims = (cosine_similarity(target_scaled, pool_scaled)[0] + 1) / 2
    elif method == 'euclidean':
        dists = euclidean_distances(target_scaled, pool_scaled)[0]
        sims = 1 / (1 + dists)
    elif method == 'manhattan':
        dists = manhattan_distances(target_scaled, pool_scaled)[0]
        sims = 1 / (1 + dists)
    else:
        n_samples, n_feat = pool_scaled.shape
        try:
            # Covariance needs more samples than features to be full-rank;
            # below that, MinCovDet returns a near-singular matrix and
            # distances blow up. Guard and fall back to Euclidean rather than return garbage.
            if n_samples <= n_feat + 1:
                raise ValueError('pool too small for a stable covariance estimate')
            all_data = np.vstack([target_scaled[0], pool_scaled])
            cov_est = MinCovDet(support_fraction=0.75)
            cov_est.fit(all_data)
            cov_matrix = cov_est.covariance_ + np.eye(all_data.shape[1]) * 1e-6
            if np.linalg.cond(cov_matrix) > 1e6:
                raise ValueError('covariance ill-conditioned')
            inv_cov = np.linalg.inv(cov_matrix)
            dists = []
            for row_feat in pool_scaled:
                try:
                    d = mahalanobis_dist(target_scaled[0], row_feat, inv_cov)
                except Exception:
                    d = np.linalg.norm(target_scaled[0] - row_feat)
                dists.append(d)
            dists = np.array(dists)
            sims = np.exp(-dists / (np.mean(dists) + 1e-6))
        except Exception:
            dists = euclidean_distances(target_scaled, pool_scaled)[0]
            sims = 1 / (1 + dists)

    # Magnitude-preserving match score (0-100): min-max of the raw distance
    # across the FULL eligible pool (before page/filter/sort) - keeps a
    # candidate's match score stable as top_n/page/filters change.
    s_min, s_max = float(np.min(sims)), float(np.max(sims))
    match = (sims - s_min) / (s_max - s_min) * 100 if s_max > s_min else np.full(len(sims), 100.0)
    pool_size = int(len(sims))
    order = np.argsort(sims)[::-1]
    rank_of = np.empty(len(sims), dtype=int)
    for pos_rank, idx_ in enumerate(order):
        rank_of[idx_] = pos_rank + 1

    return {
        'pos_df': pos_df,
        'sims': sims,
        'match': match,
        'rank': rank_of,
        'pool_size': pool_size,
        'metrics_used': usable,
        'method': method,
    }
