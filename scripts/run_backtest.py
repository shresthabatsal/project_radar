#!/usr/bin/env python3
"""
Backtest the hidden-gem detector across multiple seasons and positions in
one run - loops backend/scout_engine.py's cmd_backtest_gems over every
available (flag_season, flag_season+horizon) pair and position, then aggregates.
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

ALL_POSITIONS = ['GK', 'DF', 'MF', 'FW']


def _available_seasons(league=None):
    """Distinct seasons on file, oldest first."""
    meta = loader.load_meta()
    if meta.empty:
        return []
    if league:
        meta = meta[meta['league'] == league]
    return sorted(meta['season'].unique().tolist(), key=lambda s: int(str(s).split('-')[0]))


def _season_pairs(seasons, horizon):
    """(flag_season, outcome_season) for every flag_season whose
    flag_season + horizon outcome season is ALSO on file."""
    by_start = {int(str(s).split('-')[0]): s for s in seasons}
    pairs = []
    for start, flag_season in sorted(by_start.items()):
        outcome_start = start + horizon
        if outcome_start in by_start:
            pairs.append((flag_season, by_start[outcome_start]))
    return pairs


def _pool_summaries(runs):
    """Pool the per-run group stats (weighted by n) into one overall summary
    per group, so a run with more flagged gems counts proportionally more."""
    pooled = {}
    for group in ('riser', 'flagged_non_riser', 'baseline'):
        deltas, mins, goods, ns = [], [], [], []
        for run in runs:
            g = run['result'].get(group, {})
            n = g.get('n', 0)
            if n:
                ns.append(n)
                # Re-derive: the underlying per-run values aren't returned
                # by cmd_backtest_gems (only summary stats are) - weight
                # the summary stats themselves by n as the best available pooling.
                deltas.append((g['median_score_delta'], n))
                mins.append((g['median_minutes_delta'], n))
                goods.append((g['pct_stayed_good'], n))
        total_n = sum(ns)
        if not total_n:
            pooled[group] = {'n': 0}
            continue
        pooled[group] = {
            'n': total_n,
            'weighted_median_score_delta': round(sum(v * n for v, n in deltas) / total_n, 1),
            'weighted_pct_stayed_good': round(sum(v * n for v, n in goods) / total_n, 1),
            'weighted_median_minutes_delta': round(sum(v * n for v, n in mins) / total_n),
        }
    return pooled


def run_backtest(seasons=None, positions=None, horizon=1, league=None, engine_module=None):
    """Backtest cmd_get_hidden_gems across every available season pair and
    the given positions. Returns {'runs': [...], 'pooled': {...},
    'n_runs': int, 'n_skipped': int}."""
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot(engine_module=engine_module)

    import scout_engine as eng

    positions = positions or ALL_POSITIONS
    available = _available_seasons(league=league)
    if seasons:
        pairs = [(s, o) for s, o in _season_pairs(available, horizon) if s in seasons]
    else:
        pairs = _season_pairs(available, horizon)

    if not pairs:
        return {'error': f'no season pair with a {horizon}-season-later outcome available',
                'available_seasons': available, 'runs': [], 'pooled': {}, 'n_runs': 0, 'n_skipped': 0}

    runs = []
    skipped = []
    for flag_season, outcome_season in pairs:
        for position in positions:
            req = {'season': flag_season, 'position': position, 'horizon': horizon}
            if league:
                req['league'] = league
            result = eng.cmd_backtest_gems(req)
            if 'error' in result:
                skipped.append({'season': flag_season, 'position': position, 'error': result['error']})
                continue
            runs.append({'season': flag_season, 'outcome_season': outcome_season,
                          'position': position, 'result': result})

    return {
        'seasons_tested': sorted({r['season'] for r in runs}),
        'positions_tested': sorted({r['position'] for r in runs}),
        'horizon': horizon,
        'league': league or 'all',
        'n_runs': len(runs),
        'n_skipped': len(skipped),
        'skipped': skipped,
        'runs': runs,
        'pooled': _pool_summaries(runs),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--season', nargs='+', default=None, dest='seasons',
                         help='Flag season(s) to test, e.g. --season 2023-2024 (default: all available)')
    parser.add_argument('--position', nargs='+', default=None, dest='positions',
                         choices=ALL_POSITIONS, help='Position(s) to test (default: all four)')
    parser.add_argument('--horizon', type=int, default=1, help='Seasons ahead to check outcomes (default: 1)')
    parser.add_argument('--league', default=None, help='Restrict to one league (default: all leagues pooled)')
    args = parser.parse_args()

    report = run_backtest(seasons=args.seasons, positions=args.positions,
                           horizon=args.horizon, league=args.league)
    print(json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    main()
