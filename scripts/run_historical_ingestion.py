#!/usr/bin/env python3
"""
Entrypoint for the historical market-value ingestion pipeline
(scripts/ingest_historical_market_value/) - a one-time/periodic process,
not part of normal app boot. Fetches, matches, and merges valuation history into player_supplementary_data.
"""

import argparse
import json
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data import loader
from scripts.ingest_historical_market_value import fetch, match_players
from scripts.ingest_historical_market_value import merge as merge_mod

REPORT_PATH = os.path.join(_SCRIPTS_DIR, 'ingest_historical_market_value', '.cache', 'ingestion_report.json')


def run(dry_run=False, force_refetch=False):
    if not loader.count_rows('league_season_team_player_data'):
        loader.boot()

    print("Fetching Transfermarkt dataset (cached locally after the first run)...")
    valuations_df, players_df = fetch.fetch(force=force_refetch)
    print(f"  {len(valuations_df):,} valuation rows across {valuations_df['player_id'].nunique():,} players "
          f"in {len(fetch.LEAGUE_TM_MAP)} covered leagues")

    print("Loading this project's own player-season rows for those leagues...")
    project_rows = match_players.load_project_rows()
    n_identities = len(project_rows[['norm_name', 'birth_year']].drop_duplicates())
    print(f"  {len(project_rows):,} rows, {n_identities:,} distinct player identities")

    print("Matching players (existing transfermarkt_id first, then name+team+birth_year)...")
    matches, match_report = match_players.build_matches(project_rows, valuations_df, players_df)
    print(f"  matched via existing id:     {match_report['matched_via_existing_id']:,}")
    print(f"  matched via composite key:   {match_report['matched_via_composite_key']:,}")
    print(f"  ambiguous / team mismatch:   {match_report['ambiguous_or_team_mismatch']:,}")
    print(f"  unmatched (no TM candidate): {match_report['unmatched_no_candidate']:,}")

    print("Deriving seasons and attaching valuations to project player-season rows...")
    new_rows, attach_stats = merge_mod.build_merge_rows(valuations_df, matches, project_rows)
    print(f"  valuations for matched players:          {attach_stats['valuations_for_matched_players']:,}")
    print(f"  attached to a project player-season row: {attach_stats['valuations_attached_to_a_project_season']:,}")
    print(f"  dropped (no matching project season):    {attach_stats['valuations_dropped_no_project_season_row']:,}")

    print(f"Merging into player_supplementary_data{' (dry run - not writing)' if dry_run else ''}...")
    written_rows, merge_stats = merge_mod.merge_into_supplementary(new_rows, dry_run=dry_run)
    print(f"  new rows written:                   {merge_stats['new_rows_written']:,}")
    print(f"  skipped (already had a real value): {merge_stats['new_rows_skipped_already_covered']:,}")

    if len(written_rows):
        coverage = (
            written_rows.groupby(['league', 'season']).size().reset_index(name='n')
            .sort_values(['league', 'season'])
        )
    else:
        coverage = written_rows

    report = {
        'leagues_covered': sorted(fetch.LEAGUE_TM_MAP.keys()),
        'leagues_excluded': {
            'efl-championship': 'not tracked by the Transfermarkt dataset (2nd-tier division)',
            'serie-b': 'not tracked by the Transfermarkt dataset (2nd-tier division)',
            'major-league': "excluded due to a pre-existing data-quality bug in this project's own "
                             "player-season table for MLS (fabricated rows back to 2000-2001 for teams "
                             "founded decades later) - see fetch.py's LEAGUE_TM_MAP comment",
        },
        'match_report': match_report,
        'attach_stats': attach_stats,
        'merge_stats': {k: v for k, v in merge_stats.items() if k != 'backup_path'},
        'backup_path': merge_stats.get('backup_path'),
        'coverage_by_league_season': coverage.to_dict(orient='records') if len(written_rows) else [],
        'dry_run': dry_run,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report written to {REPORT_PATH}")

    print("\nCoverage by league/season (new rows written):")
    if len(written_rows):
        for _, r in coverage.iterrows():
            print(f"  {r['league']:<32} {r['season']:<10} {r['n']:>6,}")
    else:
        print("  (none)")

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--dry-run', action='store_true', help="Compute everything but don't write to disk/DB")
    parser.add_argument('--refetch', action='store_true', help='Force re-download of the Transfermarkt dataset')
    args = parser.parse_args()
    run(dry_run=args.dry_run, force_refetch=args.refetch)


if __name__ == '__main__':
    main()
