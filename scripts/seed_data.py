#!/usr/bin/env python3
"""
Seed the in-memory player-data store from a CSV snapshot in
data/data_files/ (data.loader.boot()) - extracted so it can be run and
checked standalone without starting the API server.
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


def seed_data(data_dir=None, engine_module=None):
    """Load players.csv.gz + supplementary.csv.gz into the store. Returns
    {'player_rows', 'supplementary_rows'}. Raises if the expected CSVs
    aren't found, rather than silently booting an empty store."""
    if data_dir is not None:
        original = loader.DATA_DIR
        loader.DATA_DIR = data_dir
        try:
            loader.boot(engine_module=engine_module)
        finally:
            loader.DATA_DIR = original
    else:
        loader.boot(engine_module=engine_module)

    counts = {
        'player_rows': loader.count_rows('league_season_team_player_data'),
        'supplementary_rows': loader.count_rows('player_supplementary_data'),
    }
    if counts['player_rows'] == 0 or counts['supplementary_rows'] == 0:
        raise RuntimeError(
            f"Seed produced an empty store ({counts}) - check that "
            f"players.csv.gz and supplementary.csv.gz exist in "
            f"{data_dir or loader.DATA_DIR}."
        )
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--data-dir', default=None,
                         help='Override the snapshot directory (default: data/data_files/)')
    args = parser.parse_args()

    counts = seed_data(data_dir=args.data_dir)
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
