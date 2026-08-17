#!/usr/bin/env python3
"""
GET /players (search/browse), GET /players/search (advanced filtering),
and GET /players/{id} (full profile: basic stats, radar, composite index).
"""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from data import loader
from data.schemas import (
    ArchetypeOption, PlayerFiltersResponse, PlayerProfileResponse, PlayerSearchResponse,
    PlayerSearchResult, PlayersListResponse, PlayerSummary,
)
from backend.scoring.composite import build_season_position_table, get_playing_style_categories
from ml.style_clustering import predict as style_predict
from ml.style_clustering.features import POSITION_GROUPS as ARCHETYPE_POSITION_GROUPS
from scripts.run_backtest import ALL_POSITIONS

from ._ids import decode_player_id, encode_player_id

router = APIRouter(tags=['players'])


def _gem_flagger(season):
    """Returns fn(player, team, position, league) -> bool, backed by
    scout_engine.gem_keyset's cache - one gem-detection run per distinct
    position+league on a page, not per row."""
    import scout_engine as eng

    def flag(player, team, position, league):
        try:
            keyset = eng.gem_keyset(season, position, league)
        except Exception:
            return None
        return (loader._norm_key(player), team) in keyset

    return flag


@router.get('/players', response_model=PlayersListResponse)
def list_players(
    season: str,
    league: Optional[str] = None,
    team: Optional[str] = None,
    position: Optional[str] = Query(None, description='Filter by primary position (GK/DF/MF/FW)'),
    name: Optional[str] = Query(None, description='Case-insensitive substring match on player name'),
    min_minutes: Optional[float] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Browse/search players for a season, optionally scoped to one league
    (and, within it, one team), with position/name/minutes filters applied
    after loading - the same pool the rest of the API scores against."""
    if team and league:
        df = loader.load_players(season, league, team)
    elif league:
        df = loader.load_league_data(season, league)
    else:
        df = loader.load_all_leagues_data(season)

    if df.empty:
        return PlayersListResponse(players=[], total=0)

    if position and 'primary_position' in df.columns:
        df = df[df['primary_position'] == position]
    if name:
        df = df[df['player'].astype(str).str.contains(name, case=False, na=False, regex=False)]
    if min_minutes is not None and 'minutes' in df.columns:
        mins = loader._num_series(df['minutes']).fillna(0)
        df = df[mins >= min_minutes]

    total = int(len(df))
    page = df.iloc[offset:offset + limit]

    is_gem = _gem_flagger(season)

    players = []
    for _, row in page.iterrows():
        row_league = str(row.get('league', league or ''))
        row_team = str(row.get('team', team or ''))
        row_player = str(row.get('player', ''))
        row_position = str(row.get('primary_position', row.get('position', '')))
        sec = row.get('secondary_position')
        players.append(PlayerSummary(
            id=encode_player_id(season, row_league, row_team, row_player),
            player=row_player,
            team=row_team,
            league=row_league,
            season=season,
            position=row_position,
            secondary_position=str(sec) if sec is not None and str(sec) not in ('', 'nan', 'None') else None,
            age=loader.parse_age(row.get('age', 0)),
            minutes=loader.safe_float(row.get('minutes', 0)),
            goals=loader.safe_float(row.get('goals', 0)),
            assists=loader.safe_float(row.get('assists', 0)),
            is_gem=is_gem(row_player, row_team, row_position, row_league),
        ))

    return PlayersListResponse(players=players, total=total)


def _distinct(df, col):
    if col not in df.columns:
        return []
    vals = df[col].dropna().astype(str).str.strip()
    vals = vals[~vals.str.lower().isin(('', 'nan', 'none'))]
    return sorted(vals.unique().tolist())


def _archetype_options():
    """Every trained ml.style_clustering archetype across FW/MF/DF (GK has
    none), sourced from the currently-trained artifacts, not a hardcoded
    list. Season/league-independent."""
    options = []
    for pos in ARCHETYPE_POSITION_GROUPS:
        catalogue = style_predict.list_archetypes(pos)
        if not catalogue:
            continue
        options.extend(ArchetypeOption(position=pos, cluster=c['cluster'], label=c['label']) for c in catalogue)
    return options


@router.get('/players/filters', response_model=PlayerFiltersResponse)
def get_player_filters(
    season: Optional[str] = Query(None, description='Scope to one season - recommended, the dataset spans 30+ seasons'),
    league: Optional[str] = Query(None, description='Further scope teams/nationalities to one league (only applied together with season)'),
):
    """Distinct team/nationality/league/position values present in the
    dataset. archetypes (see _archetype_options) comes from the trained
    ml.style_clustering artifacts instead."""
    archetypes = _archetype_options()

    if season and league:
        df = loader.load_league_data(season, league)
    elif season:
        df = loader.load_all_leagues_data(season)
    else:
        df = None

    if df is not None:
        if df.empty:
            return PlayerFiltersResponse(teams=[], nationalities=[], leagues=[], positions=[], archetypes=archetypes)
        return PlayerFiltersResponse(
            teams=_distinct(df, 'team'),
            nationalities=_distinct(df, 'nationality'),
            leagues=_distinct(df, 'league'),
            positions=_distinct(df, 'primary_position') or list(ALL_POSITIONS),
            archetypes=archetypes,
        )

    # No season given - a lightweight whole-dataset query (3 raw columns,
    # skips the per-row position standardisation a full multi-season load
    # would otherwise require).
    wide = loader.load_filter_options()
    if wide.empty:
        return PlayerFiltersResponse(teams=[], nationalities=[], leagues=[], positions=list(ALL_POSITIONS), archetypes=archetypes)
    return PlayerFiltersResponse(
        teams=_distinct(wide, 'team'),
        nationalities=_distinct(wide, 'nationality'),
        leagues=_distinct(wide, 'league'),
        positions=list(ALL_POSITIONS),
        archetypes=archetypes,
    )


def format_eur(value):
    if value is None or value <= 0:
        return None
    if value >= 1_000_000:
        return f"€{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"€{value/1_000:.0f}K"
    return f"€{value:.0f}"


def _apply_range_filter(df, column, min_val, max_val, parser=None):
    """Numeric min/max filter on `column`. A player missing the column
    entirely fails either bound - a range filter that can't be verified
    should exclude, not silently include."""
    if min_val is None and max_val is None:
        return df
    if column not in df.columns:
        return df.iloc[0:0]
    parser = parser or loader.safe_float
    vals = df[column].apply(parser)
    if min_val is not None:
        df = df[vals.fillna(-1) >= min_val]
        vals = vals[df.index]
    if max_val is not None:
        df = df[vals.fillna(float('inf')) <= max_val]
    return df


def _apply_min_filter(df, column, min_val):
    if min_val is None:
        return df
    if column not in df.columns:
        return df.iloc[0:0]
    return df[loader._num_series(df[column]).fillna(0) >= min_val]


@router.get('/players/search', response_model=PlayerSearchResponse)
def search_players(
    season: str,
    position: Optional[str] = Query(None, description='GK/DF/MF/FW'),
    league: Optional[str] = None,
    team: Optional[str] = None,
    age_min: Optional[float] = Query(None, ge=0),
    age_max: Optional[float] = Query(None, ge=0),
    nationality: Optional[str] = Query(None, description='Case-insensitive substring match, e.g. "ENG"'),
    min_minutes: Optional[float] = Query(None, ge=0),
    market_value_min: Optional[float] = Query(None, ge=0, description='market_value_eur floor'),
    market_value_max: Optional[float] = Query(None, ge=0, description='market_value_eur ceiling'),
    wage_min: Optional[float] = Query(None, ge=0, description='annual_wage_eur floor'),
    wage_max: Optional[float] = Query(None, ge=0, description='annual_wage_eur ceiling'),
    contract_expiring_months: Optional[int] = Query(None, ge=0, description='Contract expires within this many months'),
    has_release_clause: Optional[bool] = Query(None),
    min_goals_per90: Optional[float] = Query(None),
    min_assists_per90: Optional[float] = Query(None),
    min_xg_per90: Optional[float] = Query(None),
    min_npxg_per90: Optional[float] = Query(None),
    min_progressive_passes: Optional[float] = Query(None),
    min_tackles: Optional[float] = Query(None),
    min_sca_per90: Optional[float] = Query(None),
    min_gca_per90: Optional[float] = Query(None),
    archetype: Optional[str] = Query(
        None, description='ml.style_clustering archetype label - an exact match against '
                           'one of GET /players/filters\' archetypes[].label. No archetype for GK.'),
    sort: str = Query('composite_index',
                       pattern='^(composite_index|market_value|name)$'),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Advanced, Transfermarkt-style search: every filter combines with AND.
    Composite index is computed per position, over the full pool, BEFORE
    filters narrow it - else a player's composite would shift with unrelated filters."""
    if position and position not in ALL_POSITIONS:
        raise HTTPException(status_code=422, detail=f'position must be one of {ALL_POSITIONS}')

    if team and league:
        df = loader.load_players(season, league, team)
    elif league:
        df = loader.load_league_data(season, league)
    else:
        df = loader.load_all_leagues_data(season)

    if df.empty:
        return PlayerSearchResponse(players=[], total=0, limit=limit, offset=offset)

    df = loader.merge_supplementary(df, season)

    positions_to_score = [position] if position else ALL_POSITIONS
    style_cats = get_playing_style_categories()
    # ml.style_clustering archetype label: computed HERE, per position,
    # against each position's FULL pool, before filters narrow it -
    # narrowing first would compute it against a smaller, filter-dependent pool.
    needs_archetype = archetype is not None
    scored_parts = []
    if 'primary_position' in df.columns:
        for pos in positions_to_score:
            pos_df = df[df['primary_position'] == pos].copy()
            if pos_df.empty:
                continue
            if min_minutes is not None and 'minutes' in pos_df.columns:
                mins = loader._num_series(pos_df['minutes']).fillna(0)
                pos_df = pos_df[mins >= min_minutes].copy()
            if pos_df.empty:
                continue
            pos_scored = build_season_position_table(pos_df, pos, style_cats)
            if needs_archetype and pos != 'GK':
                pos_scored = pos_scored.assign(archetype_label=style_predict.predict_bulk(pos_df, pos, style_cats))
            scored_parts.append(pos_scored)

    if not scored_parts:
        return PlayerSearchResponse(players=[], total=0, limit=limit, offset=offset)

    scored = pd.concat(scored_parts, ignore_index=True)

    scored = _apply_range_filter(scored, 'age', age_min, age_max, parser=loader.parse_age)
    if nationality and 'nationality' in scored.columns:
        scored = scored[scored['nationality'].astype(str).str.contains(nationality, case=False, na=False, regex=False)]
    scored = _apply_range_filter(scored, 'market_value_eur', market_value_min, market_value_max)
    scored = _apply_range_filter(scored, 'annual_wage_eur', wage_min, wage_max)

    if contract_expiring_months is not None:
        months = scored.apply(loader.contract_months_remaining, axis=1)
        scored = scored[months.notna() & (months <= contract_expiring_months)]

    if has_release_clause is not None:
        if 'release_clause_eur' in scored.columns:
            has_clause = scored['release_clause_eur'].apply(loader.safe_float).fillna(0) > 0
            scored = scored[has_clause] if has_release_clause else scored[~has_clause]
        elif has_release_clause:
            scored = scored.iloc[0:0]

    for col, threshold in (
        ('goals_per90', min_goals_per90), ('assists_per90', min_assists_per90),
        ('xg_per90', min_xg_per90), ('npxg_per90', min_npxg_per90),
        ('progressive_passes', min_progressive_passes), ('tackles', min_tackles),
        ('sca_per90', min_sca_per90), ('gca_per90', min_gca_per90),
    ):
        scored = _apply_min_filter(scored, col, threshold)

    if archetype is not None:
        scored = scored[scored['archetype_label'] == archetype] if 'archetype_label' in scored.columns else scored.iloc[0:0]

    total = int(len(scored))

    if sort == 'market_value':
        sort_key = scored['market_value_eur'].apply(loader.safe_float) if 'market_value_eur' in scored.columns else None
        scored = scored.assign(_sort_key=sort_key).sort_values('_sort_key', ascending=False, na_position='last')
    elif sort == 'name':
        scored = scored.sort_values('player', key=lambda s: s.astype(str).str.lower())
    else:
        scored = scored.sort_values('composite_index', ascending=False, na_position='last')

    page = scored.iloc[offset:offset + limit]

    is_gem = _gem_flagger(season)

    results = []
    for _, row in page.iterrows():
        row_league = str(row.get('league', league or ''))
        row_team = str(row.get('team', team or ''))
        row_player = str(row.get('player', ''))
        row_position = str(row.get('primary_position', row.get('position', '')))
        sec = row.get('secondary_position')
        nat = row.get('nationality')
        expiry = row.get('contract_expiry')
        mv_val = loader.safe_float(row.get('market_value_eur'))
        wage_val = loader.safe_float(row.get('annual_wage_eur'))
        clause_val = loader.safe_float(row.get('release_clause_eur'))
        results.append(PlayerSearchResult(
            id=encode_player_id(season, row_league, row_team, row_player),
            player=row_player,
            team=row_team,
            league=row_league,
            season=season,
            position=row_position,
            secondary_position=str(sec) if sec is not None and str(sec) not in ('', 'nan', 'None') else None,
            nationality=str(nat) if nat is not None and str(nat) not in ('', 'nan', 'None') else None,
            age=loader.parse_age(row.get('age', 0)),
            minutes=loader.safe_float(row.get('minutes', 0)),
            goals=loader.safe_float(row.get('goals', 0)),
            assists=loader.safe_float(row.get('assists', 0)),
            composite_index=loader.safe_float(row.get('composite_index')),
            market_value=mv_val,
            market_value_label=format_eur(mv_val),
            wage=wage_val,
            wage_label=format_eur(wage_val),
            contract_expiry=str(expiry) if expiry is not None and str(expiry) not in ('', 'nan', 'None') else None,
            contract_months_remaining=loader.contract_months_remaining(row),
            release_clause=clause_val,
            release_clause_label=format_eur(clause_val),
            archetype_label=(
                str(row['archetype_label'])
                if 'archetype_label' in row.index and pd.notna(row['archetype_label'])
                else None
            ),
            is_gem=is_gem(row_player, row_team, row_position, row_league),
        ))

    return PlayerSearchResponse(players=results, total=total, limit=limit, offset=offset)


@router.get('/players/{id}', response_model=PlayerProfileResponse)
def get_player_profile(id: str):
    """Full profile for one player: basic stats, the style-category radar
    (categories with no measurable data in this league are omitted, not
    shown as a misleading zero), and the composite index breakdown."""
    try:
        season, league, team, player = decode_player_id(id)
    except ValueError:
        raise HTTPException(status_code=404, detail='player not found')

    import scout_engine as eng

    result = eng.cmd_get_player_profile({
        'season': season, 'league': league, 'team': team, 'player': player,
    })
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    if result.get('risk') is not None:
        result['risk']['id'] = id

    return PlayerProfileResponse(id=id, **result)
