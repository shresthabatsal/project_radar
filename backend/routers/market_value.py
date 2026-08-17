#!/usr/bin/env python3
"""
GET /players/{id}/market-value: headline valuation (verified > GBM >
heuristic), the GBM's own prediction + feature importances, and the
model-vs-market gap when a verified value exists. Thin decode-and-delegate wrapper.
"""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException

from data.schemas import MarketValueResponse

from ._ids import decode_player_id

router = APIRouter(tags=['market_value'])


@router.get('/players/{id}/market-value', response_model=MarketValueResponse)
def get_market_value(id: str):
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_market_value({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    return MarketValueResponse(**result)
