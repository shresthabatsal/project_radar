#!/usr/bin/env python3
"""
Feature engineering for the market-value model. Features are pool-
independent (no z-score/composite) so there's no train/inference drift.
"""

import os
import sys

import numpy as np

# ml/ is a sibling of data/ and backend/ - put the project root on sys.path
# so `from data import loader` and `from backend import config` resolve
# whether this module is launched directly or imported as a package.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import safe_float, parse_age, contract_months_remaining, _norm_key
from backend import config

MV_FEATURE_COLS = ['power_rating', 'age', 'age_sq', 'log_min', 'log_games', 'contract_months',
                   'goals_per90', 'assists_per90', 'npxg_per90', 'xg_assist_per90', 'sca_per90',
                   'def_actions_per90', 'aerials_won_pct', 'prog_passes_per90', 'gk_save_pct',
                   'pos_DF', 'pos_FW', 'pos_GK', 'pos_MF', 'log_prior_mv', 'has_prior_mv',
                   'log_prior_mv_2', 'has_prior_mv_2', 'mv_momentum', 'mv_volatility',
                   'n_real_prior_seasons', 'season_year']

# Arbitrary anchor year - only the offset from it matters to a tree
# model. Real labeled data currently spans only two adjacent seasons, so
# this has little signal yet, but is wired through for future backfill.
MV_SEASON_REFERENCE_YEAR = 2020


def _season_year(season):
    """Start year offset from MV_SEASON_REFERENCE_YEAR - a plain numeric
    offset, not one-hot, so an unseen year still slots in on the same scale."""
    try:
        return int(str(season).split('-')[0]) - MV_SEASON_REFERENCE_YEAR
    except Exception:
        return 0


def build_features(row, prior_mv=None, prior_mv_2=None):
    """Turn one raw player-season row into the feature dict the market-
    value model trains/predicts on. `prior_mv`/`prior_mv_2` are this
    player's real value 1/2 seasons back (has_prior_mv flags distinguish unknown from known-zero)."""
    age = parse_age(row.get('age', 25)) or 25
    mins = safe_float(row.get('minutes', 0))
    games = safe_float(row.get('games', row.get('games_starts', 0)))
    pos = str(row.get('primary_position', row.get('position', 'MF')))

    def p90(v):
        return (v / mins * 90.0) if mins > 0 else 0.0

    # Contract length remaining (months) is a real value driver but sparse -
    # impute a neutral ~30 months (mid-contract) when unknown so it doesn't
    # push the estimate around for the many players who have no contract on file.
    cm = contract_months_remaining(row)
    cm = config.MV_MODEL_CONTRACT_MONTHS_DEFAULT if cm is None else max(
        config.MV_MODEL_CONTRACT_MONTHS_MIN, min(config.MV_MODEL_CONTRACT_MONTHS_MAX, float(cm)))

    prior_mv_val = safe_float(prior_mv) if prior_mv else 0.0
    has_prior_mv = 1.0 if prior_mv_val > 0 else 0.0
    log_prior_mv = float(np.log1p(prior_mv_val)) if prior_mv_val > 0 else 0.0

    prior_mv_2_val = safe_float(prior_mv_2) if prior_mv_2 else 0.0
    has_prior_mv_2 = 1.0 if prior_mv_2_val > 0 else 0.0
    log_prior_mv_2 = float(np.log1p(prior_mv_2_val)) if prior_mv_2_val > 0 else 0.0

    # Both zero unless BOTH real points exist - a momentum number from only
    # one real point plus a padded zero would be meaningless (log1p(0)=0
    # would misleadingly read as "fell to near-zero").
    has_both_priors = has_prior_mv > 0 and has_prior_mv_2 > 0
    mv_momentum = (log_prior_mv - log_prior_mv_2) if has_both_priors else 0.0
    mv_volatility = abs(mv_momentum) if has_both_priors else 0.0
    n_real_prior_seasons = has_prior_mv + has_prior_mv_2

    # Position-aware performance signals, all pool-independent raw per-90s -
    # gives defenders/keepers real signal instead of goals/assists only
    # (def_actions_per90+aerials for DF, gk_save_pct for GK).
    return {
        'power_rating': safe_float(row.get('power_rating', 50)) or 50,
        'age': age,
        'age_sq': float(age) * float(age),                 # value-vs-age is humped, not linear
        'log_min': float(np.log1p(max(0.0, mins))),
        'log_games': float(np.log1p(max(0.0, games))),
        'contract_months': cm,
        'goals_per90': safe_float(row.get('goals_per90', 0)),
        'assists_per90': safe_float(row.get('assists_per90', 0)),
        'npxg_per90': safe_float(row.get('npxg_per90', 0)),
        'xg_assist_per90': safe_float(row.get('xg_assist_per90', 0)),
        'sca_per90': safe_float(row.get('sca_per90', 0)),
        'def_actions_per90': p90(safe_float(row.get('tackles', 0)) + safe_float(row.get('interceptions', 0))),
        'aerials_won_pct': safe_float(row.get('aerials_won_pct', 0)),
        'prog_passes_per90': p90(safe_float(row.get('progressive_passes', 0))),
        'gk_save_pct': safe_float(row.get('gk_save_pct', 0)),
        'pos_DF': 1.0 if pos == 'DF' else 0.0,
        'pos_FW': 1.0 if pos == 'FW' else 0.0,
        'pos_GK': 1.0 if pos == 'GK' else 0.0,
        'pos_MF': 1.0 if pos == 'MF' else 0.0,
        'log_prior_mv': log_prior_mv,
        'has_prior_mv': has_prior_mv,
        'log_prior_mv_2': log_prior_mv_2,
        'has_prior_mv_2': has_prior_mv_2,
        'mv_momentum': mv_momentum,
        'mv_volatility': mv_volatility,
        'n_real_prior_seasons': n_real_prior_seasons,
        'season_year': _season_year(row.get('season')),
        # not a feature - identity for GroupKFold so the same player can't sit in
        # both the train and test fold (which inflates the cross-validated R2)
        'player_key': _norm_key(str(row.get('player', ''))) + '|' + str(int(safe_float(row.get('birth_year', 0)))),
    }
