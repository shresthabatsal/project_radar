#!/usr/bin/env python3
"""
GET /players/{id}/style-archetype: nearest-cluster assignment
(ml.style_clustering, one model per broad position group) plus its
generated archetype label/blurb. Thin decode-and-delegate wrapper.
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

from data.schemas import StyleArchetypeResponse

from ._ids import decode_player_id

router = APIRouter(tags=['style_archetype'])


@router.get('/players/{id}/style-archetype', response_model=StyleArchetypeResponse)
def get_style_archetype(id: str):
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_style_archetype({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    return StyleArchetypeResponse(**result)
