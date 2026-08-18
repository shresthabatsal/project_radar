#!/usr/bin/env python3
"""
Weight sensitivity check for the composite index and moneyball blend:
perturbs each weight by roughly +/-20% one at a time and reports rank
stability (Spearman, top-N overlap, mean abs rank change) vs. nominal.
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
from scipy import stats

import config
from data import loader
from data.loader import _num_series
from backend.scoring import composite, moneyball

ALL_POSITIONS = ['GK', 'DF', 'MF', 'FW']


@contextmanager
def _override_config(**kwargs):
    """Temporarily set attributes on the live config module, restoring the
    originals afterwards even on exception - never leaves the real config
    permanently perturbed."""
    originals = {k: getattr(config, k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            setattr(config, k, v)
        yield
    finally:
        for k, v in originals.items():
            setattr(config, k, v)


def _one_at_a_time_scenarios(names, nominal, pct):
    """('nominal', dict) then, for each weight, +pct/-pct with the trio
    renormalised back to sum to 1."""
    yield ('nominal', dict(zip(names, nominal)))
    for i, name in enumerate(names):
        for label, mult in ((f'+{int(pct*100)}%', 1 + pct), (f'-{int(pct*100)}%', 1 - pct)):
            w = list(nominal)
            w[i] = w[i] * mult
            total = sum(w)
            w = [x / total for x in w]
            yield (f'{name}{label}', dict(zip(names, w)))


def _rank_stability(baseline, perturbed, top_n):
    """Spearman correlation, top-N overlap %, and mean absolute rank change
    between two same-length, same-index Series of scores (higher=better)."""
    base_rank = baseline.rank(ascending=False, method='min')
    pert_rank = perturbed.rank(ascending=False, method='min')
    corr, _ = stats.spearmanr(base_rank, pert_rank)
    base_top = set(base_rank[base_rank <= top_n].index)
    pert_top = set(pert_rank[pert_rank <= top_n].index)
    overlap_pct = 100.0 * len(base_top & pert_top) / max(len(base_top), 1)
    mean_abs_change = float((base_rank - pert_rank).abs().mean())
    return {
        'spearman': round(float(corr), 4) if corr is not None else None,
        'top_n_overlap_pct': round(overlap_pct, 1),
        'mean_abs_rank_change': round(mean_abs_change, 2),
    }


def run_sensitivity(season, position, league=None, pct=0.20, top_n=10, min_minutes=450, engine_module=None):
    """Composite-weight and moneyball-weight rank-stability report for one
    (season, position[, league]) pool. Returns {'pool_size',
    'composite_sensitivity', 'moneyball_sensitivity'} or {'error': ...}."""
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot(engine_module=engine_module)

    import scout_engine as eng

    df = loader.load_league_data(season, league) if league else loader.load_all_leagues_data(season)
    if df.empty:
        return {'error': f"no data for season={season!r}" + (f" league={league!r}" if league else '')}
    df = loader.merge_supplementary(df, season)
    pos_df = df[df['primary_position'] == position].copy() if 'primary_position' in df.columns else df.copy()
    if 'minutes' in pos_df.columns:
        mins = _num_series(pos_df['minutes']).fillna(0)
        pos_df = pos_df[mins >= min_minutes].copy()
    pos_df = pos_df.reset_index(drop=True)
    if len(pos_df) < top_n + 5:
        return {'error': f'pool too small ({len(pos_df)} players with >= {min_minutes} minutes) '
                          f'for a meaningful sensitivity check'}

    style_cats = composite.get_playing_style_categories()

    # ---- Composite weight sensitivity ----
    composite_results = []
    baseline_composite = None
    for label, w in _one_at_a_time_scenarios(('zscore', 'style', 'power'),
                                              (config.COMPOSITE_ZSCORE_WEIGHT, config.COMPOSITE_STYLE_WEIGHT,
                                               config.COMPOSITE_POWER_WEIGHT), pct):
        with _override_config(COMPOSITE_ZSCORE_WEIGHT=w['zscore'], COMPOSITE_STYLE_WEIGHT=w['style'],
                               COMPOSITE_POWER_WEIGHT=w['power']):
            scored = composite.calculate_composite_index(pos_df, position, style_cats)
        series = scored['composite_index']
        if label == 'nominal':
            baseline_composite = series
            composite_results.append({'scenario': label, 'weights': w, 'spearman': 1.0,
                                       'top_n_overlap_pct': 100.0, 'mean_abs_rank_change': 0.0})
        else:
            composite_results.append({'scenario': label, 'weights': w,
                                       **_rank_stability(baseline_composite, series, top_n)})

    # ---- Moneyball weight sensitivity ----
    # Composite/value-efficiency/contract-opportunity held at nominal
    # values - only the moneyball blend weights vary, isolating this from the composite check above.
    nominal_scored = composite.calculate_composite_index(pos_df, position, style_cats)
    wages = nominal_scored.apply(lambda row: eng.get_wage_value(row.to_dict())[0], axis=1)
    mb_inputs = []
    for _, row in nominal_scored.iterrows():
        comp = row['composite_index']
        wage, wage_est = eng.get_wage_value(row.to_dict())
        wage_pctl = stats.percentileofscore(wages.dropna(), wage, kind='rank') if len(wages) > 1 else 50
        value_ratio = (comp / max(wage_pctl, 1)) * config.VALUE_RATIO_SCALE
        value_eff = min(100, value_ratio) if not wage_est else 50.0
        contract_score = moneyball.calculate_contract_opportunity_score(row.to_dict())
        mb_inputs.append((comp, value_eff, contract_score))

    moneyball_results = []
    baseline_mb = None
    for label, w in _one_at_a_time_scenarios(
            ('performance', 'value_efficiency', 'contract'),
            (config.MONEYBALL_PERFORMANCE_WEIGHT, config.MONEYBALL_VALUE_EFFICIENCY_WEIGHT,
             config.MONEYBALL_CONTRACT_WEIGHT), pct):
        with _override_config(MONEYBALL_PERFORMANCE_WEIGHT=w['performance'],
                               MONEYBALL_VALUE_EFFICIENCY_WEIGHT=w['value_efficiency'],
                               MONEYBALL_CONTRACT_WEIGHT=w['contract']):
            scores = [moneyball.calculate_moneyball(c, v, ct) for c, v, ct in mb_inputs]
        series = pd.Series(scores, index=nominal_scored.index)
        if label == 'nominal':
            baseline_mb = series
            moneyball_results.append({'scenario': label, 'weights': w, 'spearman': 1.0,
                                       'top_n_overlap_pct': 100.0, 'mean_abs_rank_change': 0.0})
        else:
            moneyball_results.append({'scenario': label, 'weights': w,
                                       **_rank_stability(baseline_mb, series, top_n)})

    return {
        'season': season,
        'league': league or 'all',
        'position': position,
        'pool_size': len(pos_df),
        'min_minutes': min_minutes,
        'perturbation_pct': pct,
        'top_n': top_n,
        'composite_sensitivity': composite_results,
        'moneyball_sensitivity': moneyball_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--season', required=True, help='Season to test, e.g. 2025-2026')
    parser.add_argument('--position', required=True, choices=ALL_POSITIONS)
    parser.add_argument('--league', default=None, help='Restrict to one league (default: all leagues pooled)')
    parser.add_argument('--pct', type=float, default=0.20, help='Perturbation fraction (default: 0.20 = +/-20%%)')
    parser.add_argument('--top-n', type=int, default=10, dest='top_n', help='Top-N for the overlap metric (default: 10)')
    parser.add_argument('--min-minutes', type=int, default=450, dest='min_minutes',
                         help='Minutes floor for the comparison pool (default: 450)')
    args = parser.parse_args()

    report = run_sensitivity(args.season, args.position, league=args.league, pct=args.pct,
                              top_n=args.top_n, min_minutes=args.min_minutes)
    print(json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    main()
