#!/usr/bin/env python3
"""GET /players/{id}/raw-data - the player's full raw per-90/per-season
metric set, grouped by their own position's style categories - a plain,
un-scored breakdown, not a new categorization scheme."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException

from data.schemas import RawDataResponse

from ._ids import decode_player_id

router = APIRouter(tags=['raw-data'])


@router.get('/players/{id}/raw-data', response_model=RawDataResponse)
def get_raw_data(id: str):
    """This player-season's own raw metric values, grouped by their
    position's style categories (backend/scout_engine.py's
    cmd_get_raw_data)."""
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_raw_data({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    return RawDataResponse(**result)
