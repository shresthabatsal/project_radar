#!/usr/bin/env python3
"""GET /players/{id}/history - career history across every season on file
for this player, with composite index recomputed in each season's own
league context."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException

from data.schemas import CareerHistoryResponse

from ._ids import decode_player_id, encode_player_id

router = APIRouter(tags=['history'])


@router.get('/players/{id}/history', response_model=CareerHistoryResponse)
def get_career_history(id: str):
    """Every season+team row on file for this player's name, composite
    index recomputed against each season's own league/position pool. The
    id's season/league/team only resolve which player."""
    try:
        _season, _league, _team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_career_history({'player': player})
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    # Each season's own id, derived here (not in the pure scoring layer) -
    # lets a caller (the profile page's season switcher) navigate straight
    # to /players/{id} for any season in this player's history.
    for entry in result.get('history', []):
        entry['id'] = encode_player_id(entry['season'], entry['league'], entry['team'], player)

    return CareerHistoryResponse(**result)
