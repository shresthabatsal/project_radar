#!/usr/bin/env python3
"""
Impact Score: on-pitch team differential (on_goals_for/against,
on_xg_for/against, plus_minus, plus_minus_wowy, xg_plus_minus_wowy) - a
structurally different signal from composite/gems/moneyball's own-output focus.
"""

import os
import sys

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from data.loader import safe_float
from backend.scoring.composite import calculate_percentile_score

IMPACT_METRICS = (
    'on_goals_for', 'on_goals_against', 'on_xg_for', 'on_xg_against',
    'plus_minus', 'plus_minus_wowy', 'xg_plus_minus_wowy',
)

# Higher is worse for these two - inverted before averaging, same convention
# as composite.py's get_negative_metrics().
IMPACT_NEGATIVE_METRICS = frozenset({'on_goals_against', 'on_xg_against'})

IMPACT_METRIC_LABELS = {
    'on_goals_for': 'Team goals scored (player on pitch)',
    'on_goals_against': 'Team goals conceded (player on pitch)',
    'on_xg_for': 'Team xG for (player on pitch)',
    'on_xg_against': 'Team xG against (player on pitch)',
    'plus_minus': 'Goal differential (player on pitch)',
    'plus_minus_wowy': 'Goal differential, with-or-without-you',
    'xg_plus_minus_wowy': 'xG differential, with-or-without-you',
}


def impact_description(score):
    if score is None:
        return None
    if score >= config.IMPACT_TIER_STRONGLY_POSITIVE: return "Strongly Positive Impact"
    if score >= config.IMPACT_TIER_POSITIVE: return "Positive Impact"
    if score >= config.IMPACT_TIER_NEUTRAL: return "Neutral Impact"
    if score >= config.IMPACT_TIER_NEGATIVE: return "Negative Impact"
    return "Strongly Negative Impact"


def impact_breakdown(player, pos_df, min_minutes, minutes):
    """Percentile-based Impact Score (average percentile across the 7
    on/off-pitch differential metrics, negatives inverted) against an
    already minutes-gated pool. qualifies=False when under the minutes gate."""
    if minutes < min_minutes:
        return {
            'qualifies': False,
            'min_minutes': min_minutes,
            'minutes': round(minutes, 1),
            'impact_score': None,
            'label': None,
            'components': [],
        }

    components = []
    percentiles = []
    for metric in IMPACT_METRICS:
        if metric not in pos_df.columns:
            continue
        pv = safe_float(player.get(metric, 0)) if isinstance(player, dict) else \
            (safe_float(player[metric]) if metric in player.index else 0)
        comp = pos_df[metric].apply(safe_float).dropna()
        # Skip a metric with no variance in the pool (e.g. structurally 0 for
        # a whole season) rather than let it inject a flat, meaningless ~50.
        if len(comp) == 0 or comp.min() == comp.max():
            continue
        pctl = calculate_percentile_score(pv, comp.tolist())
        if metric in IMPACT_NEGATIVE_METRICS:
            pctl = 100 - pctl
        components.append({
            'metric': metric,
            'label': IMPACT_METRIC_LABELS.get(metric, metric),
            'value': round(pv, 2),
            'percentile': round(pctl, 1),
        })
        percentiles.append(pctl)

    impact_score = round(float(np.mean(percentiles)), 1) if percentiles else None
    return {
        'qualifies': True,
        'min_minutes': min_minutes,
        'minutes': round(minutes, 1),
        'impact_score': impact_score,
        'label': impact_description(impact_score),
        'components': components,
    }
