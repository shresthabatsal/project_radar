#!/usr/bin/env python3
"""
Step 3 of the historical market-value ingestion pipeline: converts each
Transfermarkt valuation's raw calendar date into this project's season
label, using FBref's Aug 1 - Jul 31 split-year convention for every league.
"""

import pandas as pd


def date_to_season(date_value):
    """A calendar date -> 'YYYY-YYYY'. Aug 1 - Jul 31 boundary: a valuation
    dated 2024-03-15 falls in the 2023-2024 season; one dated 2024-09-01
    falls in 2024-2025. Returns None for a missing/unparseable date."""
    d = pd.Timestamp(date_value)
    if pd.isna(d):
        return None
    start_year = d.year if d.month >= 8 else d.year - 1
    return f"{start_year}-{start_year + 1}"


def add_season_column(df, date_col='date', season_col='season'):
    """Returns a copy of df with an added season_col derived from date_col."""
    df = df.copy()
    df[season_col] = df[date_col].apply(date_to_season)
    return df
