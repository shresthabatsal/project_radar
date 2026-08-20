#!/usr/bin/env python3
"""
Market-value prediction: loads the trained GBM from ml/artifacts/ (cached
in-process) and predicts from a raw player-season row. Falls back to the
heuristic in train.py when no trained artifact exists yet.
"""

import os
import sys

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend import config
from data.loader import safe_float
from ml.market_value.features import build_features
from ml.market_value.train import MODEL_PATH, calculate_player_market_value

_MODEL_CACHE = None
_MODEL_CACHE_LOADED = False


def load_model():
    """The trained {'model', 'feature_cols', 'meta'} bundle, or None if no
    artifact has been trained yet. Cached after the first successful load -
    call reload_model() after retraining to pick up the new artifact."""
    global _MODEL_CACHE, _MODEL_CACHE_LOADED
    if _MODEL_CACHE_LOADED:
        return _MODEL_CACHE
    if os.path.exists(MODEL_PATH):
        import joblib
        _MODEL_CACHE = joblib.load(MODEL_PATH)
    _MODEL_CACHE_LOADED = True
    return _MODEL_CACHE


def reload_model():
    """Drop the in-process cache so the next load_model() call re-reads
    MODEL_PATH from disk - call this right after a retrain so the running
    server starts serving the new artifact immediately, with no restart."""
    global _MODEL_CACHE, _MODEL_CACHE_LOADED
    _MODEL_CACHE = None
    _MODEL_CACHE_LOADED = False


def _perf_signal(features):
    """Same signal scout_engine._perf_signal reads (league-neutral z-score
    aggregate, then composite), duplicated here so predict.py has no
    dependency on backend/ - only used by the heuristic fallback below."""
    for key in ('zscore_comp', 'composite_index'):
        v = features.get(key)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return float(v)
    return None


def _heuristic_fallback(player_features):
    """Raw row values come from the source CSV as text (e.g. minutes as
    '1,717'), parsed via safe_float (the codebase's comma-tolerant guard)
    rather than a bare float(), which raises on the comma."""
    row = player_features
    pr = safe_float(row.get('power_rating', 50)) or 50
    age = safe_float(row.get('age', 25)) or 25
    pos = str(row.get('primary_position', row.get('position', 'MF')))
    league = str(row.get('league', ''))
    minutes = safe_float(row.get('minutes', 0))
    games = safe_float(row.get('games', 0))
    return calculate_player_market_value(pr, age, pos, league, minutes, games,
                                          performance=_perf_signal(row))


def predict(player_features, prior_mv=None, prior_mv_2=None):
    """Predicted market value (EUR) for one player-season row. Uses the
    trained GBM when an artifact exists AND a real prior_mv is given (the
    model predicts log(current_mv/prior_mv)), else the heuristic fallback."""
    if not prior_mv or prior_mv <= 0:
        return _heuristic_fallback(player_features)

    bundle = load_model()
    if bundle is None:
        return _heuristic_fallback(player_features)

    model = bundle['model'] # Load the trained model
    cols = bundle.get('feature_cols') or [] # Get the features
    feat = build_features(player_features, prior_mv=prior_mv, prior_mv_2=prior_mv_2) # Build the input features
    try:
        # Predict the expected log change in market value
        pred_growth = float(model.predict([[feat.get(c, 0) for c in cols]])[0])
        # Convert the predicted growth back into an actual market value
        pred = float(prior_mv) * float(np.exp(pred_growth))
    except Exception:
        return _heuristic_fallback(player_features)

    return max(config.MV_PREDICTION_MIN, min(config.MV_PREDICTION_MAX, pred))


if __name__ == '__main__':
    # Smoke-test WITH a prior_mv - the GBM can't be exercised without one,
    # so omitting it here would silently only test the heuristic fallback path.
    sample = {
        'power_rating': 88, 'age': 25, 'primary_position': 'FW', 'league': 'premier-league',
        'minutes': 2500, 'games': 30, 'goals_per90': 0.55, 'assists_per90': 0.2,
        'npxg_per90': 0.5, 'xg_assist_per90': 0.25, 'sca_per90': 3.5,
    }
    print(f"model loaded: {load_model() is not None}")
    print(f"predicted market value (with prior_mv=40M): {predict(sample, prior_mv=40_000_000):,.0f}")
    print(f"predicted market value (no prior_mv, heuristic fallback): {predict(sample):,.0f}")
