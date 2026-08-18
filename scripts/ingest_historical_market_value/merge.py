#!/usr/bin/env python3
"""
Step 4 of the historical market-value ingestion pipeline: folds matched,
season-labeled historical valuations into player_supplementary_data
without overwriting any (player, team, league, season) that already carries a real market_value_eur.
"""

import os
import shutil
import sys
from datetime import datetime

import pandas as pd

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data.loader import _norm_key
from scripts.ingest_historical_market_value.derive_seasons import add_season_column

SUPPLEMENTARY_PATH = os.path.join(_PROJECT_ROOT, 'data', 'data_files', 'supplementary.csv.gz')


def build_merge_rows(valuations_df, matches_df, project_rows):
    """Attaches TM valuations to matched project player-seasons - a
    valuation only attaches to a season this project actually has a row
    for; everything else is dropped and counted. Returns (new_rows_df, stats dict)."""
    valuations_df = add_season_column(valuations_df)
    v = valuations_df.merge(matches_df[['player_id', 'norm_name', 'birth_year']], on='player_id', how='inner')

    target = project_rows[['norm_name', 'birth_year', 'season', 'player', 'team', 'league']].drop_duplicates()
    merged = v.merge(target, on=['norm_name', 'birth_year', 'season'], how='inner')

    stats = {
        'valuations_for_matched_players': int(len(v)),
        'valuations_attached_to_a_project_season': int(len(merged)),
        'valuations_dropped_no_project_season_row': int(len(v) - len(merged)),
    }

    if merged.empty:
        return merged.assign(market_value_eur=pd.Series(dtype=float), market_value_date=pd.Series(dtype=str),
                              transfermarkt_id=pd.Series(dtype=float))[
            ['player', 'team', 'season', 'league', 'market_value_eur', 'market_value_date', 'transfermarkt_id']
        ], stats

    out = pd.DataFrame({
        'player': merged['player'],
        'team': merged['team'],
        'season': merged['season'],
        'league': merged['league'],
        'market_value_eur': merged['market_value_in_eur'].astype(float),
        'market_value_date': merged['date'].astype(str),
        'transfermarkt_id': merged['player_id'].astype(float),
    })
    return out, stats


def merge_into_supplementary(new_rows, dry_run=False):
    """Concats new_rows onto the existing table, skipping keys that
    already have a real market_value_eur, and (unless dry_run) writes
    back to disk + reloads the live store. Returns (rows_actually_written_df, stats dict)."""
    existing = pd.read_csv(SUPPLEMENTARY_PATH)
    has_value = existing['market_value_eur'].notna()
    existing_keys = set(zip(
        existing.loc[has_value, 'player'].map(_norm_key),
        existing.loc[has_value, 'team'].map(_norm_key),
        existing.loc[has_value, 'league'].map(_norm_key),
        existing.loc[has_value, 'season'],
    ))

    if new_rows.empty:
        return new_rows, {'new_rows_written': 0, 'new_rows_skipped_already_covered': 0,
                           'total_supplementary_rows_after': len(existing)}

    new_rows = new_rows.copy()
    new_rows['_key'] = list(zip(
        new_rows['player'].map(_norm_key), new_rows['team'].map(_norm_key),
        new_rows['league'].map(_norm_key), new_rows['season'],
    ))
    # A player can have more than one valuation dated within the same
    # season - keep the snapshot closest to season end as the representative value.
    new_rows = new_rows.sort_values('market_value_date').drop_duplicates('_key', keep='last')

    already_covered_mask = new_rows['_key'].isin(existing_keys)
    to_add = new_rows.loc[~already_covered_mask].drop(columns=['_key'])

    stats = {
        'new_rows_written': int(len(to_add)),
        'new_rows_skipped_already_covered': int(already_covered_mask.sum()),
    }

    if to_add.empty:
        stats['total_supplementary_rows_after'] = len(existing)
        return to_add, stats

    to_add = to_add.copy()
    max_id = int(pd.to_numeric(existing['id'], errors='coerce').max()) if 'id' in existing.columns else 0
    to_add.insert(0, 'id', range(max_id + 1, max_id + 1 + len(to_add)))

    combined = pd.concat([existing, to_add], ignore_index=True, sort=False)
    stats['total_supplementary_rows_after'] = len(combined)

    if not dry_run:
        backup_path = SUPPLEMENTARY_PATH + f".bak-{datetime.now():%Y%m%dT%H%M%S}"
        shutil.copy2(SUPPLEMENTARY_PATH, backup_path)
        combined.to_csv(SUPPLEMENTARY_PATH, index=False, compression='gzip')
        stats['backup_path'] = backup_path

        from data import loader
        if loader.count_rows('league_season_team_player_data'):
            loader.load_supp_frame(combined)

    return to_add, stats
