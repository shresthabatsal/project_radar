#!/usr/bin/env python3
"""
Career history across seasons, with composite index recomputed in each
season's own league context - each season computed fresh against that
season's own league/position pool.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import safe_float, parse_age, load_league_data
from backend.scoring.composite import calculate_composite_index


def build_history(df, player_name, style_cats):
    """One record per season+team row (a player's full load_player_history()
    result), with composite_index recomputed against that season's own
    league/position pool."""
    history = []
    for _, row in df.iterrows():
        season = str(row.get('season', ''))
        league = str(row.get('league', ''))
        position = str(row.get('primary_position', row.get('position', 'MF')))
        if position not in ['GK', 'DF', 'MF', 'FW']:
            position = 'MF'

        # Try to compute composite_index for this season/league
        composite = 0
        try:
            league_df = load_league_data(season, league)
            pos_pool = league_df[league_df['primary_position'] == position].copy() if 'primary_position' in league_df.columns else league_df.copy()
            if len(pos_pool) > 1:
                pos_pool = calculate_composite_index(pos_pool, position, style_cats)
                # Match the specific club row, not just the player name - a
                # player can have two rows in one season+league after a
                # mid-season transfer, and .iloc[0] would give both stints the same score.
                team = str(row.get('team', ''))
                p_rows = pos_pool[(pos_pool['player'] == player_name) & (pos_pool['team'] == team)]
                if p_rows.empty:
                    p_rows = pos_pool[pos_pool['player'] == player_name]
                if not p_rows.empty:
                    composite = safe_float(p_rows.iloc[0].get('composite_index', 0))
        except Exception:
            pass

        history.append({
            'season': season,
            'team': str(row.get('team', '')),
            'league': league,
            'position': position,
            'age': parse_age(row.get('age', 0)),
            'games': safe_float(row.get('games', row.get('games_starts', 0))),
            'minutes': safe_float(row.get('minutes', 0)),
            'goals': safe_float(row.get('goals', 0)),
            'assists': safe_float(row.get('assists', 0)),
            'xg': round(safe_float(row.get('xg', 0)), 2),
            'xg_assist': round(safe_float(row.get('xg_assist', 0)), 2),
            'composite': round(composite, 1),
        })
    return history
