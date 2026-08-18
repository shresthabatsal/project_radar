#!/usr/bin/env python3
"""GET /meta - dataset coverage (seasons, leagues) and freshness. Used by
the homepage's data-description section and to pick a default season for
the hero search bar, rather than hardcoding either on the frontend."""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter

from data import loader
from data.schemas import LeagueInfo, MetaResponse

router = APIRouter(tags=['meta'])


@router.get('/meta', response_model=MetaResponse)
def get_meta():
    """Seasons and leagues present in the loaded dataset (a subset of
    scout_engine.LEAGUE_MAP), plus the latest last_updated timestamp from
    the wages/contract/market-value table."""
    import scout_engine as eng

    df = loader.load_meta()
    if df.empty:
        return MetaResponse(seasons=[], leagues=[], last_updated=loader.get_last_updated())

    seasons = sorted(df['season'].dropna().unique().tolist(), reverse=True)
    present = set(df['league'].dropna().unique().tolist())

    leagues = [
        LeagueInfo(key=key, label=key.replace('-', ' ').title())
        for key in eng.LEAGUE_MAP.keys()
        if key in present
    ]

    return MetaResponse(seasons=seasons, leagues=leagues, last_updated=loader.get_last_updated())
