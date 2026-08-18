#!/usr/bin/env python3
"""
Retrain the market-value GBM and write a fresh artifact to ml/artifacts/.
Thin CLI wrapper around ml.market_value.train.train_mv_models() - run
`python scripts/retrain_market_value.py` or import retrain_market_value().
"""

import argparse
import json
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data import loader
from ml.market_value import train as mv_train


def retrain_market_value(seasons=None):
    """(Re)train the market-value GBM, persist to ml/artifacts/mv_gbm.joblib.
    seasons defaults to auto-detected real-labeled seasons. Returns the
    training metadata dict, or {'error': ...}."""
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot()
    if seasons:
        return mv_train.train_mv_models(tuple(seasons))
    return mv_train.train_mv_models()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--seasons', nargs='+', default=None,
                         help='Seasons to train on, e.g. --seasons 2025-2026 2024-2025 '
                              '(default: auto-detect every season with real market_value_eur data)')
    args = parser.parse_args()

    meta = retrain_market_value(seasons=args.seasons)
    print(json.dumps(meta, indent=2))
    if isinstance(meta, dict) and 'error' in meta:
        sys.exit(1)


if __name__ == '__main__':
    main()
