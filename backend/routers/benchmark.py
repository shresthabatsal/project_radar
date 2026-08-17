#!/usr/bin/env python3
"""GET /players/{id}/benchmark - league_average, the league-best player's
own radar, category leaders, and metric leaders (the "vs the league's
best" table)."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException

from data.schemas import PositionBenchmarkResponse

from ._ids import decode_player_id, encode_player_id

router = APIRouter(tags=['benchmark'])


@router.get('/players/{id}/benchmark', response_model=PositionBenchmarkResponse)
def get_position_benchmark(id: str):
    """Per-metric league leaders, per-category leaders, and the league's
    standout performer's own radar, for this player's season/league/position
    pool (backend/scoring/benchmark.py)."""
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_position_benchmark({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    # Every leader's own id is derived here, not in the pure scoring layer -
    # encode_player_id is a router/API concern (see backend/routers/_ids.py).
    best = result.get('best')
    if best and best.get('player') and best.get('team'):
        best['player_id'] = encode_player_id(season, league, best['team'], best['player'])

    for entry in result.get('metric_leaders', []):
        leader_team = entry.pop('best_player_team', None)
        entry['best_player_id'] = (
            encode_player_id(season, league, leader_team, entry['best_player'])
            if leader_team and entry.get('best_player') else None
        )

    for entry in result.get('category_leaders', []):
        if entry.get('player') and entry.get('team'):
            entry['player_id'] = encode_player_id(season, league, entry['team'], entry['player'])

    return PositionBenchmarkResponse(**result)
