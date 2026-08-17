#!/usr/bin/env python3
"""
Squad profile: aggregates one team's roster into a diagnostic snapshot -
position depth, age curve, contract cliff, style diversity, wage-vs-
output. Read-only; never recommends a replacement or ranks candidates.
"""

import os
import sys

import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config

ALL_POSITIONS = ('GK', 'DF', 'MF', 'FW')


def _position_depth(roster_df):
    """Count + composite-index distribution per position. Flags "thin"
    positions (fewer rostered players than config.SQUAD_PROFILE_MIN_DEPTH) -
    a depth gap, not a quality judgement."""
    out = []
    for pos in ALL_POSITIONS:
        sub = roster_df[roster_df['primary_position'] == pos]
        count = int(len(sub))
        composites = sub['composite_index'].dropna()
        best_player = None
        best_composite = None
        if len(composites) > 0:
            best_idx = composites.idxmax()
            best_composite = round(float(composites.loc[best_idx]), 1)
            best_player = str(sub.loc[best_idx, 'player'])
        out.append({
            'position': pos,
            'count': count,
            'avg_composite': round(float(composites.mean()), 1) if len(composites) > 0 else None,
            'best_composite': best_composite,
            'best_player': best_player,
            'is_thin': count < config.SQUAD_PROFILE_MIN_DEPTH,
        })
    return out


def _age_curve(roster_df):
    """Age distribution per position. Flags a position "top-heavy" when a
    strict majority are at/above config.SQUAD_PROFILE_AGING_THRESHOLD.
    Ages <= 0 are excluded, not treated as age zero."""
    out = []
    for pos in ALL_POSITIONS:
        sub = roster_df[roster_df['primary_position'] == pos]
        count = int(len(sub))
        ages = sub['age'][sub['age'] > 0]
        aging_count = int((ages >= config.SQUAD_PROFILE_AGING_THRESHOLD).sum())
        out.append({
            'position': pos,
            'count': count,
            'avg_age': round(float(ages.mean()), 1) if len(ages) > 0 else None,
            'aging_count': aging_count,
            'is_top_heavy': count > 0 and aging_count * 2 > count,
            'players': [
                {'player': str(row['player']), 'age': round(float(row['age']), 1) if row['age'] > 0 else None}
                for _, row in sub.iterrows()
            ],
        })
    return out


def _contract_cliff(roster_df):
    """Players expiring within config.SQUAD_PROFILE_CONTRACT_CLIFF_LONG_MONTHS,
    ranked composite index first (then minutes) so the highest-impact expiries
    surface first - not just whichever contract happens to end soonest."""
    sub = roster_df[roster_df['contract_months_remaining'].notna()].copy()
    sub = sub[sub['contract_months_remaining'] <= config.SQUAD_PROFILE_CONTRACT_CLIFF_LONG_MONTHS]
    if sub.empty:
        return []
    sub['_composite_sort'] = sub['composite_index'].fillna(-1)
    sub['_minutes_sort'] = sub['minutes'].fillna(0)
    sub = sub.sort_values(['_composite_sort', '_minutes_sort'], ascending=[False, False])

    out = []
    for _, row in sub.iterrows():
        months = int(row['contract_months_remaining'])
        out.append({
            'player': str(row['player']),
            'position': str(row['primary_position']),
            'age': round(float(row['age']), 1) if row['age'] > 0 else None,
            'minutes': round(float(row['minutes']), 0) if pd.notna(row['minutes']) else None,
            'composite_index': round(float(row['composite_index']), 1) if pd.notna(row['composite_index']) else None,
            'contract_expiry': str(row['contract_expiry']) if pd.notna(row.get('contract_expiry')) else None,
            'contract_months_remaining': months,
            'within_short_window': months <= config.SQUAD_PROFILE_CONTRACT_CLIFF_SHORT_MONTHS,
            'within_long_window': months <= config.SQUAD_PROFILE_CONTRACT_CLIFF_LONG_MONTHS,
        })
    return out


def _style_diversity(roster_df, archetype_catalogue, player_archetypes):
    """Per position, how the squad's rostered players break down across
    that position group's trained style archetypes - every archetype
    listed, even at 0. is_style_similar is True when every player landed in the same archetype."""
    out = []
    for pos in ALL_POSITIONS:
        sub = roster_df[roster_df['primary_position'] == pos]
        players = [str(p) for p in sub['player'].tolist()]
        count = len(players)

        catalogue = (archetype_catalogue or {}).get(pos)
        if not catalogue:
            # GK (categorically excluded) or no trained artifact for this
            # position group yet - can't report archetype counts, and
            # nothing to flag either.
            out.append({'position': pos, 'count': count, 'archetypes': [], 'is_style_similar': None})
            continue

        counts = {c['cluster']: 0 for c in catalogue}
        assigned = 0
        for p in players:
            result = (player_archetypes or {}).get(p)
            if result is None:
                continue
            counts[result['cluster']] = counts.get(result['cluster'], 0) + 1
            assigned += 1

        archetypes = [
            {'cluster': c['cluster'], 'label': c['label'], 'count': counts.get(c['cluster'], 0)}
            for c in catalogue
        ]
        max_count = max((a['count'] for a in archetypes), default=0)

        out.append({
            'position': pos,
            'count': count,
            'archetypes': archetypes,
            'is_style_similar': None if assigned < 2 else (max_count == assigned),
        })
    return out


def _wage_output(roster_df):
    """One point per player: composite index vs. wage and value-efficiency
    (backend/scoring/moneyball.py's formula, computed by the caller) - a
    single squad-wide view of who's producing relative to what they cost."""
    out = []
    for _, row in roster_df.iterrows():
        out.append({
            'player': str(row['player']),
            'position': str(row['primary_position']),
            'composite_index': round(float(row['composite_index']), 1) if pd.notna(row.get('composite_index')) else None,
            'weekly_wage_eur': float(row['weekly_wage_eur']) if pd.notna(row.get('weekly_wage_eur')) else None,
            'annual_wage_eur': float(row['annual_wage_eur']) if pd.notna(row.get('annual_wage_eur')) else None,
            'wage_is_estimated': bool(row['wage_is_estimated']) if pd.notna(row.get('wage_is_estimated')) else None,
            'value_efficiency': round(float(row['value_efficiency']), 1) if pd.notna(row.get('value_efficiency')) else None,
        })
    return out


def _high_risk_players(risk_assessments):
    """Players where at least one of backend.scoring.risk's four reasons
    fired, keeping only the triggered reasons - an untriggered reason is
    noise in a squad-wide list."""
    out = []
    for a in risk_assessments or []:
        if not a.get('any_triggered'):
            continue
        out.append({**a, 'reasons': [r for r in a['reasons'] if r['triggered']]})
    return out


def build_squad_profile(roster_df, archetype_catalogue, player_archetypes, risk_assessments=None):
    """roster_df must carry player/primary_position/age/minutes/
    composite_index/contract fields/wage fields, pre-computed by the
    caller. Returns a plain dict with the six diagnostic sections plus their thresholds; purely descriptive."""
    return {
        'roster_size': int(len(roster_df)),
        'position_depth': _position_depth(roster_df),
        'age_curve': _age_curve(roster_df),
        'contract_cliff': _contract_cliff(roster_df),
        'style_diversity': _style_diversity(roster_df, archetype_catalogue, player_archetypes),
        'wage_output': _wage_output(roster_df),
        'high_risk_players': _high_risk_players(risk_assessments),
        'aging_threshold': config.SQUAD_PROFILE_AGING_THRESHOLD,
        'min_depth': config.SQUAD_PROFILE_MIN_DEPTH,
    }
