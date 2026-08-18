#!/usr/bin/env python3
"""
Feature engineering for the sell-high deterioration model: predicts
P(on-field performance deteriorates next season) - deliberately not from
composite_index (mean-reversion dominated). output_score is a z-score against a FROZEN reference, comparable across seasons.
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

from data.loader import safe_float, parse_age, _norm_key, _num_series
from backend import config

# (metric, is_negative_metric, needs_manual_per90) - per position. Four
# DF/MF/FW metrics need manual per-90 (minutes/90) since composite.py
# uses them as raw totals, which would conflate minutes with skill here.
OUTPUT_METRICS_BY_POSITION = {
    'GK': [
        ('gk_save_pct', False, False),
        ('gk_clean_sheets_pct', False, False),
        ('gk_psxg_net_per90', False, False),
        ('gk_goals_against_per90', True, False),
    ],
    'DF': [
        ('tackles', False, True),
        ('interceptions', False, True),
        ('clearances', False, True),
        ('ball_recoveries', False, True),
        ('xg_assist_per90', False, False),
        ('xg_per90', False, False),
        ('goals_per90', False, False),
        ('assists_per90', False, False),
    ],
    'MF': [
        ('xg_per90', False, False),
        ('npxg_per90', False, False),
        ('xg_assist_per90', False, False),
        ('shots_on_target_per90', False, False),
        ('goals_per90', False, False),
        ('assists_per90', False, False),
        ('xgot_per90', False, False),
        ('take_ons_won', False, True),
    ],
    'FW': [
        ('goals_per90', False, False),
        ('assists_per90', False, False),
        ('xg_per90', False, False),
        ('npxg_per90', False, False),
        ('shots_per90', False, False),
        ('xg_assist_per90', False, False),
        ('xgot_per90', False, False),
        ('take_ons_won', False, True),
    ],
}

SELL_HIGH_FEATURE_COLS = [
    'age', 'age_sq',
    'log_current_mv', 'distance_from_peak_mv', 'mv_momentum', 'has_mv_momentum',
    'output_score', 'output_score_delta', 'has_prior_output_score',
    'output_score_prior_2', 'has_output_score_prior_2', 'output_score_change_2',
    'output_score_peak_to_date', 'distance_from_output_score_peak', 'has_output_score_peak_history',
    'log_minutes', 'minutes_delta',
    'goals_per90', 'assists_per90', 'npxg_per90', 'xg_assist_per90', 'sca_per90',
    'power_rating',
    'pos_DF', 'pos_FW', 'pos_GK', 'pos_MF',
]


def _metric_value(row, metric, needs_manual_per90):
    """One metric's value from a row dict, per-90-normalized by hand for
    the four raw-total metrics - None if missing/NaN, so callers skip it
    cleanly rather than treating a missing stat as zero."""
    raw = row.get(metric)
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    val = safe_float(raw)
    if needs_manual_per90:
        minutes = safe_float(row.get('minutes', 0))
        if not minutes or minutes <= 0:
            return None
        val = val / (minutes / 90.0)
    return val


def compute_reference_distributions(seasons, min_minutes=None):
    """{position: {metric: {'mean', 'std'}}} - the frozen reference this
    module is built around. Computed once across all seasons/players (not
    just those with market-value data), persisted into the trained artifact."""
    from data.loader import load_all_leagues_data

    min_minutes = min_minutes if min_minutes is not None else config.SELL_HIGH_REFERENCE_MIN_MINUTES
    values = {pos: {m: [] for m, _, _ in metrics} for pos, metrics in OUTPUT_METRICS_BY_POSITION.items()}

    for s in seasons:
        d = load_all_leagues_data(s)
        if d.empty or 'primary_position' not in d.columns:
            continue
        d = d[_num_series(d['minutes']).fillna(0) >= min_minutes]
        for pos, metrics in OUTPUT_METRICS_BY_POSITION.items():
            pos_df = d[d['primary_position'] == pos]
            if pos_df.empty:
                continue
            for _, r in pos_df.iterrows():
                row = r.to_dict()
                for m, _, manual in metrics:
                    v = _metric_value(row, m, manual)
                    if v is not None:
                        values[pos][m].append(v)

    reference = {}
    for pos, metrics in OUTPUT_METRICS_BY_POSITION.items():
        reference[pos] = {}
        for m, _, _ in metrics:
            vals = values[pos][m]
            if len(vals) < 30:
                continue
            std = float(np.std(vals))
            reference[pos][m] = {'mean': float(np.mean(vals)), 'std': std if std > 0 else 1.0}
    return reference


def output_score(row, position, reference):
    """Average frozen z-score across this position's available metrics -
    None if nothing is computable. Comparable across any two seasons/leagues,
    unlike composite_index's zscore_comp."""
    if row is None:
        return None
    metrics = OUTPUT_METRICS_BY_POSITION.get(position, [])
    ref = reference.get(position, {})
    if not metrics or not ref:
        return None
    zs = []
    for m, neg, manual in metrics:
        params = ref.get(m)
        if params is None:
            continue
        v = _metric_value(row, m, manual)
        if v is None:
            continue
        z = (v - params['mean']) / params['std']
        zs.append(-z if neg else z)
    if not zs:
        return None
    return float(np.mean(zs))


def build_features(row, position, reference, prior_row=None, prior_row_2=None,
                    current_mv=None, prior_mv=None, prior_mv_2=None, peak_mv_to_date=None,
                    output_score_peak_to_date=None):
    """One player-season's feature dict. `current_mv`/`prior_mv`/
    `prior_mv_2`/`peak_mv_to_date` must be REAL values, never estimated.
    `peak_mv_to_date`/`output_score_peak_to_date` must already be leakage-safe."""
    age = parse_age(row.get('age', 25)) or 25
    minutes = safe_float(row.get('minutes', 0))
    prior_minutes = safe_float(prior_row.get('minutes', 0)) if prior_row is not None else None

    log_current_mv = float(np.log1p(current_mv)) if current_mv and current_mv > 0 else 0.0
    has_peak = bool(peak_mv_to_date and peak_mv_to_date > 0)
    distance_from_peak_mv = (
        float(np.log1p(current_mv)) - float(np.log1p(peak_mv_to_date))
    ) if (current_mv and current_mv > 0 and has_peak) else 0.0

    has_mv_momentum = bool(prior_mv and prior_mv > 0 and prior_mv_2 and prior_mv_2 > 0)
    mv_momentum = (
        float(np.log1p(prior_mv)) - float(np.log1p(prior_mv_2))
    ) if has_mv_momentum else 0.0

    score_now = output_score(row, position, reference)
    score_prior = output_score(prior_row, position, reference) if prior_row is not None else None
    score_prior_2 = output_score(prior_row_2, position, reference) if prior_row_2 is not None else None
    has_prior_output_score = score_now is not None and score_prior is not None
    has_output_score_prior_2 = score_prior is not None and score_prior_2 is not None
    output_score_val = score_now if score_now is not None else 0.0
    output_score_delta = (score_now - score_prior) if has_prior_output_score else 0.0
    output_score_prior_2_val = score_prior_2 if score_prior_2 is not None else 0.0
    # prior-vs-prior-2 change (not vs this season) - a second data point on
    # where the player was headed BEFORE the current season, same shape
    # ml.market_value's mv_momentum uses for the identical reason.
    output_score_change_2 = (score_prior - score_prior_2) if has_output_score_prior_2 else 0.0

    has_output_score_peak_history = bool(output_score_peak_to_date is not None and score_now is not None)
    peak_to_date_val = (
        max(output_score_peak_to_date, score_now) if has_output_score_peak_history
        else (score_now if score_now is not None else 0.0)
    )
    distance_from_output_score_peak = (
        (score_now - peak_to_date_val) if score_now is not None else 0.0
    )

    minutes_delta = (minutes - prior_minutes) if prior_minutes is not None else 0.0

    return {
        'age': age,
        'age_sq': float(age) * float(age),
        'log_current_mv': log_current_mv,
        'distance_from_peak_mv': distance_from_peak_mv,
        'mv_momentum': mv_momentum,
        'has_mv_momentum': 1.0 if has_mv_momentum else 0.0,
        'output_score': output_score_val,
        'output_score_delta': output_score_delta,
        'has_prior_output_score': 1.0 if has_prior_output_score else 0.0,
        'output_score_prior_2': output_score_prior_2_val,
        'has_output_score_prior_2': 1.0 if has_output_score_prior_2 else 0.0,
        'output_score_change_2': output_score_change_2,
        'output_score_peak_to_date': peak_to_date_val,
        'distance_from_output_score_peak': distance_from_output_score_peak,
        'has_output_score_peak_history': 1.0 if has_output_score_peak_history else 0.0,
        'log_minutes': float(np.log1p(minutes)),
        'minutes_delta': minutes_delta,
        'goals_per90': safe_float(row.get('goals_per90', 0)),
        'assists_per90': safe_float(row.get('assists_per90', 0)),
        'npxg_per90': safe_float(row.get('npxg_per90', 0)),
        'xg_assist_per90': safe_float(row.get('xg_assist_per90', 0)),
        # Chance-creation - in composite.py's RETIRED_METRICS, so likely
        # null for newest seasons - included since it's useful where it
        # exists, not depended on exclusively.
        'sca_per90': safe_float(row.get('sca_per90', 0)),
        'power_rating': safe_float(row.get('power_rating', 50)) or 50,
        'pos_DF': 1.0 if position == 'DF' else 0.0,
        'pos_FW': 1.0 if position == 'FW' else 0.0,
        'pos_GK': 1.0 if position == 'GK' else 0.0,
        'pos_MF': 1.0 if position == 'MF' else 0.0,
        'player_key': _norm_key(str(row.get('player', ''))) + '|' + str(int(safe_float(row.get('birth_year', 0)))),
    }
