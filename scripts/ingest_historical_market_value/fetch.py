#!/usr/bin/env python3
"""
Step 1 of the historical market-value ingestion pipeline: fetches the
dcaribou/transfermarkt-datasets project's player_valuations + players
tables (via a pre-built DuckDB snapshot over HTTPS) and caches them locally.
"""

import os
import sys

import pandas as pd
import requests

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

CACHE_DIR = os.path.join(_THIS_DIR, '.cache')
DUCKDB_URL = 'https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb'
DUCKDB_PATH = os.path.join(CACHE_DIR, 'transfermarkt-datasets.duckdb')
VALUATIONS_PATH = os.path.join(CACHE_DIR, 'player_valuations.parquet')
PLAYERS_PATH = os.path.join(CACHE_DIR, 'players.parquet')

# This project's league slug -> Transfermarkt's competition_id.
# efl-championship/serie-b excluded (dataset has no second-tier rows);
# major-league (MLS) excluded - this project's own MLS rows have a backfill artifact that would corrupt merges.
LEAGUE_TM_MAP = {
    'premier-league': 'GB1',
    'la-liga': 'ES1',
    'serie-a': 'IT1',
    'bundesliga': 'L1',
    'ligue-1': 'FR1',
    'eredivisie': 'NL1',
    'primeira-liga': 'PO1',
    'belgian-pro-league': 'BE1',
    'campeonato-brasileiro-serie-a': 'BRA1',
    'liga-mx': 'MEX1',
    'liga-profesional-argentina': 'ARG1',
}
TM_LEAGUE_TO_PROJECT = {v: k for k, v in LEAGUE_TM_MAP.items()}


def _download(force=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(DUCKDB_PATH) and not force:
        return DUCKDB_PATH

    tmp_path = DUCKDB_PATH + '.part'
    print(f"Downloading {DUCKDB_URL} -> {DUCKDB_PATH} ...")
    with requests.get(DUCKDB_URL, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get('Content-Length', 0))
        read = 0
        with open(tmp_path, 'wb') as out:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                out.write(chunk)
                read += len(chunk)
                if total:
                    print(f"\r  {read / 1e6:,.0f} / {total / 1e6:,.0f} MB", end='', flush=True)
    print()
    os.replace(tmp_path, DUCKDB_PATH)
    return DUCKDB_PATH


def fetch(force=False):
    """Download the dataset (if not cached) and extract player_valuations
    + players, filtered to the covered leagues, into local parquet files.
    Returns (valuations_df, players_df). Idempotent."""
    if os.path.exists(VALUATIONS_PATH) and os.path.exists(PLAYERS_PATH) and not force:
        return pd.read_parquet(VALUATIONS_PATH), pd.read_parquet(PLAYERS_PATH)

    import duckdb

    db_path = _download(force=force)
    con = duckdb.connect(db_path, read_only=True)
    try:
        valuations = con.execute(
            """
            SELECT player_id, date, market_value_in_eur, current_club_name,
                   player_club_domestic_competition_id AS tm_competition_id
            FROM player_valuations
            WHERE player_club_domestic_competition_id = ANY(?)
              AND market_value_in_eur IS NOT NULL
            """,
            [list(LEAGUE_TM_MAP.values())],
        ).fetchdf()

        con.register('filtered_valuations', valuations)
        players = con.execute(
            """
            SELECT p.player_id, p.name, p.date_of_birth, p.current_club_name AS latest_club_name
            FROM players p
            WHERE p.player_id IN (SELECT DISTINCT player_id FROM filtered_valuations)
            """
        ).fetchdf()
    finally:
        con.close()

    os.makedirs(CACHE_DIR, exist_ok=True)
    valuations.to_parquet(VALUATIONS_PATH, index=False)
    players.to_parquet(PLAYERS_PATH, index=False)
    return valuations, players


if __name__ == '__main__':
    v, p = fetch()
    print(f"valuations: {len(v):,} rows, {v['player_id'].nunique():,} distinct players")
    print(f"players: {len(p):,} rows")
    print(v['tm_competition_id'].value_counts())
