#!/usr/bin/env python3
"""
Explainability for the trained sell-high deterioration classifier: which
features drive its predictions, and by how much. Same pattern as
ml.market_value.explainability.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml.sell_high_risk.predict import load_model


def top_contributors(n=8):
    """The top n features driving the classifier's predictions, ranked by
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


if __name__ == '__main__':
    contributors = top_contributors()
    if not contributors:
        print("No trained model found - run train.py first.")
    else:
        for c in contributors:
            print(f"{c['feature']:<24} {c['weight_pct']:>5.1f}%")
