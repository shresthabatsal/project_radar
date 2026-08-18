#!/usr/bin/env python3
"""
Sell-high deterioration prediction: loads the trained classifier + its
frozen output_score reference (cached in-process), predicts P(significant
deterioration next season). Returns None when no artifact has been trained yet.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml.sell_high_risk.features import build_features
from ml.sell_high_risk.train import MODEL_PATH

_MODEL_CACHE = None
_MODEL_CACHE_LOADED = False


def load_model():
    """The trained {'model', 'feature_cols', 'reference',
    'decline_threshold_info', 'meta'} bundle, or None if untrained. Cached
    - call reload_model() after retraining."""
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
    MODEL_PATH from disk - call right after a retrain so the running
    server serves the new artifact immediately."""
    global _MODEL_CACHE, _MODEL_CACHE_LOADED
    _MODEL_CACHE = None
    _MODEL_CACHE_LOADED = False


def get_reference():
    """The trained model's frozen output_score reference, or {} if no
    artifact exists - lets callers compute against the exact same frozen
    numbers a training-time row was scored against."""
    bundle = load_model()
    return (bundle or {}).get('reference') or {}


def predict_deterioration_probability(row, position, prior_row=None, prior_row_2=None,
                                       current_mv=None, prior_mv=None, prior_mv_2=None,
                                       peak_mv_to_date=None, output_score_peak_to_date=None):
    """P(significant deterioration next season) in [0, 1], or None if
    untrained. `current_mv`/`prior_mv`/`prior_mv_2`/`peak_mv_to_date` must
    be REAL values, never estimated; `output_score_peak_to_date` must be leakage-safe."""
    bundle = load_model()
    if bundle is None:
        return None

    model = bundle['model']
    cols = bundle.get('feature_cols') or []
    reference = bundle.get('reference') or {}
    feat = build_features(
        row, position, reference, prior_row=prior_row, prior_row_2=prior_row_2,
        current_mv=current_mv, prior_mv=prior_mv, prior_mv_2=prior_mv_2,
        peak_mv_to_date=peak_mv_to_date, output_score_peak_to_date=output_score_peak_to_date,
    )
    try:
        proba = model.predict_proba([[feat.get(c, 0) for c in cols]])[0]
        # Column 1 = P(label == 1) = P(significant deterioration) -
        # classes_ are always [0, 1] since both labels are guaranteed present in training.
        return float(proba[1])
    except Exception:
        return None
