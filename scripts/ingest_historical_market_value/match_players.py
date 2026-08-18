#!/usr/bin/env python3
"""
Step 2 of the historical market-value ingestion pipeline: matches this
project's players to Transfermarkt player_ids via (1) existing
transfermarkt_id passthrough, then (2) a name+birth_year+team-overlap composite match - name alone is never trusted as an identity.
"""

import os
import re
import sys

import pandas as pd

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import _norm_key
from scripts.ingest_historical_market_value.fetch import LEAGUE_TM_MAP

SUPPLEMENTARY_PATH = os.path.join(_PROJECT_ROOT, 'data', 'data_files', 'supplementary.csv.gz')

# Transfermarkt uses full legal club names ("Everton FC"); this project
# uses shorter FBref-style names ("Everton"). _club_core() strips
# boilerplate/founding-year digits so overlap is a substring check, not exact equality.
_CLUB_BOILERPLATE = {
    'fc', 'cf', 'afc', 'sc', 'ac', 'ud', 'ss', 'ssc', 'ogc', 'as', 'ca', 'cd',
    'rc', 'sd', 'sv', 'cp', 'us', 'club', 'calcio', 'futbol', 'football', 'de',
}
_CLUB_ALIASES = {
    'united': 'utd',
    'internazionale': 'inter',
    'paris saint germain': 'psg',
    'atletico': 'atl',
    'athletic': 'ath',
}


def _club_core(name):
    n = _norm_key(name)
    n = re.sub(r'^\d+\.\s*', '', n)      # "1.fc koln" -> "fc koln"
    n = re.sub(r'\b\d{2,4}\b', '', n)    # "sc paderborn 07" -> "sc paderborn"
    for full, short in _CLUB_ALIASES.items():
        n = n.replace(full, short)
    tokens = [t for t in n.split() if t not in _CLUB_BOILERPLATE]
    return ' '.join(tokens).strip()


def _club_cores_overlap(project_teams, tm_clubs):
    project_cores = {_club_core(t) for t in project_teams}
    tm_cores = {_club_core(t) for t in tm_clubs}
    return any(
        len(p) >= 3 and len(t) >= 3 and (p == t or p in t or t in p)
        for p in project_cores for t in tm_cores
    )


def load_project_rows():
    """Every (player, team, season, league, birth_year) row this project
    has on file for the TM-covered leagues - the identity source and
    merge target surface. Reads off the live in-process store; loader.boot() must have run."""
    from data import loader

    leagues = tuple(LEAGUE_TM_MAP.keys())
    placeholders = ','.join('?' for _ in leagues)
    df = pd.read_sql(
        f"SELECT player, team, season, league, birth_year FROM league_season_team_player_data "
        f"WHERE league IN ({placeholders})",
        loader._db, params=leagues,
    )
    df = df.dropna(subset=['player', 'team', 'season', 'league']).copy()
    df['birth_year'] = pd.to_numeric(df['birth_year'], errors='coerce')
    df = df.dropna(subset=['birth_year'])
    df['birth_year'] = df['birth_year'].astype(int)
    df['norm_name'] = df['player'].map(_norm_key)
    df['norm_team'] = df['team'].map(_norm_key)
    return df.drop_duplicates()


def _existing_id_matches(project_rows):
    """Path 1: reuse the transfermarkt_id this project's own supplementary
    data already carries, resolved to a stable (norm_name, birth_year)
    identity by joining back to project_rows."""
    supp = pd.read_csv(SUPPLEMENTARY_PATH)
    supp = supp[supp['transfermarkt_id'].notna()].copy()
    supp['norm_name'] = supp['player'].map(_norm_key)
    supp['norm_team'] = supp['team'].map(_norm_key)
    supp['norm_league'] = supp['league'].map(_norm_key)

    pr = project_rows.copy()
    pr['norm_league'] = pr['league'].map(_norm_key)

    joined = supp.merge(
        pr[['norm_name', 'norm_team', 'norm_league', 'season', 'birth_year']],
        on=['norm_name', 'norm_team', 'norm_league', 'season'], how='inner',
    )
    joined = joined.drop_duplicates(subset=['transfermarkt_id'])
    matches = joined[['transfermarkt_id', 'norm_name', 'birth_year']].rename(
        columns={'transfermarkt_id': 'player_id'})
    matches['player_id'] = matches['player_id'].astype(int)
    matches['method'] = 'existing_id'

    unresolved = int(supp['transfermarkt_id'].nunique() - matches['player_id'].nunique())
    return matches, unresolved


def _composite_matches(project_rows, valuations_df, players_df, already_matched_identities):
    """Path 2 (fallback): name + birth_year + team-overlap composite match
    for every project identity NOT already resolved via an existing id.
    Returns (matches_df, ambiguous_list)."""
    players_df = players_df.copy()
    players_df['norm_name'] = players_df['name'].map(lambda x: _norm_key(x) if isinstance(x, str) else '')
    players_df['birth_year'] = pd.to_datetime(players_df['date_of_birth'], errors='coerce').dt.year
    players_df = players_df.dropna(subset=['birth_year'])
    players_df['birth_year'] = players_df['birth_year'].astype(int)

    # Every club a TM player was ever valued at, not just their current
    # club - so an old project season can still corroborate a player who has since moved on.
    tm_clubs = valuations_df.dropna(subset=['current_club_name']).groupby('player_id')['current_club_name'].apply(set)

    identity_teams = project_rows.groupby(['norm_name', 'birth_year'])['team'].apply(set)

    project_identities = project_rows[['norm_name', 'birth_year']].drop_duplicates()
    candidates = players_df.merge(project_identities, on=['norm_name', 'birth_year'], how='inner')
    if len(candidates):
        idx = pd.MultiIndex.from_frame(candidates[['norm_name', 'birth_year']])
        candidates = candidates[~idx.isin(already_matched_identities)]

    matched_by_identity = {}
    ambiguous = []
    for _, row in candidates.iterrows():
        identity = (row['norm_name'], row['birth_year'])
        pid = int(row['player_id'])
        teams = identity_teams.get(identity, set())
        clubs = tm_clubs.get(pid, set())
        if _club_cores_overlap(teams, clubs):
            matched_by_identity.setdefault(identity, []).append(pid)
        else:
            ambiguous.append({
                'reason': 'no_team_overlap',
                'identity': f"{row['name']} (b.{row['birth_year']})",
                'tm_player_id': pid,
                'tm_clubs_sample': sorted(clubs)[:5],
                'project_teams_sample': sorted(teams)[:5],
            })

    matched_rows = []
    for identity, pids in matched_by_identity.items():
        if len(pids) == 1:
            matched_rows.append({'player_id': pids[0], 'norm_name': identity[0],
                                  'birth_year': identity[1], 'method': 'composite'})
        else:
            ambiguous.append({
                'reason': 'multiple_team_corroborated_candidates',
                'identity': f"{identity[0]} (b.{identity[1]})",
                'tm_player_ids': pids,
            })

    matches = pd.DataFrame(matched_rows, columns=['player_id', 'norm_name', 'birth_year', 'method'])
    return matches, ambiguous


def build_matches(project_rows, valuations_df, players_df):
    """Runs both match paths and returns
    (matches_df[player_id, norm_name, birth_year, method], report dict)."""
    id_matches, id_unresolved = _existing_id_matches(project_rows)
    already_matched = set(zip(id_matches['norm_name'], id_matches['birth_year']))
    composite_matches, ambiguous = _composite_matches(project_rows, valuations_df, players_df, already_matched)

    matches = pd.concat([id_matches, composite_matches], ignore_index=True) if len(composite_matches) else id_matches

    all_identities = set(zip(project_rows['norm_name'], project_rows['birth_year']))
    matched_identities = set(zip(matches['norm_name'], matches['birth_year']))
    unmatched_count = len(all_identities - matched_identities)

    report = {
        'project_identities_total': len(all_identities),
        'matched_via_existing_id': int(len(id_matches)),
        'matched_via_composite_key': int(len(composite_matches)),
        'ambiguous_or_team_mismatch': len(ambiguous),
        'unmatched_no_candidate': unmatched_count,
        'existing_id_join_unresolved': id_unresolved,
        'ambiguous_samples': ambiguous[:50],
    }
    return matches, report
