#!/usr/bin/env python3
"""GET /gems - hidden-gem detection, browsable and filterable by position/league."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from data.schemas import GemsResponse, GemResult

from ._ids import encode_player_id

router = APIRouter(tags=['gems'])


@router.get('/gems', response_model=GemsResponse)
def list_gems(
    season: str,
    position: str = Query('MF', description='GK/DF/MF/FW'),
    league: Optional[str] = None,
    leagues: Optional[List[str]] = Query(None, description='Multiple league slugs (overrides league)'),
    use_trajectory: bool = Query(True, description='Include the Riser (Method 7) trajectory signal'),
    mv_ceiling: Optional[float] = Query(None, description='Market value at/above which a player cannot be "hidden" (default 40M)'),
):
    """Players flagged by >=2 of the 7 hidden-gem detection methods
    (backend/scoring/gems.py) who also show a value/upside signal and
    aren't already priced like a star. Sorted by moneyball score."""
    import scout_engine as eng

    req = {'season': season, 'position': position, 'use_trajectory': use_trajectory}
    if leagues:
        req['leagues'] = leagues
    elif league:
        req['league'] = league
    if mv_ceiling is not None:
        req['mv_ceiling'] = mv_ceiling

    result = eng.cmd_get_hidden_gems(req)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])

    gems = []
    for g in result.get('gems', []):
        gem_id = encode_player_id(season, str(g.get('league', '')), str(g.get('team', '')), str(g.get('player', '')))
        gems.append(GemResult(id=gem_id, **g))

    return GemsResponse(
        gems=gems,
        total=result.get('total', 0),
        min_minutes=result.get('min_minutes'),
        season=result.get('season', season),
        mv_method=result.get('mv_method'),
    )
