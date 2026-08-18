#!/usr/bin/env python3
"""
Archetype label + blurb generation for a trained cluster: identifies the
top 2-3 elevated style categories and feeds them through style_breakdown.
py's _band()/_ordinal() text primitives. Labels are built directly from category names, not a hand-curated lookup.
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
from backend.scoring.style_breakdown import _band, _ordinal

MAX_ELEVATED_CATEGORIES = 3


def _deficient_category(centered_center, abs_means, feature_cols, margin):
    """This centroid's single most deficient category (centered value at
    least `margin` below zero), or None. Only consulted when
    _elevated_categories found nothing - a distinct shape from being flat everywhere."""
    name, rel = min(zip(feature_cols, centered_center), key=lambda p: p[1])
    if rel <= -margin:
        return name, float(abs_means[name])
    return None


def _elevated_categories(centered_center, abs_means, feature_cols, margin):
    """This centroid's style categories at least `margin` percentile-
    points above zero (centered space), highest first, capped at
    MAX_ELEVATED_CATEGORIES. Reported using `abs_means` so text reads in real percentile terms."""
    pairs = sorted(zip(feature_cols, centered_center), key=lambda p: p[1], reverse=True)
    elevated = [(name, float(abs_means[name])) for name, rel in pairs if rel >= margin]
    return elevated[:MAX_ELEVATED_CATEGORIES]


def _archetype_label(elevated, deficient=None):
    """The elevated categories' names joined with " / ". Falls back to
    `deficient` as "Limited <category>" when nothing is elevated, and to
    "Balanced / Well-Rounded" only when neither exists."""
    if elevated:
        return " / ".join(name for name, _ in elevated)
    if deficient:
        return f"Limited {deficient[0]}"
    return "Balanced / Well-Rounded"


def _archetype_blurb(elevated, deficient=None):
    """One sentence per elevated category, in style_breakdown.py's
    _band()/_ordinal() phrasing. Falls back to `deficient` using the same
    primitives, so a weakness-defined cluster reads in the same voice as a strength-defined one."""
    if elevated:
        parts = [f"{_band(pctl, False)} at {name} ({_ordinal(pctl)} percentile)" for name, pctl in elevated]
        return "; ".join(parts) + "."
    if deficient:
        name, pctl = deficient
        return (f"{_band(pctl, True)} at {name} ({_ordinal(pctl)} percentile) - "
                f"no other category stands out by comparison.")
    return "No single standout category - a balanced, well-rounded statistical profile."


def label_clusters(km, feature_cols, X_centered, X_abs, pos, margin=config.STYLE_CLUSTER_ELEVATED_MARGIN):
    """One {cluster, label, blurb, top_categories, size} dict per cluster.
    `X_abs` reports real percentiles; `X_centered` is the real-scale
    centered matrix, used instead of km.cluster_centers_ since a cosine fit's centers live on the unit sphere."""
    labels = km.labels_
    sizes = pd.Series(labels).value_counts().to_dict()
    centered_df = pd.DataFrame(X_centered, columns=feature_cols)
    abs_df = pd.DataFrame(X_abs, columns=feature_cols)
    overrides = config.ARCHETYPE_NAME_OVERRIDES.get(pos, {})
    clusters = []
    for i in range(len(km.cluster_centers_)):
        member_mask = (labels == i)
        if member_mask.any():
            center = centered_df.loc[member_mask].mean().to_numpy()
            abs_means = abs_df.loc[member_mask].mean().to_dict()
        else:
            center = np.zeros(len(feature_cols))
            abs_means = {c: 50.0 for c in feature_cols}
        elevated = _elevated_categories(center, abs_means, feature_cols, margin)
        # Only consulted when nothing is elevated - see _deficient_category.
        deficient = None if elevated else _deficient_category(center, abs_means, feature_cols, margin)
        algo_label = _archetype_label(elevated, deficient)
        clusters.append({
            'cluster': int(i),
            'label': overrides.get(algo_label, algo_label),
            'blurb': _archetype_blurb(elevated, deficient),
            'top_categories': [{'category': n, 'percentile': round(p, 1)} for n, p in elevated],
            'size': int(sizes.get(i, 0)),
        })
    return clusters
