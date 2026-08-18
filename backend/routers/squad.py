#!/usr/bin/env python3
"""
GET /teams/{team}/squad-profile: a read-only diagnostic snapshot of one
team's roster (position depth, age curve, contract cliff, style
diversity, wage-vs-output) - never recommends a replacement or ranks candidates.
"""

import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
from scipy import stats
from fastapi import APIRouter, HTTPException, Query

import config
from data import loader
from data.schemas import SquadProfileResponse
from backend.scoring.composite import (
    build_season_position_table, calculate_category_scores, get_playing_style_categories,
)
from backend.scoring.squad_profile import build_squad_profile, ALL_POSITIONS
from backend.scoring.risk import assess_player_risk
from ml.style_clustering import predict as style_predict
from ._ids import encode_player_id

router = APIRouter(tags=['squad'])


@router.get('/teams/{team}/squad-profile', response_model=SquadProfileResponse)
def get_squad_profile(
    team: str,
    season: str = Query(...),
    league: str = Query(...),
):
    import scout_engine as eng  # get_wage_value - same wage estimate cmd_get_moneyball_score uses

    roster = loader.load_players(season, league, team)
    if roster.empty:
        raise HTTPException(status_code=404, detail=f'No roster found for {team} in {league} {season}')
    roster = loader.merge_supplementary(roster, season)

    league_df = loader.load_league_data(season, league)
    league_df = loader.merge_supplementary(league_df, season)

    style_cats = get_playing_style_categories()
    category_scores = {}
    scored_parts = []
    risk_assessments = []
    # ml.style_clustering: archetype_catalogue is every trained archetype
    # per position group (GK stays None), fetched once per position.
    # player_archetypes is each rostered player's own nearest-cluster assignment.
    archetype_catalogue = {}
    player_archetypes = {}

    for pos in ALL_POSITIONS:
        pos_roster = roster[roster['primary_position'] == pos].copy() if 'primary_position' in roster.columns else roster.iloc[0:0].copy()
        if pos_roster.empty:
            continue

        archetype_catalogue[pos] = style_predict.list_archetypes(pos)

        pos_league_df = league_df[league_df['primary_position'] == pos].copy() if 'primary_position' in league_df.columns else league_df.copy()
        # build_season_position_table (not the bare calculate_composite_index)
        # for composite_index itself - same pool-scoring function GET
        # /players/search uses to score its own composite-index sort.
        pos_league_scored = (
            build_season_position_table(pos_league_df, pos, style_cats)
            if len(pos_league_df) > 1 else pos_league_df.assign(composite_index=None)
        )

        # Wage distribution for the whole league position pool - computed
        # once per position (not per roster player) so this stays O(league
        # pool size), not O(roster size x league pool size).
        wages_series = (
            pos_league_df.apply(lambda r: eng.get_wage_value(r.to_dict())[0], axis=1)
            if not pos_league_df.empty else pd.Series(dtype=float)
        )

        rows = []
        for _, prow in pos_roster.iterrows():
            player_name = str(prow['player'])

            crow = pos_league_scored[(pos_league_scored['player'] == player_name) & (pos_league_scored['team'] == team)]
            if crow.empty:
                crow = pos_league_scored[pos_league_scored['player'] == player_name]
            c0 = crow.iloc[0] if not crow.empty else None
            composite = loader.safe_float(c0.get('composite_index')) if c0 is not None and pd.notna(c0.get('composite_index')) else None

            # Style-category percentile vector, scored against the full
            # league position pool - same function the profile radar uses.
            category_scores[player_name] = calculate_category_scores(
                prow, pos_league_df, style_cats, pos, method='percentile', empty_as_none=True,
            )
            # Nearest archetype from that same category-score vector - GK
            # is categorically excluded rather than forced into an
            # outfield archetype.
            player_archetypes[player_name] = (
                style_predict.predict(category_scores[player_name], pos, style_cats) if pos != 'GK' else None
            )

            row_dict = prow.to_dict()
            wage, wage_est = eng.get_wage_value(row_dict)
            wage_pctl = max(stats.percentileofscore(wages_series.dropna(), wage, kind='rank'), 1) if len(wages_series) else 50.0
            # Value efficiency = (performance / wage percentile) x scale,
            # capped 0-100 - identical formula to cmd_get_moneyball_score.
            # An estimated wage neutralizes to 50.
            composite_for_eff = composite if composite is not None else 50.0
            value_ratio_raw = (composite_for_eff / wage_pctl) * config.VALUE_RATIO_SCALE
            value_eff = 50.0 if wage_est else min(100, max(0, value_ratio_raw))

            row_dict['composite_index'] = composite
            row_dict['age'] = loader.parse_age(prow.get('age', 0))
            row_dict['minutes'] = loader.safe_float(prow.get('minutes', 0))
            row_dict['annual_wage_eur'] = loader.safe_float(row_dict.get('annual_wage_eur', 0)) or None
            row_dict['contract_months_remaining'] = loader.contract_months_remaining(row_dict)
            row_dict['weekly_wage_eur'] = wage
            row_dict['wage_is_estimated'] = wage_est
            row_dict['value_efficiency'] = value_eff
            rows.append(row_dict)

            # Career-accumulated minutes + this player's prior-season row
            # (needed by sell_high_risk's deterioration model) - one
            # history load covers both.
            history = loader.load_player_history(player_name)
            career_minutes = None
            prior_row = None
            if not history.empty and 'minutes' in history.columns:
                career_minutes = float(loader._num_series(history['minutes']).fillna(0).sum())
                prior_season = loader.prev_season_label(season)
                if prior_season:
                    prow_prior = history[history['season'].astype(str) == str(prior_season)]
                    if not prow_prior.empty:
                        prior_row = prow_prior.iloc[0].to_dict()

            risk_assessments.append(assess_player_risk(
                row_dict, player_name, season, pos, style_cats, category_scores[player_name],
                career_minutes=career_minutes, prior_row=prior_row, history=history,
            ))

        scored_parts.append(pd.DataFrame(rows))

    if not scored_parts:
        raise HTTPException(status_code=404, detail=f'No scoreable players found for {team} in {league} {season}')

    roster_scored = pd.concat(scored_parts, ignore_index=True)
    profile = build_squad_profile(roster_scored, archetype_catalogue, player_archetypes, risk_assessments=risk_assessments)

    # Every player here is on this same roster, so their id is always
    # (season, league, this team, their name) - derived here since
    # encode_player_id is a router concern.
    for entry in profile['position_depth']:
        if entry.get('best_player'):
            entry['best_player_id'] = encode_player_id(season, league, team, entry['best_player'])
    for entry in profile['age_curve']:
        for p in entry['players']:
            p['id'] = encode_player_id(season, league, team, p['player'])
    for entry in profile['contract_cliff']:
        entry['id'] = encode_player_id(season, league, team, entry['player'])
    for entry in profile['wage_output']:
        entry['id'] = encode_player_id(season, league, team, entry['player'])
    for entry in profile['high_risk_players']:
        entry['id'] = encode_player_id(season, league, team, entry['player'])

    return SquadProfileResponse(team=team, season=season, league=league, **profile)
