#!/usr/bin/env python3
"""
Retrain the sell-high deterioration-probability classifier and write a
fresh artifact to ml/artifacts/. Thin CLI wrapper around
ml.sell_high_risk.train.train_sell_high_model(), mirroring retrain_market_value.py's pattern.
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
from ml.sell_high_risk import train as sell_high_train


def retrain_sell_high_risk(seasons=None):
    """(Re)train the sell-high deterioration classifier, persist to
    ml/artifacts/sell_high_gbm.joblib. seasons defaults to every season on
    file. Returns the training metadata dict, or {'error': ...}."""
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot()
    if seasons:
        return sell_high_train.train_sell_high_model(seasons=tuple(seasons))
    return sell_high_train.train_sell_high_model()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--seasons', nargs='+', default=None,
                         help='Seasons to train on, e.g. --seasons 2025-2026 2024-2025 '
                              '(default: every season on file)')
    args = parser.parse_args()

    meta = retrain_sell_high_risk(seasons=args.seasons)
    print(json.dumps(meta, indent=2))
    if isinstance(meta, dict) and 'error' in meta:
        sys.exit(1)


if __name__ == '__main__':
    main()
