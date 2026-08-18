#!/usr/bin/env python3
"""
Explainability for the trained market-value GBM: which features drive its
predictions, and by how much.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml.market_value.predict import load_model


def top_contributors(n=8):
    """The top n features driving the trained GBM's predictions, ranked by
    importance (weight_pct sums to 100 across all features). Returns [] if
    no model has been trained yet."""
    bundle = load_model()
    if bundle is None:
        return []

    model = bundle.get('model')
    cols = bundle.get('feature_cols') or []
    importances = getattr(model, 'feature_importances_', None)
    if importances is None or len(importances) != len(cols):
        return []

    total = float(importances.sum()) or 1.0
    ranked = sorted(zip(cols, importances), key=lambda pair: pair[1], reverse=True)
    return [
        {
            'feature': name,
            'importance': round(float(imp), 6),
            'weight_pct': round(float(imp) / total * 100, 1),
        }
        for name, imp in ranked[:n]
    ]


def prediction_confidence(prior_mv):
    """How much real labeled training data backs a GBM prediction at this
    prior-value level - {'tier', 'n', 'mdape_pct', 'note'}, or None if
    unavailable. Not a correction to the prediction, just a confidence signal."""
    bundle = load_model()
    if bundle is None:
        return None
    brackets = (bundle.get('meta') or {}).get('mdape_pct_by_prior_bracket') or []
    for b in brackets:
        lo, hi = b['anchor_mv_min'], b['anchor_mv_max']
        if prior_mv >= lo and (hi is None or prior_mv < hi):
            tier = b['tier']
            note = {
                'high': f"Backed by {b['n']:,} comparable real transfers in the training data - typically within {b['mdape_pct']:.0f}% of actual value at this level.",
                'medium': f"Backed by {b['n']:,} comparable real transfers - a moderate sample, typically within {b['mdape_pct']:.0f}% of actual value at this level.",
                'low': f"Only {b['n']:,} comparable real transfers this high in the training data - individual predictions at this level can vary substantially (typically within {b['mdape_pct']:.0f}%, but with more spread than lower brackets).",
            }[tier]
            return {'tier': tier, 'n': b['n'], 'mdape_pct': b['mdape_pct'], 'note': note}
    return None


if __name__ == '__main__':
    contributors = top_contributors()
    if not contributors:
        print("No trained model found - run train.py first.")
    else:
        for c in contributors:
            print(f"{c['feature']:<20} {c['weight_pct']:>5.1f}%")
