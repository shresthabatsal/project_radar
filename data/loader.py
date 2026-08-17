#!/usr/bin/env python3
"""
Data access layer for Radar: owns the in-memory SQLite store seeded from
data/data_files/ (replaceable via POST /upload), plus dependency-free
record-parsing utilities (safe_float, parse_age, etc.) shared by backend/ and ml/.
"""

import io
import os
import re
import sqlite3
import threading
import unicodedata
from datetime import datetime

import pandas as pd

# ==============================================================================
# CONNECTION
# ==============================================================================
# One shared in-memory SQLite connection for the whole process; callers
# serialise around it with LOCK. A psycopg2-shaped shim (%s-style params,
# context-managed connections) so scout_engine.py's commands run unchanged.

LOCK = threading.Lock()

_db = sqlite3.connect(":memory:", check_same_thread=False)


class _Cur:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        self._cur.execute(sql, list(params) if params else [])
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()


class _Conn:
    def cursor(self):
        return _Cur(_db.cursor())

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        # keep the shared in-memory db alive across requests
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def get_connection():
    return _Conn()


def count_rows(table):
    """Row count for a table in the store, or 0 if it doesn't exist yet
    (e.g. before boot / before the first upload)."""
    try:
        with LOCK:
            return _db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


# ==============================================================================
# CACHES
# ==============================================================================

_ALL_LEAGUES_CACHE = {}
_SUPP_HISTORY_CACHE = {}


def clear_caches(engine_module=None):
    """Invalidate the season-keyed load_all_leagues_data cache and the
    whole-table supplementary-history index, plus scout_engine's
    _MS_POOL_CACHE if given. All must drop after every /upload."""
    _ALL_LEAGUES_CACHE.clear()
    _SUPP_HISTORY_CACHE.clear()
    if engine_module is not None:
        c = getattr(engine_module, "_MS_POOL_CACHE", None)
        if isinstance(c, dict):
            c.clear()


# ==============================================================================
# POSITION NORMALISATION
# ==============================================================================

def standardize_positions(df):
    """Standardize position names, mapping various abbreviations to
    GK/DF/MF/FW. Adds primary_position and secondary_position columns."""
    position_map = {
        'GK': 'GK', 'GOALKEEPER': 'GK',
        'DF': 'DF', 'DEFENDER': 'DF', 'CB': 'DF', 'LB': 'DF', 'RB': 'DF', 'LWB': 'DF', 'RWB': 'DF',
        'MF': 'MF', 'MIDFIELDER': 'MF', 'CM': 'MF', 'CDM': 'MF', 'CAM': 'MF', 'LM': 'MF', 'RM': 'MF',
        'FW': 'FW', 'ST': 'FW', 'ATTACKER': 'FW', 'STRIKER': 'FW', 'CF': 'FW', 'LW': 'FW', 'RW': 'FW'
    }

    if 'position' not in df.columns:
        for col in ['pos', 'position_played', 'player_position']:
            if col in df.columns:
                df['position'] = df[col]
                break
        else:
            df['position'] = 'UNKNOWN'

    df['position'] = df['position'].astype(str).str.upper().str.strip()

    df['primary_position'] = 'UNKNOWN'
    df['secondary_position'] = None

    for idx, row in df.iterrows():
        pos_str = str(row['position'])

        # Split by common separators
        positions = []
        for sep in [',', '/', '-', ' ']:
            if sep in pos_str:
                positions = [p.strip() for p in pos_str.split(sep)]
                break

        if not positions:
            positions = [pos_str]

        # Map each position and filter valid ones
        mapped_positions = []
        for pos in positions:
            mapped = position_map.get(pos, None)
            if mapped and mapped not in mapped_positions:
                mapped_positions.append(mapped)

        # Assign primary and secondary positions
        if mapped_positions:
            df.at[idx, 'primary_position'] = mapped_positions[0]
            if len(mapped_positions) > 1:
                df.at[idx, 'secondary_position'] = mapped_positions[1]
        else:
            # If no valid mapping found, try to infer from the original string
            if any(gk in pos_str for gk in ['GK', 'GOAL']):
                df.at[idx, 'primary_position'] = 'GK'
            elif any(df_pos in pos_str for df_pos in ['DF', 'DEF', 'CB', 'LB', 'RB', 'WB']):
                df.at[idx, 'primary_position'] = 'DF'
            elif any(mf in pos_str for mf in ['MF', 'MID', 'CM', 'DM', 'AM']):
                df.at[idx, 'primary_position'] = 'MF'
            elif any(fw in pos_str for fw in ['FW', 'ST', 'CF', 'ATTACK', 'STRIKER']):
                df.at[idx, 'primary_position'] = 'FW'

    return df


# ==============================================================================
# RECORD PARSING
# ==============================================================================

def safe_float(value):
    if isinstance(value, pd.Series):
        return value.apply(lambda x: safe_float(x))
    if pd.isna(value) or value is None:
        return 0.0
    s = str(value).strip()
    if s in ('', 'nan', 'None', 'null', 'NaN'):
        return 0.0
    try:
        return float(s.replace(',', ''))
    except (ValueError, TypeError):
        return 0.0


def _num_series(col):
    """Vectorised numeric parse tolerant of comma thousand-separators -
    plain pd.to_numeric on '1,409'-style text silently reads NaN, dropping
    every regular starter (>=1000 minutes) from minutes filters."""
    return pd.to_numeric(col.astype(str).str.replace(',', '', regex=False), errors='coerce')


def parse_age(value):
    if pd.isna(value) or value is None:
        return 0.0
    s = str(value).strip()
    if '-' in s:
        parts = s.split('-')
        if len(parts) == 2:
            try:
                years = int(parts[0])
                days = int(parts[1])
                if 10 <= years <= 60 and 0 <= days <= 366:
                    return float(years)
            except (ValueError, TypeError):
                pass
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def contract_months_remaining(row):
    expiry = row.get('contract_expiry', None)
    if expiry is None or pd.isna(expiry):
        return None
    try:
        if isinstance(expiry, str):
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m', '%Y'):
                try:
                    exp_dt = datetime.strptime(expiry.strip(), fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
        else:
            exp_dt = pd.Timestamp(expiry).to_pydatetime()
        now = datetime.now()
        months = (exp_dt.year - now.year) * 12 + (exp_dt.month - now.month)
        return max(0, months)
    except Exception:
        return None


def next_season_label(season):
    """'2024-2025' -> '2025-2026'. Returns None if unparseable."""
    try:
        a, b = str(season).split('-')
        return f"{int(a) + 1}-{int(b) + 1}"
    except Exception:
        return None


def prev_season_label(season):
    """'2024-2025' -> '2023-2024'. Returns None if unparseable."""
    try:
        a, b = str(season).split('-')
        return f"{int(a) - 1}-{int(b) - 1}"
    except Exception:
        return None


# ==============================================================================
# IDENTITY MATCHING
# ==============================================================================

def _norm_key(s):
    """Normalise a name/team/league for matching: strip accents, lowercase,
    collapse whitespace. So 'Ádám Nagy' and 'Adam Nagy' match."""
    if not isinstance(s, str):
        s = '' if s is None else str(s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


def _name_token_set(s):
    """_norm_key(s), further split on whitespace and hyphens, so a
    hyphenated compound surname tokenizes like a shortened single-surname
    form of the same name. Used only by the loose-match fallback below."""
    return tuple(t for t in re.split(r'[\s\-]+', _norm_key(s)) if t)


def _names_loosely_match(a, b):
    """True if two spellings likely name the same person despite
    _norm_key(a) != _norm_key(b) - same first token AND one's full token
    set a subset of the other's. Requires >=2 tokens per side to avoid single-name false matches."""
    return _tokens_loosely_match(_name_token_set(a), _name_token_set(b))


def _tokens_loosely_match(ta, tb):
    """Same rule as _names_loosely_match, on already-tokenized names -
    lets a caller precompute one side's tokens once and reuse them across many comparisons."""
    if len(ta) < 2 or len(tb) < 2 or ta[0] != tb[0]:
        return False
    sa, sb = set(ta), set(tb)
    return sa <= sb or sb <= sa


# ==============================================================================
# READS
# ==============================================================================

def load_meta():
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT DISTINCT season, league, team
            FROM league_season_team_player_data
            ORDER BY season DESC, league, team
        """, conn)
    return df

def load_filter_options():
    """Distinct team/league/nationality across the whole dataset - a
    lightweight raw query for GET /players/filters' unscoped fallback.
    The season-scoped path reuses load_all_leagues_data instead."""
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT DISTINCT team, league, nationality
            FROM league_season_team_player_data
        """, conn)
    return df

def get_last_updated():
    """Max last_updated timestamp across player_supplementary_data, or
    None if unavailable. A freshness signal for GET /meta, not a scrape-completion guarantee."""
    with get_connection() as conn:
        try:
            df = pd.read_sql(
                "SELECT MAX(last_updated) AS last_updated FROM player_supplementary_data", conn
            )
        except Exception:
            return None
    if df.empty:
        return None
    val = df.iloc[0]['last_updated']
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val)

def load_players(season, league, team):
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT * FROM league_season_team_player_data
            WHERE season = %s AND league = %s AND team = %s
        """, conn, params=[season, league, team])
    if not df.empty:
        df = standardize_positions(df)
    return df

def load_league_data(season, league):
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT * FROM league_season_team_player_data
            WHERE season = %s AND league = %s
        """, conn, params=[season, league])
    if not df.empty:
        df = standardize_positions(df)
    return df

def load_all_leagues_data(season):
    # Cached per season: multi-season matching and gem tagging both re-load
    # the same season, so this would otherwise run many times per request.
    # Returns a defensive copy so callers can mutate freely.
    if season in _ALL_LEAGUES_CACHE:
        return _ALL_LEAGUES_CACHE[season].copy()
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT * FROM league_season_team_player_data
            WHERE season = %s
        """, conn, params=[season])
    if not df.empty:
        df = standardize_positions(df)
    _ALL_LEAGUES_CACHE[season] = df
    return df.copy()

def load_supplementary(season):
    """Load supplementary data (wages, market values, contracts).
    Falls back to the latest available season if no data for requested season."""
    try:
        with get_connection() as conn:
            df = pd.read_sql("""
                SELECT * FROM player_supplementary_data WHERE season = %s
            """, conn, params=[season])
            if df.empty:
                # Fallback: use the latest available season's supplementary data
                df = pd.read_sql("""
                    SELECT * FROM player_supplementary_data
                    WHERE season = (SELECT MAX(season) FROM player_supplementary_data)
                """, conn)
            return df
    except Exception:
        return pd.DataFrame()

def load_all_supplementary():
    """Every player_supplementary_data row across all seasons - used to
    build a season-keyed prior-market-value lookup. Deliberately has NO
    "fall back to latest season" behavior, unlike load_supplementary()."""
    with get_connection() as conn:
        try:
            df = pd.read_sql("""
                SELECT player, team, league, season, market_value_eur
                FROM player_supplementary_data
            """, conn)
        except Exception:
            return pd.DataFrame()
    return df


SUPP_COLS = ['contract_expiry', 'contract_signed', 'release_clause_eur', 'weekly_wage_eur', 'annual_wage_eur', 'market_value_eur']


def _consolidate_by_transfermarkt_id(supp):
    """Collapses duplicate-spelling supplementary rows to one per
    (transfermarkt_id, season, team, league) before name matching - keyed
    on team+league too, since a mid-season transfer can produce >1 real row per (id, season). Ties keep the more complete row."""
    if supp.empty or 'transfermarkt_id' not in supp.columns:
        return supp
    has_id = supp['transfermarkt_id'].notna()
    with_id, without_id = supp[has_id], supp[~has_id]
    if with_id.empty:
        return supp
    with_id = with_id.copy()
    with_id['_tkey'] = with_id['team'].map(_norm_key)
    with_id['_lkey'] = with_id['league'].map(_norm_key)
    with_id['_completeness'] = with_id.notna().sum(axis=1)
    with_id = (
        with_id.sort_values('_completeness', ascending=False)
        .drop_duplicates(subset=['transfermarkt_id', 'season', '_tkey', '_lkey'], keep='first')
        .drop(columns=['_completeness', '_tkey', '_lkey'])
    )
    return pd.concat([with_id, without_id], ignore_index=True)


def merge_supplementary(df, season):
    """Merges supplementary data (wages, market values, contracts) via
    four tiers - strict (player+team+league) down to loose-name-only -
    each only filling what the previous tier missed, never crossing leagues. Consolidates by transfermarkt_id first."""
    supp = load_supplementary(season)
    if supp.empty:
        return df
    supp = _consolidate_by_transfermarkt_id(supp)
    supp_cols = [c for c in SUPP_COLS if c in supp.columns]
    supp_dedup = supp[['player', 'team', 'league'] + supp_cols].drop_duplicates().copy()

    df = df.copy()
    df['_pkey'] = df['player'].map(_norm_key)
    df['_tkey'] = df['team'].map(_norm_key)
    df['_lkey'] = df['league'].map(_norm_key)
    supp_dedup['_pkey'] = supp_dedup['player'].map(_norm_key)
    supp_dedup['_tkey'] = supp_dedup['team'].map(_norm_key)
    supp_dedup['_lkey'] = supp_dedup['league'].map(_norm_key)

    # Step 1: strict merge on normalised player + team + league
    supp_strict = supp_dedup[['_pkey', '_tkey', '_lkey'] + supp_cols].drop_duplicates(
        subset=['_pkey', '_tkey', '_lkey'], keep='first')
    merged = df.merge(supp_strict, on=['_pkey', '_tkey', '_lkey'], how='left')

    # Step 2: fallback on normalised player + league only (same league),
    # filling any field still missing. Never matches across leagues.
    supp_by_pl = supp_dedup.drop_duplicates(subset=['_pkey', '_lkey'], keep='first')
    supp_by_pl = supp_by_pl[['_pkey', '_lkey'] + supp_cols].rename(
        columns={c: c + '_fallback' for c in supp_cols})
    merged = merged.merge(supp_by_pl, on=['_pkey', '_lkey'], how='left')
    for col in supp_cols:
        fb = col + '_fallback'
        if fb in merged.columns:
            merged[col] = merged[col].fillna(merged[fb])
            merged.drop(columns=[fb], inplace=True)

    # Step 3: still-missing rows only - accent/suffix-tolerant name match,
    # WITHIN THE SAME TEAM (a loose match alone can conflate two different
    # players sharing a first name). Ambiguous (2+) matches are left unmatched.
    still_missing = merged[supp_cols].isna().all(axis=1)
    if still_missing.any() and not supp_dedup.empty:
        supp_by_league = {lk: g for lk, g in supp_dedup.groupby('_lkey')}
        for idx in merged.index[still_missing]:
            lkey = merged.at[idx, '_lkey']
            pool = supp_by_league.get(lkey)
            if pool is None or pool.empty:
                continue
            player_name = merged.at[idx, 'player']
            loose = pool[pool['player'].map(lambda p: _names_loosely_match(p, player_name))]
            if loose.empty:
                continue
            tkey = merged.at[idx, '_tkey']
            with_team = loose[loose['_tkey'] == tkey]
            if len(with_team) != 1:
                continue
            for col in supp_cols:
                merged.at[idx, col] = with_team.iloc[0][col]

    merged.drop(columns=['_pkey', '_tkey', '_lkey'], inplace=True, errors='ignore')
    return merged

def load_player_history(player_name):
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT * FROM league_season_team_player_data
            WHERE player = %s ORDER BY season ASC, league, team
        """, conn, params=[player_name])
        if df.empty:
            df = pd.read_sql("""
                SELECT * FROM league_season_team_player_data
                WHERE LOWER(player) LIKE LOWER(%s)
                ORDER BY season ASC, league, team
            """, conn, params=[f'%{player_name}%'])
    if not df.empty:
        df = standardize_positions(df)
    return df

def _all_supplementary_indexed():
    """The full player_supplementary_data table plus a precomputed
    (norm_key, token_set) per row, built once per process and reused
    until clear_caches() invalidates it - avoids re-tokenizing 70k+ rows on every squad-profile/risk call."""
    if 'df' not in _SUPP_HISTORY_CACHE:
        try:
            with get_connection() as conn:
                all_rows = pd.read_sql("SELECT * FROM player_supplementary_data", conn)
        except Exception:
            all_rows = pd.DataFrame()
        if not all_rows.empty:
            norm = all_rows['player'].map(_norm_key)
            tokens = all_rows['player'].map(_name_token_set)
        else:
            norm = pd.Series(dtype=str)
            tokens = pd.Series(dtype=object)
        _SUPP_HISTORY_CACHE['df'] = all_rows
        _SUPP_HISTORY_CACHE['norm'] = norm
        _SUPP_HISTORY_CACHE['tokens'] = tokens
    return _SUPP_HISTORY_CACHE['df'], _SUPP_HISTORY_CACHE['norm'], _SUPP_HISTORY_CACHE['tokens']


def load_player_supplementary_history(player_name):
    """Every supplementary row for a player across all seasons - matches
    by exact normalised name UNIONED with a loose accent/suffix-tolerant
    match (different spellings can carry different seasons). Never falls back to another season."""
    all_rows, norm, tokens = _all_supplementary_indexed()
    if all_rows.empty:
        return all_rows
    target_tokens = _name_token_set(player_name)
    exact = all_rows[norm == _norm_key(player_name)]
    loose = all_rows[tokens.map(lambda t: _tokens_loosely_match(t, target_tokens))]
    return pd.concat([exact, loose]).drop_duplicates()


# ==============================================================================
# WRITES  (table load from DataFrames - boot seed + POST /upload)
# ==============================================================================

def load_players_frame(players: pd.DataFrame, engine_module=None):
    """Replace just the players table + its indexes, and refresh the caches."""
    with LOCK:
        players.to_sql(
            "league_season_team_player_data", _db, if_exists="replace", index=False
        )
        cur = _db.cursor()
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_season "
            "ON league_season_team_player_data(season)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_season_league "
            "ON league_season_team_player_data(season, league)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_player "
            "ON league_season_team_player_data(player)"
        )
        _db.commit()
        clear_caches(engine_module)


def load_supp_frame(supplementary: pd.DataFrame, engine_module=None):
    """Replace just the supplementary table + its index, and refresh the caches."""
    with LOCK:
        supplementary.to_sql(
            "player_supplementary_data", _db, if_exists="replace", index=False
        )
        cur = _db.cursor()
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_supp_player "
            "ON player_supplementary_data(player)"
        )
        _db.commit()
        clear_caches(engine_module)


# Named, auditable list of specific (player, season, team) rows to treat
# as spurious duplicates and drop - currently empty. A general dedup
# heuristic was tried and rejected: it also excluded genuine transfers.
_KNOWN_BAD_PLAYER_TEAM_ROWS = set()


def _prioritize_current_team_rows(players: pd.DataFrame, supplementary: pd.DataFrame):
    """A player can legitimately have two rows in the same (season,
    league) from a mid-season transfer. Moves the row with a real
    contract_signed date to sort last within its group, so "take the last row" tie-breaks resolve to the current club."""
    if players.empty or supplementary.empty:
        return players
    needed_p = {'player', 'birth_year', 'season', 'league', 'team'}
    needed_s = {'player', 'season', 'team', 'contract_signed'}
    if not needed_p <= set(players.columns) or not needed_s <= set(supplementary.columns):
        return players

    signed = supplementary[['player', 'season', 'team', 'contract_signed']].copy()
    signed['contract_signed'] = pd.to_datetime(signed['contract_signed'], errors='coerce')
    signed = signed.dropna(subset=['contract_signed'])
    if signed.empty:
        return players
    signed_keys = {
        (_norm_key(str(r['player'])), str(r['season']), str(r['team']))
        for _, r in signed.iterrows()
    }

    players = players.reset_index(drop=True)
    group_cols = ['player', 'birth_year', 'season', 'league']
    multi_mask = players.groupby(group_cols)['team'].transform('nunique') > 1
    if not multi_mask.any():
        return players

    sort_key = players.index.to_series().astype(float)
    for _, grp in players.loc[multi_mask].groupby(group_cols):
        if len(grp) < 2:
            continue
        has_signed = grp.apply(
            lambda r: (_norm_key(str(r['player'])), str(r['season']), str(r['team'])) in signed_keys,
            axis=1,
        )
        if has_signed.any() and not has_signed.all():
            max_pos = grp.index.max()
            sort_key.loc[grp.index[has_signed]] = max_pos + 0.5

    return (
        players.assign(_sort_key=sort_key)
        .sort_values('_sort_key', kind='stable')
        .drop(columns=['_sort_key'])
        .reset_index(drop=True)
    )


def _dedupe_backfilled_duplicate_seasons(players: pd.DataFrame, min_repeats=5):
    """Detects backfill-padding: the same (minutes, goals, assists)
    stat-line duplicated across `min_repeats`+ different seasons for one
    (player, birth_year, team) - keeps only the latest season in each duplicate run, drops the rest."""
    if players.empty or 'minutes' not in players.columns:
        return players
    key_cols = ['player', 'birth_year', 'team']
    if not all(c in players.columns for c in key_cols):
        return players
    if 'goals' not in players.columns or 'assists' not in players.columns or 'season' not in players.columns:
        return players

    minutes_num = pd.to_numeric(players['minutes'].astype(str).str.replace(',', ''), errors='coerce')
    goals_num = pd.to_numeric(players['goals'], errors='coerce')
    assists_num = pd.to_numeric(players['assists'], errors='coerce')
    start_year = pd.to_numeric(players['season'].astype(str).str.split('-').str[0], errors='coerce')

    fp = pd.DataFrame({
        'player': players['player'], 'birth_year': players['birth_year'], 'team': players['team'],
        'minutes': minutes_num, 'goals': goals_num, 'assists': assists_num, 'start_year': start_year,
    })
    group_cols = ['player', 'birth_year', 'team', 'minutes', 'goals', 'assists']
    counts = fp.groupby(group_cols, dropna=True)['start_year'].transform('count')
    is_dup_group = counts >= min_repeats
    if not is_dup_group.fillna(False).any():
        return players

    latest_in_group = fp.groupby(group_cols, dropna=True)['start_year'].transform('max')
    is_latest = fp['start_year'] == latest_in_group
    drop_mask = is_dup_group.fillna(False) & ~is_latest.fillna(False)
    if drop_mask.any():
        players = players.loc[~drop_mask].copy()
    return players


def _clean_known_data_issues(players: pd.DataFrame, supplementary: pd.DataFrame):
    """Applied once, at load_frames' single choke point (both boot and
    POST /upload go through it). Four fixes in order: drop known-bad rows,
    drop malformed comma-joined team names (unrecoverable which club is current), collapse backfill duplicates, then reorder multi-team rows (must run LAST)."""
    if not players.empty and {'player', 'season', 'league', 'team'} <= set(players.columns):
        bad_mask = players.apply(
            lambda r: (str(r.get('player')), str(r.get('season')), str(r.get('league')), str(r.get('team')))
            in _KNOWN_BAD_PLAYER_TEAM_ROWS,
            axis=1,
        )
        if bad_mask.any():
            players = players.loc[~bad_mask].copy()

    if not supplementary.empty and 'team' in supplementary.columns:
        comma_mask = supplementary['team'].astype(str).str.contains(',', na=False)
        if comma_mask.any():
            supplementary = supplementary.loc[~comma_mask].copy()

    players = _dedupe_backfilled_duplicate_seasons(players)
    players = _prioritize_current_team_rows(players, supplementary)

    return players, supplementary


def load_frames(players: pd.DataFrame, supplementary: pd.DataFrame, engine_module=None):
    """Rebuild both tables from two DataFrames."""
    players, supplementary = _clean_known_data_issues(players, supplementary)
    load_players_frame(players, engine_module=engine_module)
    load_supp_frame(supplementary, engine_module=engine_module)


def read_csv_upload(raw: bytes, name: str) -> pd.DataFrame:
    gz = name.endswith(".gz")
    return pd.read_csv(
        io.BytesIO(raw), compression="gzip" if gz else None, low_memory=False
    )


# ==============================================================================
# BOOT  (seed from data/data_files/ on process start)
# ==============================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_files")


def boot(engine_module=None):
    """Seed the store from the on-disk CSV snapshot in data_files/, if present."""
    players = os.path.join(DATA_DIR, "players.csv.gz")
    supp = os.path.join(DATA_DIR, "supplementary.csv.gz")
    if os.path.exists(players) and os.path.exists(supp):
        p = pd.read_csv(players, compression="gzip", low_memory=False)
        s = pd.read_csv(supp, compression="gzip", low_memory=False)
        load_frames(p, s, engine_module=engine_module)
        print(f"Loaded {len(p):,} player-season rows + {len(s):,} supplementary rows.")
    else:
        print(
            "No data/data_files/players.csv.gz + data/data_files/supplementary.csv.gz found - "
            "upload a snapshot via POST /upload (multipart: players, supplementary)."
        )
