#!/usr/bin/env python3
"""
Market-value heuristic + trained model. calculate_player_market_value()
is the hand-tuned fallback; train_mv_models() fits a GBM predicting
log(current_mv/prior_mv), validated by both GroupKFold and a temporal holdout - report both, never just the optimistic one.
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data import loader
from data.loader import (
    merge_supplementary, load_all_leagues_data, safe_float, _norm_key,
    load_all_supplementary, prev_season_label,
)
from backend import config
from ml.market_value.features import MV_FEATURE_COLS, build_features
from ml.market_value.eval_utils import (
    start_year, select_hyperparams, oof_evaluation_report, temporal_holdout_report,
)

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'artifacts')
ARTIFACTS_DIR = os.path.normpath(ARTIFACTS_DIR)
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'mv_gbm.joblib')
# Standalone JSON mirror of the joblib bundle's 'meta' dict, so hyperparameters/
# CV score are inspectable with a plain file read, without loading joblib/sklearn.
META_PATH = os.path.join(ARTIFACTS_DIR, 'mv_gbm_meta.json')


def calculate_player_market_value(power_rating, age, position, league, minutes=0, games=0, performance=None):
    # League base (per power rating). The power rating already encodes
    # league strength, so there is no separate league-name multiplier - an
    # old one double-counted league and broke on slug mismatches.
    if power_rating >= config.MV_PR_90:
        base = config.MV_BASE_90 + (power_rating - config.MV_PR_90) * config.MV_INCR_90         # 6-12M
    elif power_rating >= config.MV_PR_80:
        base = config.MV_BASE_80 + (power_rating - config.MV_PR_80) * config.MV_INCR_80         # 3-6M
    elif power_rating >= config.MV_PR_70:
        base = config.MV_BASE_70 + (power_rating - config.MV_PR_70) * config.MV_INCR_70         # 1.5-3M
    elif power_rating >= config.MV_PR_60:
        base = config.MV_BASE_60 + (power_rating - config.MV_PR_60) * config.MV_INCR_60         # 0.75-1.5M
    elif power_rating >= config.MV_PR_50:
        base = config.MV_BASE_50 + (power_rating - config.MV_PR_50) * config.MV_INCR_50         # 0.3-0.75M
    else:
        base = config.MV_BASE_UNDER_50 + max(0, (power_rating - config.MV_PR_FLOOR_40)) * config.MV_INCR_UNDER_50

    pm = config.MV_POSITION_MULTIPLIERS.get(position, config.MV_POSITION_MULTIPLIER_DEFAULT)

    if age < config.MV_AGE_U21_MAX: am = config.MV_AGE_MULT_U21
    elif age < config.MV_AGE_U24_MAX: am = config.MV_AGE_MULT_U24
    elif age <= config.MV_AGE_26_MAX: am = config.MV_AGE_MULT_26
    elif age <= config.MV_AGE_28_MAX: am = config.MV_AGE_MULT_28
    elif age <= config.MV_AGE_30_MAX: am = config.MV_AGE_MULT_30
    elif age <= config.MV_AGE_32_MAX: am = config.MV_AGE_MULT_32
    else: am = config.MV_AGE_MULT_OVER_32

    fm = config.MV_FATIGUE_MULT_DEFAULT
    if games > 0 and minutes > 0:
        avg_min = minutes / games
        if avg_min > config.MV_HIGH_MINUTES_PER_GAME: fm = config.MV_HIGH_MINUTES_MULT
        elif avg_min < config.MV_LOW_MINUTES_PER_GAME: fm = config.MV_LOW_MINUTES_MULT

    # Performance scaling (0-100). The league base reflects roughly a top
    # player in that league; this scales it down for everyone else. None ->
    # no scaling.
    perf_mult = config.MV_PERF_MULT_DEFAULT
    if performance is not None:
        p = max(0.0, min(100.0, float(performance)))
        perf_mult = min(config.MV_PERF_MULT_MAX, max(config.MV_PERF_MULT_MIN, (p / 100.0) ** config.MV_PERF_MULT_EXPONENT))

    return base * pm * am * fm * perf_mult


def _build_prior_mv_lookup():
    """{(norm_player_key, season): market_value_eur} from the full
    supplementary table - lets each training row look up its player's real
    value from the immediately preceding season, wherever that season is."""
    wide = load_all_supplementary()
    lookup = {}
    if wide.empty:
        return lookup
    for _, row in wide.iterrows():
        mv = safe_float(row.get('market_value_eur', 0))
        if mv <= 0:
            continue
        key = (_norm_key(str(row.get('player', ''))), str(row.get('season', '')))
        lookup.setdefault(key, mv)
    return lookup


def _seasons_with_real_labels():
    """Auto-detect which seasons have real market_value_eur rows on file -
    avoids pulling in load_supplementary()'s "fall back to latest season"
    behavior, which would mislabel old stats with a different season's price."""
    wide = load_all_supplementary()
    if wide.empty:
        return ()
    real = wide[pd.to_numeric(wide['market_value_eur'], errors='coerce').fillna(0) > 0]
    return tuple(sorted(real['season'].astype(str).unique()))


def train_mv_models(seasons=None):
    """Fit the growth-ratio GBM on real market_value_eur values, evaluate
    two ways, persist to MODEL_PATH. Every training row REQUIRES a real
    prior-season anchor; seasons defaults to auto-detected real-labeled seasons."""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import GroupKFold
    import joblib

    if seasons is None:
        seasons = _seasons_with_real_labels()
    if not seasons:
        return {'error': 'no seasons with real market_value_eur data on file'}

    prior_lookup = _build_prior_mv_lookup()

    rows = []
    for s in seasons:
        d = merge_supplementary(load_all_leagues_data(s), s)
        if d.empty or 'market_value_eur' not in d.columns:
            continue
        d = d[pd.to_numeric(d['market_value_eur'], errors='coerce').fillna(0) > 0]
        prior_season = prev_season_label(s)
        prior_season_2 = prev_season_label(prior_season) if prior_season else None
        for _, r in d.iterrows():
            key = _norm_key(str(r.get('player', '')))
            prior_mv = prior_lookup.get((key, prior_season)) if prior_season else None
            if not prior_mv or prior_mv <= 0:
                continue  # no real anchor to divide by - see docstring above
            prior_mv_2 = prior_lookup.get((key, prior_season_2)) if prior_season_2 else None
            feat = build_features(r.to_dict(), prior_mv=prior_mv, prior_mv_2=prior_mv_2)
            feat['mv'] = safe_float(r.get('market_value_eur'))
            # Eval-only (excluded from MV_FEATURE_COLS, same as player_key) -
            # lets the evaluation breakdown below group by position.
            feat['position'] = str(r.get('primary_position', r.get('position', 'MF')))
            # Eval-only (raw EUR) - the anchor for both the growth-ratio
            # target below and the by-prior-bracket reliability breakdown.
            # Always > 0 here (see the `continue` above).
            feat['prior_mv_eur'] = float(prior_mv)
            feat['season_start_year'] = start_year(s)
            rows.append(feat)
    if len(rows) < 100:
        return {'error': f'not enough labeled market values with a real prior-season anchor ({len(rows)})'}

    train_df = pd.DataFrame(rows)
    X = train_df[MV_FEATURE_COLS].values
    mv_eur = train_df['mv'].values
    prior_mv_eur = train_df['prior_mv_eur'].values
    positions = train_df['position'].values
    season_start_years = train_df['season_start_year'].values
    groups = train_df['player_key'].values

    # GROWTH-RATIO target: log(this season's value / prior season's value).
    # has_prior_mv is a CONSTANT 1.0 by construction here - expect ~0%
    # feature importance for it; that's correct, not a bug.
    y = np.log(mv_eur / prior_mv_eur)

    # GroupKFold by player: the same player recurs across seasons, so plain
    # K-fold would inflate R2. Does NOT guard against temporal leakage -
    # see eval_utils.temporal_holdout_report, run separately below.
    n_groups = len(set(groups))
    cv = GroupKFold(n_splits=min(5, max(2, n_groups)))

    hyperparams, gbm_r2 = select_hyperparams(X, y, groups, cv)
    gbm = GradientBoostingRegressor(**hyperparams).fit(X, y)

    oof_eval = oof_evaluation_report(X, y, mv_eur, positions, prior_mv_eur, groups, cv, hyperparams)
    temporal_eval = temporal_holdout_report(X, y, mv_eur, positions, prior_mv_eur, season_start_years, hyperparams)

    meta = {
        'n': len(train_df),
        'n_players': int(n_groups),
        'seasons': list(seasons),
        'target': 'log(current_mv / prior_mv)',
        'hyperparams': hyperparams,
        'gbm_r2_target_space': round(gbm_r2, 3),
        'oof_evaluation': oof_eval,
        'temporal_holdout_evaluation': temporal_eval,
        # Top-level convenience mirrors of the OOF block, for readers that
        # look up mdape_pct_by_prior_bracket directly on meta rather than under 'oof_evaluation'.
        'mdape_pct': oof_eval['mdape_pct'],
        'mdape_pct_by_position': oof_eval['mdape_pct_by_position'],
        'mdape_pct_by_prior_bracket': oof_eval['mdape_pct_by_bracket'],
        'mdape_summary': oof_eval['mdape_summary'],
        'trained_at': datetime.now().isoformat(timespec='seconds'),
    }
    print(f"Selected hyperparameters (best of grid search, GroupKFold R2 in target-space={gbm_r2:.3f}): {hyperparams}")
    print(f"OOF (GroupKFold): {oof_eval['mdape_summary']} directional accuracy {oof_eval['directional_accuracy_pct']:.1f}%")
    print(f"OOF MdAPE by position: {oof_eval['mdape_pct_by_position']}")
    if temporal_eval:
        print(f"Temporal holdout (years {temporal_eval['held_out_years']}): "
              f"{temporal_eval['mdape_summary']} directional accuracy {temporal_eval['directional_accuracy_pct']:.1f}%")
    else:
        print("Temporal holdout: skipped (not enough distinct seasons on file)")

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    joblib.dump({'model': gbm, 'feature_cols': MV_FEATURE_COLS, 'meta': meta}, MODEL_PATH)
    with open(META_PATH, 'w') as f:
        json.dump(meta, f, indent=2)
    return meta


if __name__ == '__main__':
    # Standalone run: seed the in-memory store from data/data_files/ first -
    # normally backend/main.py does this at boot, but a manual training pass
    # doesn't go through it.
    loader.boot()
    result = train_mv_models()
    print(json.dumps(result, indent=2))
