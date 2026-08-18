#!/usr/bin/env python3
"""
Retrain the style-archetype K-means clusters (FW/MF/DF) and write fresh
artifacts to ml/artifacts/. IMPORTANT: unsupervised - no accuracy to
report; validate with a manual face-validity spot check (ml.style_clustering.predict.predict()), don't present labels as validated.
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
from backend import config
from ml.style_clustering import train as style_train


def retrain_style_clusters(seasons=None, min_minutes=None, k_range=None):
    """(Re)train the FW/MF/DF style-cluster K-means models, persist to
    ml/artifacts/style_clusters_<pos>.joblib. Returns {position:
    meta_dict}, each training metadata or {'error': ...}."""
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot()
    kwargs = {}
    if seasons:
        kwargs['seasons'] = tuple(seasons)
    if min_minutes is not None:
        kwargs['min_minutes'] = min_minutes
    if k_range is not None:
        kwargs['k_range'] = tuple(k_range)
    return style_train.train_style_clusters(**kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--seasons', nargs='+', default=None,
                         help='Seasons to train on, e.g. --seasons 2023-2024 2022-2023 '
                              '(default: every season on file)')
    parser.add_argument('--min-minutes', type=int, default=None,
                         help=f'Minimum minutes for a player-season to count '
                              f'(default: {config.STYLE_CLUSTER_MIN_MINUTES})')
    k_default = list(config.STYLE_CLUSTER_K_RANGE)
    parser.add_argument('--k-min', type=int, default=None,
                         help=f'Smallest K to try (default: {k_default[0]})')
    parser.add_argument('--k-max', type=int, default=None,
                         help=f'Largest K to try (default: {k_default[-1]})')
    args = parser.parse_args()

    k_range = None
    if args.k_min is not None or args.k_max is not None:
        k_min = args.k_min if args.k_min is not None else k_default[0]
        k_max = args.k_max if args.k_max is not None else k_default[-1]
        k_range = range(k_min, k_max + 1)

    result = retrain_style_clusters(seasons=args.seasons, min_minutes=args.min_minutes, k_range=k_range)
    print(json.dumps(result, indent=2, default=str))
    if isinstance(result, dict):
        if 'error' in result or any(isinstance(v, dict) and 'error' in v for v in result.values()):
            sys.exit(1)


if __name__ == '__main__':
    main()
