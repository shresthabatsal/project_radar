#!/usr/bin/env python3
"""
Feature engineering for style-archetype clustering: built on the same
style-category percentile vectors composite.py's composite index uses,
kept as a full per-category matrix instead of collapsed to one average.
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

from data.loader import safe_float, _num_series
from backend import config
from backend.scoring.composite import style_category_matrix

# GK excluded on purpose - see module docstring.
POSITION_GROUPS = ('FW', 'MF', 'DF')

# Categories excluded from clustering entirely - real stats, but not
# stylistic dimensions. Discipline is a behavioral trait; who takes
# penalties/crosses is a team-hierarchy fact, not a skill difference.
EXCLUDED_CLUSTER_CATEGORIES_BY_POS = {
    'FW': ('Discipline', 'Penalties & Set Pieces'),
    'MF': ('Discipline & Game Management',),
    'DF': ('Discipline & Errors', 'Crosses & Set Pieces'),
}


def cluster_feature_columns(pos, style_categories):
    """Fixed, ordered list of this position's style-category names - the
    clustering feature space, pinned to style_categories' own key order so
    train.py/predict.py always agree. Excludes EXCLUDED_CLUSTER_CATEGORIES_BY_POS."""
    excluded = EXCLUDED_CLUSTER_CATEGORIES_BY_POS.get(pos, ())
    return [c for c in style_categories.get(pos, {}).keys() if c not in excluded]


def center_on_own_mean(matrix):
    """Row-wise centering: subtract each player's own mean across
    clustering categories, so clustering fits on relative emphasis/shape,
    not absolute magnitude - an uncentered fit collapsed into one meaningless "Balanced" catch-all."""
    return matrix.sub(matrix.mean(axis=1), axis=0)


def dampen_negative(x, weight):
    """Scale only the negative entries of a centered vector by `weight`,
    leaving positives untouched, so a deficiency pulls the fit direction
    less hard than an equal-size elevation. Apply BEFORE l2_normalize, never after."""
    x = np.asarray(x, dtype=float)
    return np.where(x < 0, x * weight, x)


def l2_normalize(x):
    """Rescale each row to unit length - strips magnitude, keeps
    direction. Euclidean K-means on the result is mathematically
    identical to cosine similarity. A zero-norm row is left as all-zeros rather than divided."""
    x = np.asarray(x, dtype=float)
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    return x / safe_norms


def build_position_group_matrix(df, pos, style_categories, min_minutes=config.STYLE_CLUSTER_MIN_MINUTES):
    """(pos_df, feature_matrix) for one broad position group: pos_df is
    the minutes-filtered pool; feature_matrix fills missing/under-covered
    categories with 50.0 (neutral), matching build_season_position_table's convention."""
    if 'primary_position' not in df.columns:
        return df.iloc[0:0].copy(), pd.DataFrame()

    pos_df = df[df['primary_position'] == pos].copy()
    if 'minutes' in pos_df.columns and min_minutes:
        pos_df = pos_df[_num_series(pos_df['minutes']).fillna(0) >= min_minutes]
    pos_df = pos_df.reset_index(drop=True)
    if pos_df.empty:
        return pos_df, pd.DataFrame()

    cols = cluster_feature_columns(pos, style_categories)
    cat_df = style_category_matrix(pos_df, pos, style_categories)
    cat_df = cat_df.reindex(columns=cols).fillna(50.0)
    return pos_df, cat_df


def build_features(category_scores, pos, style_categories):
    """Turn one player's {category_name: percentile} dict into the
    fixed-order, own-mean-centered vector predict.py feeds to KMeans.
    Missing categories fill with 50.0, matching build_position_group_matrix's convention."""
    cols = cluster_feature_columns(pos, style_categories)
    out = []
    for c in cols:
        v = category_scores.get(c)
        out.append(safe_float(v) if v is not None else 50.0)
    if out:
        mean = sum(out) / len(out)
        out = [v - mean for v in out]
    return out
