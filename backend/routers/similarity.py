#!/usr/bin/env python3
"""GET /players/{id}/similar - similarity search over 4 selectable distance
methods (backend/scoring/similarity.py), mahalanobis by default.
GET /similarity-methods - the reasoning/"best for" copy behind each method.
"""

import os
import sys
from typing import Optional

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, HTTPException, Query

from data.schemas import (
    SimilarPlayersResponse, SimilarPlayerMatch, SimilarityMethodInfo, SimilarityMethodsResponse,
)
from backend.scoring.similarity import SIMILARITY_METHODS, DEFAULT_SIMILARITY_METHOD

from ._ids import decode_player_id, encode_player_id

router = APIRouter(tags=['similarity'])

_SORT_VALUES = {'match_score', 'composite', 'age', 'market_value'}
_CONTRACT_STATUS_VALUES = {'free', 'expiring', 'clause'}


@router.get('/similarity-methods', response_model=SimilarityMethodsResponse)
def get_similarity_methods():
    """Static reasoning/"best for" copy for each of the 4 distance methods
    GET /players/{id}/similar accepts, sourced from
    backend/scoring/similarity.py's SIMILARITY_METHODS."""
    return SimilarityMethodsResponse(
        methods=[
            SimilarityMethodInfo(key=key, **info) for key, info in SIMILARITY_METHODS.items()
        ],
        default=DEFAULT_SIMILARITY_METHOD,
    )


@router.get('/players/{id}/similar', response_model=SimilarPlayersResponse)
def get_similar_players(
    id: str,
    min_minutes: float = Query(600, ge=0),
    window: int = Query(1, ge=1, le=5, description='Seasons to blend into one minutes-weighted profile (1 = single season)'),
    league: Optional[str] = Query(None, description='Filter candidates to this league'),
    team: Optional[str] = Query(None, description='Filter candidates to this team'),
    age_min: Optional[float] = Query(None, ge=0),
    age_max: Optional[float] = Query(None, ge=0),
    minutes_min: Optional[float] = Query(None, ge=0),
    minutes_max: Optional[float] = Query(None, ge=0),
    contract_status: Optional[str] = Query(None, description='free | expiring | clause'),
    archetype: Optional[str] = Query(
        None,
        description='ml.style_clustering archetype label to filter candidates to - an '
                    'exact match against one of the labels in this response\'s own archetype_options. '
                    'Omit for no filter.',
    ),
    method: str = Query(
        DEFAULT_SIMILARITY_METHOD,
        description=f'Distance method: {" | ".join(sorted(SIMILARITY_METHODS))}. '
                    f'Defaults to {DEFAULT_SIMILARITY_METHOD} - see GET /similarity-methods '
                    f'for the reasoning behind each.',
    ),
    sort: str = Query('match_score', description='match_score | composite | age | market_value'),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Players closest to this one by distance over the position's full raw
    per-90 metric set. `method` picks which of the 4 distance metrics,
    filtered/sorted/paginated over the eligible pool."""
    if sort not in _SORT_VALUES:
        raise HTTPException(status_code=422, detail=f'sort must be one of {sorted(_SORT_VALUES)}')
    if contract_status is not None and contract_status not in _CONTRACT_STATUS_VALUES:
        raise HTTPException(status_code=422, detail=f'contract_status must be one of {sorted(_CONTRACT_STATUS_VALUES)}')
    if method not in SIMILARITY_METHODS:
        raise HTTPException(status_code=422, detail=f'method must be one of {sorted(SIMILARITY_METHODS)}')

    try:
        season, target_league, target_team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_similar_players({
        'season': season, 'league': target_league, 'team': target_team, 'player': player,
        'min_minutes': min_minutes, 'window': window,
        'filter_league': league, 'filter_team': team,
        'age_min': age_min, 'age_max': age_max,
        'minutes_min': minutes_min, 'minutes_max': minutes_max,
        'contract_status': contract_status,
        'archetype': archetype,
        'method': method,
        'sort': sort, 'page': page, 'page_size': page_size,
    })
    if 'error' in result and not result.get('similar'):
        # Some errors are "not found" (bad id), others "no data for this
        # pool" (a valid empty result) - only 404 when the target player
        # itself couldn't be resolved.
        if result['error'].startswith(f'Player {player}'):
            raise HTTPException(status_code=404, detail=result['error'])

    similar = []
    for sp in result.get('similar', []):
        similar.append(SimilarPlayerMatch(
            id=encode_player_id(season, str(sp.get('league', target_league)), str(sp.get('team', '')), str(sp.get('player', ''))),
            **sp,
        ))

    return SimilarPlayersResponse(
        similar=similar,
        total=result.get('total', len(similar)),
        page=result.get('page', page),
        page_size=result.get('page_size', page_size),
        method=result.get('method', DEFAULT_SIMILARITY_METHOD),
        metrics_used=result.get('metrics_used', 0),
        metric_keys=result.get('metric_keys', []),
        metric_groups=result.get('metric_groups', []),
        window=result.get('window', window),
        min_minutes=result.get('min_minutes', min_minutes),
        sort=result.get('sort', sort),
        archetype_options=result.get('archetype_options', []),
        target=result.get('target', {}),
        error=result.get('error'),
    )
