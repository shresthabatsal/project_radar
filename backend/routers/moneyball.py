#!/usr/bin/env python3
"""GET /players/{id}/moneyball - performance + value-efficiency + contract-opportunity blend."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException

from data.schemas import MoneyballScore

from ._ids import decode_player_id

router = APIRouter(tags=['moneyball'])


@router.get('/players/{id}/moneyball', response_model=MoneyballScore)
def get_moneyball_score(id: str):
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_moneyball_score({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    return MoneyballScore(**result)
