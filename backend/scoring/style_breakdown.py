#!/usr/bin/env python3
"""
Playing-style breakdown: per-category percentile/normalized scores with
per-metric detail, plus a strengths/weaknesses summary with generated text.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import safe_float
from backend.scoring.composite import calculate_category_scores, calculate_percentile_score, get_negative_metrics


def category_breakdown(player, pos_df, style_cats, position):
    """Per-category percentile + normalized score, with every category
    metric's own value/percentile. Categories with no measurable data get
    no_data=True instead of a misleading zero."""
    pctl_scores = calculate_category_scores(player, pos_df, style_cats, position, method='percentile', empty_as_none=True)
    norm_scores = calculate_category_scores(player, pos_df, style_cats, position, method='normalized', empty_as_none=True)
    neg_metrics = get_negative_metrics()

    categories = []
    for cat_name in style_cats.get(position, {}).keys():
        available_metrics = [m for m in style_cats[position][cat_name] if m in pos_df.columns]
        metric_details = []
        for m in available_metrics:
            pv = safe_float(player.get(m, 0)) if isinstance(player, dict) else safe_float(player[m]) if m in player.index else 0
            comp = pos_df[m].apply(safe_float).dropna()
            # Skip structurally-N/A columns (no variance in the pool, e.g. a stat
            # that is 0 for a whole season) so the breakdown never shows a
            # misleading "0.00" row that carries no information.
            if len(comp) == 0 or comp.min() == comp.max():
                continue
            pctl = calculate_percentile_score(pv, comp.tolist())
            if m in neg_metrics:
                pctl = 100 - pctl
            metric_details.append({
                'metric': m,
                'value': round(pv, 2),
                'percentile': round(pctl, 1),
            })
        ps = pctl_scores.get(cat_name)
        ns = norm_scores.get(cat_name)
        no_data = (ps is None) or (len(metric_details) == 0)
        categories.append({
            'name': cat_name,
            'percentile_score': None if no_data else round(ps, 1),
            'normalized_score': None if (ns is None) else round(ns, 1),
            'metrics': metric_details,
            'no_data': no_data,
        })
    return categories


def _humanize_metric(m):
    """Lightweight fallback label for a raw metric column (strip gk_
    prefix, turn _per90/_pct into readable suffixes) - not the full
    curated label dictionary scout_engine.py uses, to avoid a two-way import."""
    label = m[3:] if m.startswith('gk_') else m
    label = label.replace('_per90', '/90').replace('_pct', ' %').replace('_', ' ')
    return label.strip()


def _ordinal(n):
    n = int(round(n))
    if 10 <= (n % 100) <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def _band(pctl, low):
    if low:
        return 'Weak' if pctl <= 25 else 'Below par' if pctl <= 40 else 'Room to improve'
    return 'Elite' if pctl >= 85 else 'Strong' if pctl >= 70 else 'Solid' if pctl >= 55 else 'Around average'


def _drivers_for(category, low, top_n=2):
    """Top N metrics driving a category, ranked in the direction the
    highlight cares about (highest percentile for a strength, lowest for a
    weakness)."""
    metrics = sorted(category['metrics'], key=lambda m: m['percentile'], reverse=not low)
    return [
        {'metric': m['metric'], 'label': _humanize_metric(m['metric']), 'value': m['value'], 'percentile': m['percentile']}
        for m in metrics[:top_n]
    ]


def summarize_strengths_weaknesses(categories, top_n=3):
    """Strengths (highest-percentile categories) and weaknesses (lowest), each
    with its driving metrics and a one-line generated description - built
    from the unchanged per-category/per-metric breakdown above."""
    scored = [c for c in categories if not c['no_data'] and c['percentile_score'] is not None]

    def build(cat, low):
        pctl = cat['percentile_score']
        drivers = _drivers_for(cat, low)
        driver_str = '; '.join(f"{d['label']}: {d['value']}" for d in drivers)
        text = f"{_band(pctl, low)} at {cat['name']} ({_ordinal(pctl)} percentile)"
        text += f" - {driver_str}." if driver_str else '.'
        return {'category': cat['name'], 'percentile': pctl, 'drivers': drivers, 'text': text}

    strengths = [build(c, False) for c in sorted(scored, key=lambda c: c['percentile_score'], reverse=True)[:top_n]]
    weaknesses = [build(c, True) for c in sorted(scored, key=lambda c: c['percentile_score'])[:top_n]]
    return strengths, weaknesses
