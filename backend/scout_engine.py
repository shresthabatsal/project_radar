#!/usr/bin/env python3
"""
Player scouting analysis: composite index, similarity, hidden gems, market
value, moneyball, and squad/risk scoring. Imported in-process by backend/main.py
and backend/routers/*.py, which call its cmd_* functions directly.
"""

import sys
import os
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances, manhattan_distances
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import MinCovDet
from scipy.spatial.distance import mahalanobis as mahalanobis_dist
import warnings
warnings.filterwarnings('ignore')

# data/ is a sibling of backend/, not a subpackage of it - put the project
# root on sys.path so `from data import loader` resolves whether this module
# is launched via main.py or imported standalone.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from data.loader import (
    get_connection, standardize_positions, _norm_key,
    safe_float, parse_age, contract_months_remaining, _num_series,
    load_meta, load_players, load_league_data, load_all_leagues_data,
    load_supplementary, merge_supplementary, SUPP_COLS,
    load_player_history, load_player_supplementary_history,
    prev_season_label,
)
from ml.market_value.train import calculate_player_market_value
from ml.market_value import predict as mv_predict
from ml.market_value import explainability as mv_explain
from ml.style_clustering import predict as style_predict
from backend.scoring.composite import (
    get_playing_style_categories, get_negative_metrics, invert_negative_metrics,
    calculate_percentile_score, calculate_category_scores,
    calculate_composite_index, get_power_rating, composite_description,
    build_season_position_table,
)
from backend.scoring.moneyball import (
    calculate_moneyball, contract_opportunity_breakdown, calculate_contract_opportunity_score,
)
from backend.scoring.risk import assess_player_risk
from backend.scoring.gems import detect as detect_gem
from backend.scoring.similarity import position_pool, find_similar, DEFAULT_SIMILARITY_METHOD
from backend.scoring.benchmark import metric_leaders, category_leaders, league_best
from backend.scoring.style_breakdown import category_breakdown, summarize_strengths_weaknesses
from backend.scoring.career import build_history
from backend.scoring.impact import impact_breakdown

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# This module loads data (data/loader.py) and calls into ml/market_value,
# ml/style_clustering, and backend/scoring/* for the actual computations;
# it formats responses rather than computing scores itself.

LEAGUE_MAP = {
    'premier-league':              {'fbref_id': '9',  'fbref_name': 'Premier-League',      'understat': 'epl',        'capology': 'uk/premier-league',   'tm': 'GB1'},
    'la-liga':                     {'fbref_id': '12', 'fbref_name': 'La-Liga',             'understat': 'la_liga',    'capology': 'es/la-liga',          'tm': 'ES1'},
    'serie-a':                     {'fbref_id': '11', 'fbref_name': 'Serie-A',             'understat': 'serie_a',    'capology': 'it/serie-a',          'tm': 'IT1'},
    'bundesliga':                  {'fbref_id': '20', 'fbref_name': 'Bundesliga',          'understat': 'bundesliga', 'capology': 'de/1-bundesliga',     'tm': 'L1'},
    'ligue-1':                     {'fbref_id': '13', 'fbref_name': 'Ligue-1',             'understat': 'ligue_1',    'capology': 'fr/ligue-1',          'tm': 'FR1'},
    'eredivisie':                  {'fbref_id': '23', 'fbref_name': 'Eredivisie',          'understat': None,         'capology': 'nl/eredivisie',       'tm': 'NL1'},
    'efl-championship':            {'fbref_id': '10', 'fbref_name': 'Championship',        'understat': None,         'capology': 'uk/championship',     'tm': 'GB2'},
    'primeira-liga':               {'fbref_id': '32', 'fbref_name': 'Primeira-Liga',       'understat': None,         'capology': 'pt/primeira-liga',    'tm': 'PO1'},
    'belgian-pro-league':          {'fbref_id': '37', 'fbref_name': 'Belgian-Pro-League',  'understat': None,         'capology': 'be/first-division-a', 'tm': 'BE1'},
    'serie-b':                     {'fbref_id': '18', 'fbref_name': 'Serie-B',             'understat': None,         'capology': 'it/serie-b',          'tm': 'IT2'},
    'major-league':                {'fbref_id': '22', 'fbref_name': 'Major-League-Soccer', 'understat': None,         'capology': 'us/mls',              'tm': 'MLS1'},
    'campeonato-brasileiro-serie-a': {'fbref_id': '24', 'fbref_name': 'Serie-A',           'understat': None,         'capology': None,                  'tm': 'BRA1'},
    'liga-profesional-argentina':  {'fbref_id': '21', 'fbref_name': 'Primera-Division',    'understat': None,         'capology': None,                  'tm': 'AR1N'},
    'liga-mx':                     {'fbref_id': '31', 'fbref_name': 'Liga-MX',             'understat': None,         'capology': None,                  'tm': 'MEX1'},
}

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def r(val, decimals=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return float(np.round(val, decimals))

def format_eur(value):
    if value is None or value <= 0:
        return "N/A"
    if value >= 1_000_000:
        return f"€{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"€{value/1_000:.0f}K"
    return f"€{value:.0f}"


def _format_signed_eur(value):
    """Same magnitude formatting as format_eur, but for a SIGNED difference
    that can legitimately be negative or zero (format_eur alone treats any
    value <= 0 as "N/A")."""
    if value is None:
        return None
    if value == 0:
        return "€0"
    sign = '+' if value > 0 else '-'
    return f"{sign}{format_eur(abs(value))}"


def get_hidden_gems_metrics():
    return {
        'GK': {
            'expected_performance': ['gk_save_pct', 'gk_saves', 'gk_clean_sheets_pct'],
            'progression': ['passes_completed', 'gk_clean_sheets_pct', 'minutes'],
            'key_metrics': ['gk_clean_sheets', 'gk_goals_against', 'gk_saves'],
        },
        'DF': {
            'expected_performance': ['xg_per90', 'npxg_per90', 'xg_assist_per90'],
            'progression': ['xg_assist_per90', 'xg_per90'],
            'key_metrics': ['tackles_per90', 'interceptions_per90', 'clearances_per90', 'goals', 'assists'],
        },
        'MF': {
            'expected_performance': ['xg_per90', 'xg_assist_per90', 'npxg_per90'],
            'progression': ['xg_assist_per90', 'xg_per90', 'assists_per90'],
            'key_metrics': ['xg_assist_per90', 'take_ons_won', 'goals', 'assists'],
        },
        'FW': {
            'expected_performance': ['xg_per90', 'npxg_per90', 'xg_assist_per90'],
            'progression': ['take_ons_won', 'xgot_per90', 'shots_on_target_per90'],
            'key_metrics': ['goals', 'assists', 'shots_per90', 'shots_on_target_pct'],
        }
    }

# ==============================================================================
# MARKET VALUE FUNCTIONS
# ==============================================================================
# calculate_player_market_value() (the heuristic) and the trained GBM live
# in ml/market_value/. Functions below decide when to use a real
# market_value_eur vs. estimate one, not the estimation logic itself.

def _perf_signal(row):
    """Player performance signal (0-100) for scaling the MV/wage estimate.
    Prefers the league-neutral z-score aggregate, then composite. Returns
    None when neither is present so legacy callers keep the old behaviour."""
    for key in ('zscore_comp', 'composite_index'):
        v = row.get(key)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            return safe_float(v)
    return None


def get_wage_value(row):
    wage = safe_float(row.get('weekly_wage_eur', 0))
    if wage > 0:
        return wage, False
    annual = safe_float(row.get('annual_wage_eur', 0))
    if annual > 0:
        return annual / 52, False
    pr = safe_float(row.get('power_rating', 50))
    age = parse_age(row.get('age', 25)) or 25  # age is "YY-DDD" in FBref data; safe_float would read 0
    pos = str(row.get('primary_position', row.get('position', 'MF')))
    league = str(row.get('league', ''))
    mv = calculate_player_market_value(pr, age, pos, league,
                                        safe_float(row.get('minutes', 0)),
                                        safe_float(row.get('games', 0)),
                                        performance=_perf_signal(row))
    estimated = mv * config.WAGE_ESTIMATE_MV_FACTOR / 52
    return max(estimated, config.WAGE_ESTIMATE_FLOOR), True

def get_market_value(row, method='heuristic'):
    mv = safe_float(row.get('market_value_eur', 0))
    if mv > 0:
        return mv, False
    pr = safe_float(row.get('power_rating', 50))
    age = parse_age(row.get('age', 25)) or 25  # age is "YY-DDD" in FBref data; safe_float would read 0
    pos = str(row.get('primary_position', row.get('position', 'MF')))
    league = str(row.get('league', ''))
    est = calculate_player_market_value(pr, age, pos, league,
                                         safe_float(row.get('minutes', 0)),
                                         safe_float(row.get('games', 0)),
                                         performance=_perf_signal(row))
    return est, True


def predict_mv_from_performance(row, method='heuristic'):
    """The model's performance-predicted value, IGNORING any real price (unlike
    get_market_value, which returns the real price when it exists). Used to compute
    the value RESIDUAL = actual - predicted (negative = market underpays = a gem)."""
    pr = safe_float(row.get('power_rating', 50))
    age = parse_age(row.get('age', 25)) or 25
    pos = str(row.get('primary_position', row.get('position', 'MF')))
    league = str(row.get('league', ''))
    return calculate_player_market_value(pr, age, pos, league,
                                         safe_float(row.get('minutes', 0)),
                                         safe_float(row.get('games', 0)),
                                         performance=_perf_signal(row))


def _season_start_year(season):
    try:
        return int(str(season).split('-')[0])
    except (ValueError, AttributeError):
        return 0


_MULTISEASON_CACHE = {}


def compute_multiseason_features(season, league, position, lookback=config.MULTISEASON_DEFAULT_LOOKBACK,
                                  min_minutes=config.MULTISEASON_DEFAULT_MIN_MINUTES):
    """Per-player performance time series over [season-lookback, season], keyed
    by (norm_name, birth_year). Uses league-neutral zscore_comp (not full
    composite) so moving to a stronger league doesn't fake a trajectory bump."""
    cache_key = (season, league or '_all', position, lookback, min_minutes)
    if cache_key in _MULTISEASON_CACHE:
        return _MULTISEASON_CACHE[cache_key]

    start = _season_start_year(season)
    window = [f"{y}-{y + 1}" for y in range(start - lookback, start + 1)]
    style_cats = get_playing_style_categories()

    per_player = {}
    for s in window:
        d = load_league_data(s, league) if league else load_all_leagues_data(s)
        if d.empty:
            continue
        pos_d = d[d['primary_position'] == position].copy() if 'primary_position' in d.columns else d.copy()
        if 'minutes' in pos_d.columns:
            pos_d = pos_d[_num_series(pos_d['minutes']).fillna(0) >= min_minutes]
        if pos_d.empty:
            continue
        pos_d = calculate_composite_index(pos_d, position, style_cats)
        si = _season_start_year(s)
        for _, r in pos_d.iterrows():
            by = int(safe_float(r.get('birth_year', 0)))
            if by <= 0:
                continue
            key = (_norm_key(str(r.get('player', ''))), by)
            per_player.setdefault(key, []).append({
                'season': s, 'idx': si,
                'name': str(r.get('player', '')),
                'score': safe_float(r.get('zscore_comp', 0)),
                'minutes': safe_float(r.get('minutes', 0)),
            })

    feats = {}
    for key, hist in per_player.items():
        hist = sorted(hist, key=lambda x: x['idx'])
        scores = [h['score'] for h in hist]
        idxs = [h['idx'] for h in hist]
        mins = [h['minutes'] for h in hist]
        n = len(hist)
        slope = float(np.polyfit(idxs, scores, 1)[0]) if n >= 2 else 0.0
        min_slope = float(np.polyfit(idxs, mins, 1)[0]) if n >= 2 else 0.0
        consistency = float(np.std(scores)) if n >= 2 else 0.0
        latest = scores[-1]
        prior_avg = (sum(scores[:-1]) / (n - 1)) if n >= 2 else latest
        feats[key] = {
            'player': hist[-1]['name'],
            'seasons_tracked': n,
            'series': [{'season': h['season'], 'score': round(h['score'], 1), 'minutes': int(round(h['minutes']))} for h in hist],
            'trajectory_slope': round(slope, 2),
            'consistency_std': round(consistency, 2),
            'peak': round(max(scores), 1),
            'latest': round(latest, 1),
            'breakout': bool(n >= 2 and (latest - prior_avg) >= config.BREAKOUT_SCORE_DELTA),
            'minutes_slope': round(min_slope, 1),
        }
    _MULTISEASON_CACHE[cache_key] = feats
    return feats


# Pure volume metrics: summed across seasons (totals), never turned into a rate.
_VOLUME_METRICS = {
    'minutes', 'gk_minutes', 'games', 'games_starts', 'gk_games', 'gk_games_starts',
}

def _is_rate_metric(m):
    """A metric already expressed as a rate/ratio (per-90, percentage, average,
    per-game). These are blended with a minutes-weighted average; everything
    else is a counting total and gets converted to a true per-90."""
    return (m.endswith('_per90') or m.endswith('_pct') or '_avg' in m
            or 'per_game' in m or m == 'points_per_game'
            or m.endswith('_per_shot_on_target_against'))


_MS_POOL_CACHE = {}
# Per-player {season: minutes} for the exact seasons that fed the blend, so the
# 'Season by season' panel reflects the SAME data the match used (position pool,
# no 270-min floor) rather than the stricter compute_multiseason_features.
_MS_SERIES_CACHE = {}

def _multiseason_pool(season, position, window):
    """Minutes-weighted average of each player's stats over the last `window`
    seasons (keyed by norm name + birth year), for the multi-season 'average
    level' similarity mode. Cached per (season, position, window)."""
    window = max(2, min(5, int(window)))
    ck = (season, position, window)
    if ck in _MS_POOL_CACHE:
        return _MS_POOL_CACHE[ck].copy()
    start = _season_start_year(season)
    win = [f"{y}-{y + 1}" for y in range(start - (window - 1), start + 1)]
    style = get_playing_style_categories()
    mset = set()
    for ms in style.get(position, {}).values():
        mset.update(ms)
    frames = []
    for s in win:
        d = load_all_leagues_data(s)
        if d.empty:
            continue
        d = position_pool(d, position)
        if d.empty:
            continue
        d = d.copy()
        d['_idx'] = _season_start_year(s)
        d['_season'] = s
        frames.append(d)
    if not frames:
        return None
    alld = pd.concat(frames, ignore_index=True, sort=False)
    metric_cols = [m for m in mset if m in alld.columns]
    if not metric_cols:
        return None
    alld['_pkey'] = alld['player'].astype(str).map(_norm_key)
    alld['_by'] = (_num_series(alld['birth_year']).fillna(0).astype(int)
                   if 'birth_year' in alld.columns else 0)
    alld['_min'] = (_num_series(alld['minutes']).fillna(0)
                    if 'minutes' in alld.columns else 0.0)
    nummat = {m: _num_series(alld[m]) for m in metric_cols}
    rows = []
    series_map = {}
    for (pk, by), g in alld.groupby(['_pkey', '_by']):
        idx = g.index
        w = alld.loc[idx, '_min'].values
        # actual minutes per season for this player (the seasons that fed the blend)
        smin = {}
        for s_, mn_ in zip(g['_season'].values, w):
            smin[s_] = smin.get(s_, 0.0) + float(mn_)
        series_map[(pk, by)] = smin
        rec = {}
        for m in metric_cols:
            vals = nummat[m].loc[idx]
            mask = vals.notna().values
            if not mask.any():
                rec[m] = np.nan
                continue
            vv = vals.values[mask]
            ww = w[mask]
            if m in _VOLUME_METRICS:
                rec[m] = float(vv.sum())                      # total (volume)
            elif _is_rate_metric(m):
                # already a rate -> minutes-weighted average across seasons
                rec[m] = float(np.average(vv, weights=ww)) if ww.sum() > 0 else float(vv.mean())
            else:
                # counting total -> true per-90 (sum of the stat / sum of 90s),
                # so the blended number reflects rate, not how much he played
                nineties = ww.sum() / 90.0
                rec[m] = float(vv.sum() / nineties) if nineties > 0 else float(vv.mean())
        latest = g.sort_values('_idx').iloc[-1]
        rec['player'] = latest.get('player', '')
        rec['team'] = latest.get('team', '')
        rec['league'] = latest.get('league', '')
        rec['age'] = latest.get('age', 0)
        rec['primary_position'] = latest.get('primary_position', position)
        rec['secondary_position'] = latest.get('secondary_position', '')
        rec['birth_year'] = by
        rec['minutes'] = float(w.sum())
        rec['seasons_count'] = int(g['_season'].nunique())
        rec['_pkey'] = pk
        rec['_by'] = by
        rows.append(rec)
    out = pd.DataFrame(rows)
    _MS_POOL_CACHE[ck] = out
    _MS_SERIES_CACHE[ck] = series_map
    return out.copy()


_GEM_KEYSET_CACHE = {}

def gem_keyset(season, position, league=None):
    """Set of (normalised name, team) for players flagged as hidden gems in
    this scope. Cached per (season, scope, position); public since
    backend/routers/players.py also calls it for membership tests."""
    ck = (season, league or '_all', position)
    if ck in _GEM_KEYSET_CACHE:
        return _GEM_KEYSET_CACHE[ck]
    req = {'season': season, 'position': position}
    if league:
        req['league'] = league
    try:
        res = cmd_get_hidden_gems(req)
        ks = {(_norm_key(str(g.get('player', ''))), str(g.get('team', '')))
              for g in res.get('gems', [])}
    except Exception:
        ks = set()
    _GEM_KEYSET_CACHE[ck] = ks
    return ks


_AVAIL_CACHE = {}

def _availability_index(season):
    """Supplementary-merged rows for a season, indexed by (name, team, league)
    so each similar player can be tagged with his contract/wage/value. Cached."""
    if season in _AVAIL_CACHE:
        return _AVAIL_CACHE[season]
    try:
        df = merge_supplementary(load_all_leagues_data(season), season)
        idx = {}
        for rec in df.to_dict('records'):
            k = (_norm_key(str(rec.get('player', ''))),
                 _norm_key(str(rec.get('team', ''))),
                 _norm_key(str(rec.get('league', ''))))
            idx[k] = rec
        _AVAIL_CACHE[season] = idx
    except Exception:
        idx = {}
        _AVAIL_CACHE[season] = idx
    return idx


def _tag_availability(sp, season, avail):
    """Attach contract months, wage, market value, release clause and an
    'opportunity' type (free / expiring / clause) to one similar-player dict."""
    rec = avail.get((_norm_key(sp['player']), _norm_key(sp['team']), _norm_key(sp['league'])))
    months = wage = mv = rc = None
    opp = None
    if rec is not None:
        months = contract_months_remaining(rec)
        try:
            w, _est = get_wage_value(rec)
            wage = r(w, 0) if w else None
        except Exception:
            wage = None
        mv = safe_float(rec.get('market_value_eur', 0)) or None
        rc = safe_float(rec.get('release_clause_eur', 0)) or None
        if months is not None and months <= config.AVAILABILITY_FREE_MAX_MONTHS:
            opp = 'free'
        elif months is not None and months <= config.AVAILABILITY_EXPIRING_MAX_MONTHS:
            opp = 'expiring'
        elif rc and rc > 0:
            opp = 'clause'
    sp['contract_months'] = months
    sp['wage'] = wage
    sp['wage_label'] = (format_eur(wage) + '/wk') if wage else None
    sp['market_value'] = r(mv, 0) if mv else None
    sp['market_value_label'] = format_eur(mv) if mv else None
    sp['release_clause'] = r(rc, 0) if rc else None
    sp['release_clause_label'] = format_eur(rc) if rc else None
    sp['opportunity'] = opp


def _trajectory_label(f):
    """Human-readable trajectory classification + one-line summary."""
    n = f['seasons_tracked']
    if n < 2:
        return 'Limited history', 'Only one tracked season - no trend yet.'
    series = f['series']
    span = f"z {series[0]['score']:.0f} → {series[-1]['score']:.0f}"
    if f['consistency_std'] > config.TRAJECTORY_VOLATILE_STD:
        return 'Volatile', f'Inconsistent across {n} seasons ({span}) - high variance, treat the latest season with caution.'
    if f['trajectory_slope'] >= config.TRAJECTORY_RISING_SLOPE:
        extra = ' Breakout - latest season well above prior form.' if f['breakout'] else ''
        return 'Rising', f'Improving across {n} seasons ({span}).{extra}'
    if f['trajectory_slope'] <= config.TRAJECTORY_DECLINING_SLOPE:
        return 'Declining', f'Trending down across {n} seasons ({span}) - possible age/role decline.'
    return 'Stable', f'Consistent across {n} seasons ({span}) - reliable, predictable level.'


def cmd_backtest_gems(req):
    """Validate the detector: flag gems in `season`, measure how they perform
    `horizon` seasons later vs. a baseline. Heavy (loads multiple seasons) -
    a deliberate study action, not part of browsing."""
    flag_season = req.get('season')
    position = req.get('position', 'FW')
    league = req.get('league')
    horizon = int(req.get('horizon', 1))
    if not flag_season:
        return {'error': 'season required'}
    start = _season_start_year(flag_season)
    outcome_season = f"{start + horizon}-{start + horizon + 1}"

    gem_req = {'season': flag_season, 'position': position}
    if league:
        gem_req['league'] = league
    gem_res = cmd_get_hidden_gems(gem_req)
    gems = gem_res.get('gems', [])
    if not gems:
        return {'error': 'no gems flagged in that season/position', 'flag_season': flag_season}
    # Split flagged gems by whether the Riser signal fired - the key
    # comparison for validating Method 7.
    riser_keys = {_norm_key(g['player']) for g in gems if g.get('methods', {}).get('riser')}
    other_keys = {_norm_key(g['player']) for g in gems if not g.get('methods', {}).get('riser')}

    feats = compute_multiseason_features(outcome_season, league, position, lookback=horizon)
    # group -> {'score':[], 'min':[], 'stayed_good':[]}
    groups = {'riser': {'s': [], 'm': [], 'g': []},
              'flagged_non_riser': {'s': [], 'm': [], 'g': []},
              'baseline': {'s': [], 'm': [], 'g': []}}
    GOOD = config.GEM_BACKTEST_GOOD_Z  # outcome z-score considered "still good"
    for (pkey, _by), f in feats.items():
        by_season = {p['season']: p for p in f['series']}
        if flag_season not in by_season or outcome_season not in by_season:
            continue
        ds = by_season[outcome_season]['score'] - by_season[flag_season]['score']
        dm = by_season[outcome_season]['minutes'] - by_season[flag_season]['minutes']
        stayed = by_season[outcome_season]['score'] >= GOOD
        g = 'riser' if pkey in riser_keys else 'flagged_non_riser' if pkey in other_keys else 'baseline'
        groups[g]['s'].append(ds); groups[g]['m'].append(dm); groups[g]['g'].append(stayed)

    def summ(d):
        s = d['s']
        if not s:
            return {'n': 0}
        return {
            'n': len(s),
            'median_score_delta': round(float(np.median(s)), 1),
            'pct_improved': round(100.0 * float(np.mean([x > 0 for x in s]))),
            'pct_stayed_good': round(100.0 * float(np.mean(d['g']))),
            'median_minutes_delta': int(round(float(np.median(d['m'])))),
        }

    return {
        'flag_season': flag_season,
        'outcome_season': outcome_season,
        'position': position,
        'league': league or 'all',
        'good_threshold_z': GOOD,
        'n_flagged_total': len(gems),
        'riser': summ(groups['riser']),
        'flagged_non_riser': summ(groups['flagged_non_riser']),
        'baseline': summ(groups['baseline']),
    }


def cmd_get_player_profile(req):
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = merge_supplementary(load_players(season, league, team), season)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    position = str(player.get('primary_position', player.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    # merge_supplementary here so the wage-percentile pool has REAL wages
    # wherever available, same as `df` above - without it, comparing this
    # player's real wage against a mostly-estimated pool inflates financial_risk.
    league_df = merge_supplementary(load_league_data(season, league), season)
    pos_df = league_df[league_df['primary_position'] == position] if 'primary_position' in league_df.columns else league_df

    style_cats = get_playing_style_categories()
    scores = calculate_category_scores(player, pos_df, style_cats, position, method='percentile', empty_as_none=True)

    # Calculate composite index (legacy formula). build_season_position_table
    # (not the bare calculate_composite_index) so the pool also carries
    # style_pctile_max/min/std for the style-spread breakdown below.
    pos_df_ci = build_season_position_table(pos_df, position, style_cats) if len(pos_df) > 1 else pos_df.assign(composite_index=None)
    # Match the specific club row, not just the name - a player with a
    # mid-season transfer has two rows in this season+league, and a name-only
    # .iloc[0] would hand both stints the same composite.
    player_ci_rows = pos_df_ci[(pos_df_ci['player'] == player_name) & (pos_df_ci['team'] == team)]
    if player_ci_rows.empty:
        player_ci_rows = pos_df_ci[pos_df_ci['player'] == player_name]
    if not player_ci_rows.empty:
        ci_row = player_ci_rows.iloc[0]
        composite = r(safe_float(ci_row.get('composite_index', 0)), 1)
        zscore_comp = r(safe_float(ci_row.get('zscore_comp', 0)), 1)
        style_pctile_avg = r(safe_float(ci_row.get('style_pctile_avg', 0)), 1)
        power_norm = r(safe_float(ci_row.get('power_norm', 0)), 1)
    else:
        ci_row = None
        _valid = [v for v in scores.values() if v is not None]
        composite = r(float(np.mean(_valid)), 1) if _valid else 0
        zscore_comp = 0
        style_pctile_avg = 0
        power_norm = 0

    # Radar data — omit categories with no measurable data in this league so the
    # radar only plots axes we can actually score (no misleading zeros).
    radar = [{'category': k, 'score': r(v, 1)} for k, v in scores.items() if v is not None]

    # Wage/contract - from player_supplementary_data via merge_supplementary()
    # above. Not every player has a verified record, so each numeric field
    # falls back to None (0.0 is falsy) rather than a misleading "€0".
    weekly_wage = safe_float(player.get('weekly_wage_eur', 0)) or None
    annual_wage = safe_float(player.get('annual_wage_eur', 0)) or None
    release_clause = safe_float(player.get('release_clause_eur', 0)) or None
    contract_expiry = player.get('contract_expiry')
    contract_signed = player.get('contract_signed')

    # Basic stats
    basic = {
        'player': player_name,
        'team': team,
        'league': league,
        'season': season,
        'position': position,
        'age': parse_age(player.get('age', 0)),
        'minutes': safe_float(player.get('minutes', 0)),
        'games': safe_float(player.get('games', safe_float(player.get('games_starts', 0)))),
        'goals': safe_float(player.get('goals', 0)),
        'assists': safe_float(player.get('assists', 0)),
        'xg': r(safe_float(player.get('xg', 0)), 2),
        'xg_assist': r(safe_float(player.get('xg_assist', 0)), 2),
        'weekly_wage_eur': weekly_wage,
        'annual_wage_eur': annual_wage,
        'weekly_wage_label': format_eur(weekly_wage) if weekly_wage else None,
        'annual_wage_label': format_eur(annual_wage) if annual_wage else None,
        'contract_expiry': str(contract_expiry) if contract_expiry is not None and str(contract_expiry) not in ('', 'nan', 'None') else None,
        'contract_signed': str(contract_signed) if contract_signed is not None and str(contract_signed) not in ('', 'nan', 'None') else None,
        'contract_months_remaining': contract_months_remaining(player.to_dict()),
        'release_clause_eur': release_clause,
        'release_clause_label': format_eur(release_clause) if release_clause else None,
    }

    # Risk assessment (backend/scoring/risk.py): four independent,
    # diagnostic reasons (contract/mileage/sell-high/financial). Needs
    # value_efficiency, career-accumulated minutes, and the prior-season row.
    player_dict = player.to_dict()
    player_dict['composite_index'] = composite

    wage, wage_est = get_wage_value(player_dict)
    wages_series = pos_df.apply(lambda row: get_wage_value(row.to_dict())[0], axis=1) if not pos_df.empty else pd.Series([500])
    wage_pctl = max(stats.percentileofscore(wages_series.dropna(), wage, kind='rank'), 1)
    value_ratio_raw = ((composite or 0) / wage_pctl) * config.VALUE_RATIO_SCALE
    player_dict['value_efficiency'] = 50.0 if wage_est else min(100, max(0, value_ratio_raw))
    player_dict['wage_is_estimated'] = wage_est

    history = load_player_history(player_name)
    career_minutes = None
    prior_row = None
    if not history.empty and 'minutes' in history.columns:
        career_minutes = float(_num_series(history['minutes']).fillna(0).sum())
        prior_season = prev_season_label(season)
        if prior_season:
            prow_prior = history[history['season'].astype(str) == str(prior_season)]
            if not prow_prior.empty:
                prior_row = prow_prior.iloc[0].to_dict()

    risk = assess_player_risk(
        player_dict, player_name, season, position, style_cats, scores,
        career_minutes=career_minutes, prior_row=prior_row, history=history,
    )

    return {
        'profile': basic,
        'radar': radar,
        'composite_index': composite,
        'composite_description': composite_description(composite),
        'zscore_comp': zscore_comp,
        'style_pctile_avg': style_pctile_avg,
        'power_norm': power_norm,
        'category_scores': {k: (r(v, 1) if v is not None else None) for k, v in scores.items()},
        'risk': risk,
    }

def cmd_get_position_benchmark(req):
    """Per-metric league leaders + the flat 50 average ring, for the Player
    Profile radar overlay. Position comes from the reference player if
    given, else an explicit `position`; computations live in backend/scoring/benchmark.py."""
    season = req.get('season')
    league = req.get('league')
    if not all([season, league]):
        return {'error': 'season, league required'}

    position = req.get('position')
    team = req.get('team')
    player_name = req.get('player')
    player_row = None
    if team and player_name:
        try:
            df = load_players(season, league, team)
            prows = df[df['player'] == player_name]
            if not prows.empty:
                player_row = prows.iloc[0]
                if not position:
                    position = str(player_row.get('primary_position', player_row.get('position', 'MF')))
        except Exception:
            player_row = None
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    league_df = load_league_data(season, league)
    pos_df = league_df[league_df['primary_position'] == position].copy() if 'primary_position' in league_df.columns else league_df.copy()
    if pos_df is None or pos_df.empty:
        return {'error': f'no {position} players for {league} {season}'}
    pos_df = pos_df.reset_index(drop=True)

    style_cats = get_playing_style_categories()
    best_block = league_best(pos_df, position, style_cats)

    return {
        'position': position,
        'league': league,
        'season': season,
        'sample_size': int(len(pos_df)),
        'league_average': 50.0,  # percentile midpoint (measured ~50.2-50.4 across the pool)
        'best': best_block,
        'category_leaders': category_leaders(pos_df, position, style_cats),
        'metric_leaders': metric_leaders(pos_df, position, player_row),
    }

def cmd_get_playing_style(req):
    """Per-category percentile/normalized breakdown, plus a strengths/
    weaknesses summary with driver metrics and generated text. Computation
    lives in backend/scoring/style_breakdown.py."""
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    position = str(player.get('primary_position', player.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    league_df = load_league_data(season, league)
    pos_df = league_df[league_df['primary_position'] == position] if 'primary_position' in league_df.columns else league_df

    style_cats = get_playing_style_categories()
    categories = category_breakdown(player, pos_df, style_cats, position)
    strengths, weaknesses = summarize_strengths_weaknesses(categories)

    return {
        'position': position,
        'categories': categories,
        'strengths': strengths,
        'weaknesses': weaknesses,
    }

def cmd_get_raw_data(req):
    """The player's full raw per-90/per-season metric set for the profile's
    Raw Data tab, grouped by their own position's style categories - a
    plain, un-scored breakdown, reusing the Similar Players raw-compare formatting."""
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    row = player_rows.iloc[0]
    position = str(row.get('primary_position', row.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    groups = _all_similar_metric_groups(position, df.columns)
    categories = []
    for g in groups:
        metrics = []
        for m in g['metrics']:
            val = _format_metric_value(m['key'], row.get(m['key']))
            metrics.append({'key': m['key'], 'label': m['label'], 'value': val if val is not None else 'N/A'})
        categories.append({'category': g['category'], 'metrics': metrics})

    return {'position': position, 'season': season, 'categories': categories}

def _gem_display_stats(row, position):
    """Position-specific stat line for a hidden gem - e.g. a keeper is
    judged on clean sheets/save %, not goals, so the evidence matches the
    position-specific detection."""
    def _missing(key):
        raw = row.get(key)
        return raw is None or (isinstance(raw, float) and pd.isna(raw)) or (
            isinstance(raw, str) and raw.strip().lower() in ('', 'nan', 'none', 'null'))

    def count(key):
        if _missing(key):
            return 'N/A'
        return str(int(round(safe_float(row.get(key, 0)))))

    def dec(key):
        if _missing(key):
            return 'N/A'
        return str(round(safe_float(row.get(key, 0)), 1))

    def pct(key):
        if _missing(key):
            return 'N/A'
        return f"{round(safe_float(row.get(key, 0)), 1)}%"

    games = int(round(safe_float(row.get('games', row.get('games_starts', 0)))))
    minutes = int(round(safe_float(row.get('minutes', 0))))
    tail = [
        {'label': 'Games', 'value': str(games)},
        {'label': 'Minutes', 'value': f"{minutes:,}"},
    ]
    if position == 'GK':
        return [
            {'label': 'Clean Sheets', 'value': str(count('gk_clean_sheets'))},
            {'label': 'Save %', 'value': pct('gk_save_pct')},
            {'label': 'Goals Against', 'value': str(count('gk_goals_against'))},
        ] + tail
    if position == 'DF':
        return [
            {'label': 'Tackles', 'value': str(count('tackles'))},
            {'label': 'Interceptions', 'value': str(count('interceptions'))},
            {'label': 'Aerials Won %', 'value': pct('aerials_won_pct')},
            {'label': 'Prog. Passes', 'value': str(count('progressive_passes'))},
        ] + tail
    if position == 'MF':
        return [
            {'label': 'Key Passes', 'value': str(count('assisted_shots'))},
            {'label': 'xA', 'value': str(dec('xg_assist'))},
            {'label': 'Prog. Passes', 'value': str(count('progressive_passes'))},
            {'label': 'Tackles', 'value': str(count('tackles'))},
        ] + tail
    # FW
    return [
        {'label': 'Goals', 'value': str(count('goals'))},
        {'label': 'Assists', 'value': str(count('assists'))},
        {'label': 'xG', 'value': str(dec('xg'))},
        {'label': 'Shots', 'value': str(count('shots'))},
    ] + tail


# Readable labels for individual metrics - used to spell out *why* a
# category is a strength or weakness ("8 yellow cards", "2 penalties missed").
METRIC_LABEL = {
    'cards_yellow': 'yellow cards', 'cards_red': 'red cards', 'cards_yellow_red': 'second-yellow reds',
    'fouls': 'fouls committed', 'fouled': 'times fouled', 'errors': 'errors leading to a shot',
    'own_goals': 'own goals', 'offsides': 'offsides', 'pens_conceded': 'penalties conceded',
    'pens_made': 'penalties scored', 'pens_att': 'penalties taken', 'pens_missed': 'penalties missed',
    'pens_won': 'penalties won', 'miscontrols': 'miscontrols', 'dispossessed': 'times dispossessed',
    'goals': 'goals', 'goals_per90': 'goals/90', 'goals_pens': 'non-penalty goals',
    'assists': 'assists', 'assists_per90': 'assists/90', 'goals_assists': 'goals + assists',
    'xg': 'xG', 'xg_per90': 'xG/90', 'npxg': 'non-penalty xG', 'npxg_per90': 'non-penalty xG/90',
    'xg_assist': 'xA', 'xg_assist_per90': 'xA/90', 'npxg_per_shot': 'non-penalty xG per shot',
    'shots': 'shots', 'shots_per90': 'shots/90', 'shots_on_target': 'shots on target',
    'shots_on_target_pct': 'shot accuracy', 'goals_per_shot': 'goals per shot',
    'average_shot_distance': 'avg shot distance', 'sca': 'shot-creating actions',
    'sca_per90': 'shot-creating actions/90', 'gca': 'goal-creating actions',
    'gca_per90': 'goal-creating actions/90', 'assisted_shots': 'key passes',
    'through_balls': 'through balls', 'progressive_passes': 'progressive passes',
    'progressive_carries': 'progressive carries', 'progressive_passes_received': 'progressive passes received',
    'passes_into_final_third': 'passes into the final third', 'passes_into_penalty_area': 'passes into the box',
    'carries_into_final_third': 'carries into the final third', 'carries_into_penalty_area': 'carries into the box',
    'tackles': 'tackles', 'tackles_won': 'tackles won', 'interceptions': 'interceptions',
    'blocks': 'blocks', 'blocked_shots': 'shots blocked', 'blocked_passes': 'passes blocked',
    'clearances': 'clearances', 'aerials_won': 'aerial duels won', 'aerials_lost': 'aerial duels lost',
    'aerials_won_pct': 'aerial win %', 'take_ons': 'take-ons attempted', 'take_ons_won': 'take-ons completed',
    'take_ons_won_pct': 'dribble success %', 'passes_pct': 'pass completion %',
    'passes_completed': 'passes completed', 'crosses_into_penalty_area': 'crosses into the box',
    'touches_att_pen_area': 'touches in the box', 'ball_recoveries': 'ball recoveries',
    'gk_saves': 'saves', 'gk_save_pct': 'save %', 'gk_clean_sheets': 'clean sheets',
    'gk_clean_sheets_pct': 'clean sheet %', 'gk_goals_against': 'goals conceded',
    'gk_goals_against_per90': 'goals conceded/90', 'gk_psxg_net': 'post-shot xG +/-',
    'gk_pens_saved': 'penalties saved', 'gk_crosses_stopped_pct': 'crosses claimed %',
    # Corner / free-kick / pass-type metrics - these are TYPES, not outcomes.
    # ("corner_kicks_in" = inswinging corners, NOT corners that went in.)
    'corner_kicks': 'corners taken', 'corner_kicks_in': 'inswinging corners',
    'corner_kicks_out': 'outswinging corners', 'corner_kicks_straight': 'straight corners',
    'passes_free_kicks': 'free-kick passes', 'shots_free_kicks': 'free-kick shots',
    'passes_switches': 'switches of play', 'crosses': 'crosses', 'misc_crosses': 'crosses',
    'passes_dead': 'dead-ball passes', 'passes_live': 'open-play passes',
    'sca_passes_live': 'open-play shot-creating passes', 'sca_passes_dead': 'dead-ball shot-creating passes',
    'sca_take_ons': 'take-ons leading to a shot', 'sca_shots': 'shots leading to another shot',
    'sca_fouled': 'fouls won leading to a shot', 'gca_passes_live': 'open-play goal-creating passes',
    'gca_passes_dead': 'dead-ball goal-creating passes', 'pass_xa': 'pass-based xA',
    'passes_total_distance': 'total pass distance', 'passes_progressive_distance': 'progressive pass distance',
    'carries': 'carries', 'carries_distance': 'carry distance', 'carries_progressive_distance': 'progressive carry distance',
}

# Role/volume descriptors - measure how OFTEN, not how WELL, so they must
# never be surfaced as the headline reason a category is a strength/weakness.
DESCRIPTOR_METRICS = {
    'corner_kicks', 'corner_kicks_in', 'corner_kicks_out', 'corner_kicks_straight',
    'passes_free_kicks', 'shots_free_kicks', 'passes_switches', 'passes_dead', 'passes_live',
    'crosses', 'misc_crosses', 'passes_total_distance', 'passes_progressive_distance',
    'carries', 'carries_distance', 'carries_progressive_distance', 'touches',
    'touches_def_pen_area', 'touches_def_3rd', 'touches_mid_3rd', 'touches_att_3rd',
    'touches_live_ball', 'passes_received', 'gk_passes', 'gk_passes_throws',
    'gk_passes_launched', 'gk_goal_kicks', 'gk_passes_completed_launched',
    # availability / volume / team-outcome - not individual quality signals
    'minutes', 'gk_minutes', 'minutes_per_game', 'games', 'games_starts',
    'gk_games', 'gk_games_starts', 'gk_wins', 'gk_ties', 'gk_losses',
    'points_per_game', 'on_goals_against', 'on_goals_for',
}

# Pretty league names for the data-coverage note.
LEAGUE_LABEL = {
    'efl-championship': 'the EFL Championship', 'serie-b': 'Serie B',
    'eredivisie': 'the Eredivisie', 'belgian-pro-league': 'the Belgian Pro League',
    'primeira-liga': 'the Primeira Liga', 'brasileirao': 'the Brasileirão',
    'liga-profesional-argentina': 'Liga Profesional Argentina', 'liga-mx': 'Liga MX',
    'major-league-soccer': 'MLS', 'premier-league': 'the Premier League',
    'la-liga': 'La Liga', 'serie-a': 'Serie A', 'bundesliga': 'the Bundesliga', 'ligue-1': 'Ligue 1',
}


def _metric_label(m):
    if m in METRIC_LABEL:
        return METRIC_LABEL[m]
    label = m[3:] if m.startswith('gk_') else m
    label = label.replace('_per90', '/90').replace('_pct', ' %').replace('_', ' ')
    return label.strip()


def _format_metric_value(m, raw, per90=False):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or (isinstance(raw, str) and raw.strip().lower() in ('', 'nan', 'none')):
        return None
    try:
        v = float(str(raw).replace(',', ''))
    except (ValueError, TypeError):
        return None
    if m.endswith('_pct') or m == 'aerials_won_pct':
        return f"{v:.1f}%"
    if m.endswith('_per90'):
        return f"{v:.2f}/90"
    # In multi-season mode counting stats are stored as a per-90 rate (see
    # _multiseason_pool), so label them as such instead of as a raw count.
    if per90 and not _is_rate_metric(m) and m not in _VOLUME_METRICS:
        return f"{v:.2f}/90"
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.1f}"


def _league_label(slug):
    return LEAGUE_LABEL.get(slug, slug.replace('-', ' ').title())


# Headline stats shown in the Similar Players table, by position. Goals/assists
# are meaningless for a keeper, so each position gets the three stats that
# actually describe it.
SIMILAR_STAT_KEYS = {
    'GK': [('Clean Sheets', 'gk_clean_sheets'), ('Save %', 'gk_save_pct'), ('Goals Against', 'gk_goals_against')],
    'DF': [('Tackles', 'tackles'), ('Interceptions', 'interceptions'), ('Aerials %', 'aerials_won_pct')],
    'MF': [('Goals', 'goals'), ('xA', 'xg_assist'), ('xG', 'xg')],
    'FW': [('Goals', 'goals'), ('Assists', 'assists'), ('xG', 'xg')],
}


def _similar_stats(row, position, per90=False):
    keys = SIMILAR_STAT_KEYS.get(position, SIMILAR_STAT_KEYS['FW'])
    out = []
    for label, k in keys:
        val = _format_metric_value(k, row.get(k), per90=per90)
        out.append({'label': label, 'value': val if val is not None else 'N/A'})
    return out

def _all_similar_metric_keys(position, columns):
    """Ordered unique list of a position's style-category metrics present in the
    data - the full set the Similar Players 'metric' dropdown offers."""
    cats = get_playing_style_categories().get(position, {})
    keys = []
    for metrics in cats.values():
        for m in metrics:
            if m in columns and m not in keys:
                keys.append(m)
    return keys

def _all_similar_stats(row, keys, per90=False):
    """Formatted value for every metric, keyed by column name."""
    out = {}
    for k in keys:
        v = _format_metric_value(k, row.get(k), per90=per90)
        out[k] = v if v is not None else 'N/A'
    return out

def _fmt_diff(d):
    """Signed, tidily-rounded difference for the comparison popup."""
    ad = abs(d)
    s = f'{d:.0f}' if ad >= 100 else (f'{d:.1f}' if ad >= 10 else f'{d:.2f}')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return ('+' + s) if d >= 0 and not s.startswith('-') else s

def _compare_metrics(cand_row, target_row, keys, per90=False):
    """Per-metric candidate value, target value, their difference (target
    minus candidate), and who's better on it - direction-aware (lower is
    better for negative metrics). Missing candidate data returns 'N/A'."""
    neg = get_negative_metrics()
    out = {}
    for k in keys:
        c_raw = cand_row.get(k)
        t_raw = target_row.get(k) if target_row is not None else None
        cv = _format_metric_value(k, c_raw, per90=per90)
        tv = _format_metric_value(k, t_raw, per90=per90)
        cnum = _num_series(pd.Series([c_raw]))[0]
        tnum = _num_series(pd.Series([t_raw]))[0]
        diff = None
        better = None
        if not pd.isna(cnum) and not pd.isna(tnum):
            d = float(tnum) - float(cnum)
            diff = _fmt_diff(d)
            if d == 0:
                better = 'tie'
            elif k in neg:
                better = 'player' if d > 0 else 'target'
            else:
                better = 'target' if d > 0 else 'player'
        out[k] = {
            'value': cv if cv is not None else 'N/A',
            'target': tv if tv is not None else 'N/A',
            'diff': diff,
            'better': better,
        }
    return out

def _all_similar_metric_groups(position, columns):
    """The position's style categories with their metrics, for the
    per-player 'all data points' popup - each metric carries its raw
    column key plus a plain-English label, since the frontend lacks METRIC_LABEL."""
    cats = get_playing_style_categories().get(position, {})
    groups = []
    for cat, metrics in cats.items():
        present = [m for m in metrics if m in columns]
        if present:
            groups.append({
                'category': cat,
                'metrics': [{'key': m, 'label': _metric_label(m)} for m in present],
            })
    return groups


# Plain-English labels for each style category - turns jargon like
# "Progressive Play & Build-Up" into something any reader understands.
CATEGORY_PLAIN = {
    # GK
    'Shot Stopping & Saves': 'shot-stopping',
    'Post-Shot xG & Advanced': 'beating the quality of shots faced (post-shot xG)',
    'Distribution & Passing': 'distribution and passing',
    'Goal Kicks & Long Distribution': 'long distribution',
    'Sweeping & Modern Play': 'sweeping behind the defence',
    'Penalties & Set Pieces': 'penalty and set-piece situations',
    'Expected Goals (xG) Conceded': 'limiting the quality of chances conceded',
    'Command & Presence': 'command of his area and availability',
    # DF
    'Defensive Actions & Tackles': 'tackling',
    'Interceptions & Blocks': 'interceptions and blocks',
    'Aerial Duels & Physical': 'aerial duels',
    'Ball Playing & Passing': 'ball-playing and passing',
    'Progressive Play & Build-Up': 'ball progression from the back',
    'Dribbling & Take-Ons': 'dribbling',
    'Attacking Contribution': 'attacking output (goals and assists)',
    'Expected Goals (xG) & xA': 'chance quality created and taken',
    'Crosses & Set Pieces': 'crossing and set pieces',
    'Touches & Ball Control': 'ball retention',
    'Discipline & Errors': 'discipline (avoiding errors)',
    # MF
    'Creativity & Chance Creation': 'chance creation',
    'Expected Assists (xA)': 'high-quality chance creation (xA)',
    'Passing & Distribution': 'passing and distribution',
    'Final Third & Penetration': 'penetrating final-third passing',
    'Ball Carrying & Progressive Play': 'ball carrying and progression',
    'Goal Threat & Shooting': 'goal threat and shooting',
    'Expected Goals (xG)': 'getting into shooting positions (xG)',
    'Defensive Contribution': 'defensive contribution',
    'Aerial & Physical Duels': 'aerial and physical duels',
    'Touches & Positioning': 'involvement and positioning',
    'Discipline & Game Management': 'discipline and game management',
    # FW
    'Finishing & Clinical': 'clinical finishing',
    'Expected Goals (xG) & Efficiency': 'getting into scoring positions (xG)',
    'Creativity & Assists': 'creativity and assists',
    'Dribbling & 1v1 Skills': '1v1 dribbling',
    'Ball Control & Touch': 'ball control and link play',
    'Progressive Play & Carries': 'carrying the ball into dangerous areas',
    'Aerial & Heading': 'aerial duels and heading',
    'Link-Up & Passing': 'link-up play and passing',
    'Defensive Work': 'pressing and defensive work',
    'Discipline': 'discipline',
}

POSITION_WORD = {'GK': 'goalkeeper', 'DF': 'defender', 'MF': 'midfielder', 'FW': 'forward'}


def _ordinal(n):
    n = int(round(n))
    if 10 <= (n % 100) <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def _season_short(season):
    s = str(season)
    if '-' in s:
        a, b = s.split('-', 1)
        return f"{a}-{b[-2:]}" if len(b) >= 2 else s
    return s


def build_verdict(player, position, age, team, season, league, methods_triggered,
                  top_cats, bottom_cats, value_ratio, wage_pctl,
                  mv_label, mv_estimated, contract_months, anomaly,
                  present_cats, total_cats, goals, xg_missing, shots_missing, minutes,
                  traj=None, release_clause=0.0, assists=0.0):
    """Plain-English scouting verdict assembled from the computed signals."""
    pos_word = POSITION_WORD.get(position, 'player')

    if methods_triggered >= 5:
        tier, headline = 'Strong Signal', 'A priority target - act quickly.'
    elif methods_triggered == 4:
        tier, headline = 'Good Signal', 'Worth a closer look.'
    elif methods_triggered == 3:
        tier, headline = 'Worth Monitoring', 'Keep on the watchlist.'
    else:
        tier, headline = 'Weak Signal', 'Track, but no rush.'

    summary = (f"{player} is a {age}-year-old {pos_word} at {team} ({_season_short(season)}), "
               f"flagged by {methods_triggered} of 7 detection methods.")

    def driver_str(c):
        drivers = c.get('drivers') or []
        if not drivers:
            return ''
        return ' - ' + ', '.join(f"{d['label']}: {d['value']}" for d in drivers)

    def strength_text(c):
        p = c['percentile']
        plain = CATEGORY_PLAIN.get(c['category'], c['category'].lower())
        band = 'Elite' if p >= 85 else 'Strong' if p >= 70 else 'Solid' if p >= 55 else 'Around average'
        return f"{band} at {plain} ({_ordinal(p)} percentile){driver_str(c)}."

    def weakness_text(c):
        p = c['percentile']
        plain = CATEGORY_PLAIN.get(c['category'], c['category'].lower())
        band = 'Weak' if p <= 25 else 'Below par' if p <= 40 else 'Room to improve'
        return f"{band} at {plain} ({_ordinal(p)} percentile){driver_str(c)}."

    strengths = [{'category': c['category'], 'percentile': c['percentile'], 'drivers': c.get('drivers', []), 'text': strength_text(c)} for c in top_cats]
    weaknesses = [{'category': c['category'], 'percentile': c['percentile'], 'drivers': c.get('drivers', []), 'text': weakness_text(c)} for c in bottom_cats]

    # Data-coverage honesty: when most style categories have no data
    # (e.g. a forward in a league with no shot/xG data), say so plainly
    # and temper the headline rather than calling a data-starved player elite.
    coverage = (present_cats / total_cats) if total_cats else 0.0
    data_note = None
    if coverage < 0.5:
        missing_bits = []
        if xg_missing:
            missing_bits.append('xG')
        if shots_missing:
            missing_bits.append('shots')
        missing_str = ' and '.join(missing_bits) if missing_bits else 'several advanced metrics'
        note = (f"Heads up: {missing_str} read zero here because {_league_label(league)} doesn't carry "
                f"advanced shot data - those aren't real zeros. ")
        if goals and goals > 0:
            note += f"He still scored {int(goals)} in {int(minutes)} minutes, so the flag rests on basic output plus league strength, "
        else:
            note += "so the flag rests on basic output plus league strength, "
        note += (f"with only {present_cats} of {total_cats} style categories carrying enough data to score. "
                 f"Lean on video over the model here, and treat the headline tier with caution.")
        data_note = note
        headline = 'Promising on basic stats - but limited data to confirm.'

    wage_band = 'bottom 30%' if wage_pctl <= 30 else 'lower half' if wage_pctl <= 50 else 'upper half'
    if value_ratio > 120:
        assess = 'exceptional value for money'
    elif value_ratio > 80:
        assess = 'strong value'
    elif value_ratio > 60:
        assess = 'good value'
    else:
        assess = 'fair value'
    value_note = (f"Estimated {mv_label}, with a wage in the {wage_band} for his position"
                  f" - value ratio {value_ratio:.0f}, {assess}.")

    contract_note = None
    if contract_months is not None:
        if contract_months <= 0:
            cn = 'is out of contract - available as a free agent.'
        elif contract_months <= 6:
            cn = 'has under 6 months left - could be signed cheaply or pre-agreed.'
        elif contract_months <= 12:
            cn = 'is in the final year of his contract - negotiate before he can leave on a free.'
        elif contract_months <= 18:
            cn = 'has 18 months or less remaining - a clear window to sign before the price climbs.'
        elif contract_months <= 24:
            cn = 'has around two years left - still time to negotiate from strength.'
        else:
            cn = 'has a long contract remaining - any deal would command a premium.'
        contract_note = f"{age} years old and {cn}"

    # Age horizon + profile type - a hidden gem can be a development
    # prospect (young, future resale) or a short-term value play (a cheap
    # veteran still performing). Make the value window explicit by age.
    if age <= 20:
        age_horizon = 'Long runway - primary value is development and future resale.'
        profile_type = 'Development Prospect'
    elif age <= 23:
        age_horizon = 'Prime potential - peak upside and resale value (the classic hidden-gem age).'
        profile_type = 'Development Prospect'
    elif age <= 26:
        age_horizon = 'Approaching prime - immediate quality with solid resale value.'
        profile_type = 'Prime Performer'
    elif age <= 29:
        age_horizon = 'In his prime - buy for impact; resale window still decent.'
        profile_type = 'Prime Performer'
    elif age <= 32:
        age_horizon = 'Experienced - immediate impact, but a 2-3 year window and fading resale.'
        profile_type = 'Short-Term Value'
    else:
        age_horizon = 'Veteran - short-term squad value only; minimal resale, expect 1-2 useful seasons.'
        profile_type = 'Short-Term Value'

    veteran = age >= 30
    weak_area = CATEGORY_PLAIN.get(bottom_cats[0]['category'], 'his weaker areas') if bottom_cats else 'his weaker areas'
    if methods_triggered >= 4:
        if veteran:
            recommendation = (f"Request video footage focused on {weak_area}. A low-cost, ready-now option for "
                              f"immediate squad depth rather than a long-term project - pursue only if the short-term value fits the plan.")
        else:
            recommendation = (f"Request video footage focused on {weak_area}, and schedule a live scout "
                              f"for his next 3 matches.")
    elif methods_triggered == 3:
        if veteran:
            recommendation = 'Shortlist as a short-term value / squad-depth option; review recent highlights before committing.'
        else:
            recommendation = 'Add to the shortlist and review highlights over the next few matches.'
    else:
        recommendation = 'Log for tracking; revisit if his minutes or output rise.'

    # Output framing (data-derived): goals/assists over the minutes played.
    output_note = None
    if minutes > 0:
        per90 = 90.0 / minutes
        ga = (goals + assists)
        output_note = (f"Output: {int(goals)} goals, {int(assists)} assists in {int(minutes)} minutes "
                       f"({ga * per90:.2f} goal involvements per 90).")

    # Trajectory signal (multi-season), if we have it.
    trajectory_note = None
    if traj and traj.get('seasons_tracked', 0) >= 2:
        _lab, _summ = _trajectory_label(traj)
        trajectory_note = f"Trajectory signal: {_summ}"
        if traj.get('minutes_slope', 0) > 50:
            trajectory_note += ' Minutes are trending up - the club is leaning on him more.'
        elif traj.get('minutes_slope', 0) < -50:
            trajectory_note += ' Minutes are trending down.'

    # Release-clause framing - what the parent club thinks vs the open market.
    clause_note = None
    if release_clause and release_clause > 0:
        clause_note = (f"Release clause {format_eur(release_clause)} - the parent club's ceiling, "
                       f"against an estimated market value of {mv_label}. A wide gap is itself a signal.")

    caveats = []
    if mv_estimated:
        caveats.append('Market value is estimated, not an actual transfer figure.')
    if minutes and minutes < 900:
        caveats.append(f'Small sample ({int(minutes)} min) - per-90 rates are noisy; weight career history and video.')
    if anomaly:
        caveats.append('Elite across multiple categories - strong fit for a specialist role.')

    return {
        'tier': tier,
        'headline': headline,
        'summary': summary,
        'profile_type': profile_type,
        'age_horizon': age_horizon,
        'output_note': output_note,
        'trajectory_note': trajectory_note,
        'clause_note': clause_note,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'value_note': value_note,
        'contract_note': contract_note,
        'recommendation': recommendation,
        'caveats': caveats,
        'data_note': data_note,
        'coverage': round(coverage, 2),
    }


def cmd_get_hidden_gems(req):
    season = req.get('season')
    league = req.get('league')
    leagues = req.get('leagues')  # optional list of league slugs (multi-select)
    position = req.get('position', 'MF')
    use_trajectory = req.get('use_trajectory', True)
    mv_method = 'heuristic'  # heuristic-only valuation (single, readable formula)
    # Analyst-set ceiling: any player whose market value (real OR estimated via
    # the selected method) is at/above this can't be a "hidden gem". Default 40M.
    try:
        mv_ceiling = float(req.get('mv_ceiling', config.GEM_MV_CEILING_DEFAULT)) or config.GEM_MV_CEILING_DEFAULT
    except (TypeError, ValueError):
        mv_ceiling = config.GEM_MV_CEILING_DEFAULT
    if not season:
        return {'error': 'season required'}

    if leagues:
        df = load_all_leagues_data(season)
        if not df.empty and 'league' in df.columns:
            df = df[df['league'].isin(leagues)].copy()
    elif league:
        df = load_league_data(season, league)
    else:
        df = load_all_leagues_data(season)

    if df.empty:
        return {'gems': [], 'total': 0}

    # Merge supplementary data (wages, market values, contracts)
    df = merge_supplementary(df, season)

    pos_df = df[df['primary_position'] == position].copy() if 'primary_position' in df.columns else df.copy()
    if pos_df.empty:
        return {'gems': [], 'total': 0}

    # Minimum-minutes filter - small samples produce noise (inflated
    # composite, blown-up z-scores, exploded value ratios). Drop them
    # before any percentile/z math runs.
    min_minutes_for_gem = config.GEM_MIN_MINUTES.get(position, config.GEM_MIN_MINUTES_DEFAULT)
    if 'minutes' in pos_df.columns:
        mins_col = _num_series(pos_df['minutes']).fillna(0)
        pos_df = pos_df[mins_col >= min_minutes_for_gem].copy()
    if pos_df.empty:
        return {'gems': [], 'total': 0, 'min_minutes': min_minutes_for_gem}

    style_cats = get_playing_style_categories()
    neg_metrics = get_negative_metrics()

    # Calculate composite index vectorized (legacy formula)
    pos_df = calculate_composite_index(pos_df, position, style_cats)

    # Multi-season trajectory (cached), powers Method 7 (Riser). Leak-free
    # (only uses seasons up to `season`); spans leagues since identity is
    # by name + birth_year.
    traj_league = None if leagues else league
    traj_feats = compute_multiseason_features(season, traj_league, position) if use_trajectory else {}

    # Pre-compute wages for percentile
    wages = pos_df.apply(lambda r2: get_wage_value(r2.to_dict())[0], axis=1)

    # Composite z-score stats (for z-score detection method)
    ci_mean = pos_df['composite_index'].mean()
    ci_std = pos_df['composite_index'].std()
    position_pool_size = int(len(pos_df))

    # Pre-compute per-player category percentile ranks for Method 6 (Statistical Anomaly)
    # Coverage-aware: players missing >50% of a category's metrics get
    # NaN for that category, so they can't trigger an anomaly on hollow data.
    position_cats = style_cats.get(position, {})
    cat_pctile_cols = {}
    cat_metric_pctiles = {}  # {category: {metric: directional pctile Series}} - for driver callouts
    total_cats = 0
    for cat_name, cat_metrics in position_cats.items():
        avail = [m for m in cat_metrics if m in pos_df.columns]
        if not avail:
            continue
        total_cats += 1
        cat_pctile_sum = pd.Series(0.0, index=pos_df.index)
        cat_pctile_present = pd.Series(0, index=pos_df.index)
        metric_pcts = {}
        for m in avail:
            col = _num_series(pos_df[m])
            pctile = col.rank(pct=True, na_option='keep') * 100
            if m in neg_metrics:
                pctile = 100 - pctile
            non_null = ~pctile.isna()
            cat_pctile_sum += pctile.fillna(0)
            cat_pctile_present += non_null.astype(int)
            metric_pcts[m] = pctile
        cat_metric_pctiles[cat_name] = metric_pcts
        coverage_threshold = max(1, len(avail) // config.CATEGORY_COVERAGE_DIVISOR)
        cat_avg = cat_pctile_sum / cat_pctile_present.replace(0, 1)
        cat_pctile_cols[cat_name] = cat_avg.where(cat_pctile_present >= coverage_threshold, np.nan)

    def _category_drivers(cat_name, idx, want_low):
        """Top 2 metrics driving a category up (strength) or down (weakness)."""
        metric_pcts = cat_metric_pctiles.get(cat_name, {})
        items = []
        for m, pser in metric_pcts.items():
            if m in DESCRIPTOR_METRICS:
                continue
            v = pser.get(idx, np.nan)
            if pd.notna(v):
                items.append((m, float(v)))
        items.sort(key=lambda x: x[1], reverse=not want_low)
        drivers = []
        seen_labels = set()
        for m, _pct in items:
            if len(drivers) >= 2:
                break
            label = _metric_label(m)
            if label in seen_labels:
                continue
            val = _format_metric_value(m, pos_df.at[idx, m])
            if val is not None:
                seen_labels.add(label)
                drivers.append({'label': label, 'value': val})
        return drivers

    results = []
    for idx, row in pos_df.iterrows():
        composite = safe_float(row.get('composite_index', 0))
        age = parse_age(row.get('age', 25))
        mv, mv_est = get_market_value(row.to_dict(), method=mv_method)
        wage, wage_est = get_wage_value(row.to_dict())

        # Riser (Method 7): improving across seasons - the other 6 methods
        # favor peak players who regress to the mean. Computed here since
        # trajectory labelling hasn't moved into backend/scoring/.
        _by = int(safe_float(row.get('birth_year', 0)))
        _tf = traj_feats.get((_norm_key(str(row.get('player', ''))), _by)) if _by > 0 else None
        riser = bool(_tf and _trajectory_label(_tf)[0] == 'Rising')

        gem = detect_gem(row.to_dict(), idx, composite, ci_mean, ci_std, age, wage, wage_est,
                          wages, mv, mv_ceiling, cat_pctile_cols, riser)
        pctl_outlier = gem['methods']['percentile_outlier']
        z_outlier = gem['methods']['z_score_outlier']
        value_gem = gem['methods']['value_ratio']
        age_gem = gem['methods']['age_weighted']
        composite_gem = gem['methods']['composite_score']
        anomaly = gem['methods']['statistical_anomaly']
        gem_methods = gem['gem_methods']
        wage_pctl = gem['wage_pctl']
        z_score = gem['z_score']
        value_ratio = gem['value_ratio']
        age_potential = gem['age_potential']
        moneyball = gem['moneyball_score']

        if gem['qualifies']:
            # Per-player category percentiles (skip NaN = insufficient coverage)
            player_cats = []
            for cn, cs in cat_pctile_cols.items():
                v = cs.get(idx, np.nan)
                if pd.notna(v):
                    player_cats.append({'category': cn, 'percentile': int(round(float(v)))})

            # Coverage gate: a player with zero scoring categories has a
            # composite propped up only by league power + a neutral fallback -
            # meaningless, so exclude outright rather than flag noise.
            if not player_cats:
                continue

            player_cats.sort(key=lambda c: c['percentile'], reverse=True)
            top_cats_list = player_cats[:3]
            bottom_cats_list = list(reversed(player_cats[-3:])) if len(player_cats) >= 3 else list(reversed(player_cats))
            anomaly_cats_list = [c for c in player_cats if c['percentile'] > config.GEM_ANOMALY_PERCENTILE]
            for c in top_cats_list:
                c['drivers'] = _category_drivers(c['category'], idx, want_low=False)
            for c in bottom_cats_list:
                c['drivers'] = _category_drivers(c['category'], idx, want_low=True)

            present_cats = len(player_cats)
            goals_val = safe_float(row.get('goals', 0))

            def _raw_missing(key):
                raw = row.get(key)
                return raw is None or (isinstance(raw, float) and pd.isna(raw))
            xg_missing = _raw_missing('xg')
            shots_missing = _raw_missing('shots')

            contract_months = contract_months_remaining(row.to_dict())
            verdict = build_verdict(
                str(row.get('player', '')), position, age, str(row.get('team', '')),
                season, str(row.get('league', '')), gem_methods,
                top_cats_list, bottom_cats_list, value_ratio, wage_pctl,
                format_eur(mv), mv_est, contract_months, anomaly,
                present_cats, total_cats, goals_val, xg_missing, shots_missing,
                safe_float(row.get('minutes', 0)),
                traj=_tf, release_clause=safe_float(row.get('release_clause_eur', 0)),
                assists=safe_float(row.get('assists', 0)),
            )

            # Output-per-EUR-M: production (xG+xA) per million of market value - the
            # model-free 'value residual' quick check (higher = more output per euro).
            _out = (safe_float(row.get('xg', 0)) or 0.0) + (safe_float(row.get('xg_assist', 0)) or 0.0)
            _mvm = (mv or 0) / 1e6
            output_per_mv = round(_out / _mvm, 2) if (_mvm >= 0.5 and _out > 0) else None
            # Model's performance-predicted price + the value residual (actual -
            # predicted, EUR M). Residual only meaningful against a REAL price;
            # negative = market underpays for his output = a gem.
            _pred = predict_mv_from_performance(row.to_dict(), mv_method)
            predicted_value = r(_pred, 0) if (_pred and _pred > 0) else None
            predicted_value_label = format_eur(_pred) if (_pred and _pred > 0) else None
            value_residual = None
            if not mv_est and mv and mv > 0 and _pred and _pred > 0:
                value_residual = round((mv - _pred) / 1e6, 1)
            results.append({
                'output_per_mv': output_per_mv,
                'value_residual': value_residual,
                'predicted_value': predicted_value,
                'predicted_value_label': predicted_value_label,
                'player': row.get('player', ''),
                'team': str(row.get('team', '')),
                'league': str(row.get('league', '')),
                'age': age,
                'position': position,
                'composite': r(composite, 1),
                'market_value': r(mv, 0),
                'market_value_label': format_eur(mv),
                'mv_estimated': mv_est,
                'wage': r(wage, 0),
                'wage_label': format_eur(wage) + '/wk',
                'wage_estimated': wage_est,
                'moneyball_score': r(moneyball, 1),
                'z_score': r(z_score, 2),
                'value_ratio': r(value_ratio, 1),
                'age_potential': r(age_potential, 1),
                'methods_triggered': gem_methods,
                'methods': {
                    'percentile_outlier': pctl_outlier,
                    'z_score_outlier': z_outlier,
                    'value_ratio': value_gem,
                    'age_weighted': age_gem,
                    'composite_score': composite_gem,
                    'statistical_anomaly': anomaly,
                    'riser': riser,
                },
                'goals': safe_float(row.get('goals', 0)),
                'assists': safe_float(row.get('assists', 0)),
                'minutes': safe_float(row.get('minutes', 0)),
                'games': int(round(safe_float(row.get('games', row.get('games_starts', 0))))),
                'games_starts': int(round(safe_float(row.get('games_starts', 0)))),
                'display_stats': _gem_display_stats(row, position),
                'composite_components': {
                    'z_aggregate': safe_float(row.get('zscore_comp', 0)),
                    'style_pctile': safe_float(row.get('style_pctile_avg', 0)),
                    'league_power': safe_float(row.get('power_norm', 0)),
                },
                'top_categories': top_cats_list,
                'bottom_categories': bottom_cats_list,
                'anomaly_categories': anomaly_cats_list,
                'position_pool_size': position_pool_size,
                'position_mean_composite': r(ci_mean, 1),
                'position_std_composite': r(ci_std, 2),
                'wage_percentile': r(wage_pctl, 1),
                'verdict': verdict,
            })

    results.sort(key=lambda x: x['moneyball_score'], reverse=True)
    return {'gems': results[:50], 'total': len(results), 'min_minutes': min_minutes_for_gem,
            'season': season, 'mv_method': mv_method}


def cmd_get_similar_players(req):
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    # Result filters (candidate-side, applied AFTER ranking) and sort/page.
    filter_league = req.get('filter_league')
    filter_team = req.get('filter_team')
    age_min = req.get('age_min')
    age_max = req.get('age_max')
    minutes_min = req.get('minutes_min')
    minutes_max = req.get('minutes_max')
    contract_status = req.get('contract_status')
    # ml.style_clustering archetype filter - an exact label match against
    # this position group's trained archetypes (see archetype_options
    # below). Pass a label for "only players of this archetype".
    archetype = req.get('archetype')
    # Router validates this against SIMILARITY_METHODS; find_similar() also
    # falls back to DEFAULT_SIMILARITY_METHOD on an unrecognized value, so
    # an invalid method here degrades rather than errors.
    method = req.get('method') or DEFAULT_SIMILARITY_METHOD
    sort = req.get('sort') or 'match_score'
    page = max(1, int(req.get('page', 1) or 1))
    page_size = max(1, min(100, int(req.get('page_size', 20) or 20)))

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    position = str(player.get('primary_position', player.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    # Minutes filter: an unfiltered pool is full of cup cameos with noisy
    # per-90s that show up as spurious "perfect" matches. Require a real
    # sample so comparisons are credible.
    min_minutes = req.get('min_minutes', 600)
    # window > 1 -> multi-season "average level" matching; 1 -> single season.
    window = max(1, min(5, int(req.get('window', 1) or 1)))

    if window > 1:
        # Multi-season: blend each player's last `window` seasons into one
        # minutes-weighted row, then run the identical similarity pipeline.
        agg = _multiseason_pool(season, position, window)
        if agg is None or agg.empty:
            return {'similar': [], 'error': 'No multi-season data available'}
        tkey = _norm_key(player_name)
        tby = int(safe_float(player.get('birth_year', 0)))
        tmask = (agg['_pkey'] == tkey) & (agg['_by'] == tby)
        if not tmask.any():
            tmask = agg['_pkey'] == tkey  # fall back to name-only identity
        if not tmask.any():
            return {'similar': [], 'error': 'Target not found across these seasons'}
        player_ref = agg[tmask].iloc[0]
        pos_df = agg[~tmask.values].copy()
        if 'minutes' in pos_df.columns and min_minutes:
            filtered = pos_df[pos_df['minutes'] >= min_minutes]
            if len(filtered) >= 10:
                pos_df = filtered
        pos_df = pos_df.reset_index(drop=True)
    else:
        # Single season. Pool = players who play OR can play this position.
        all_df = load_all_leagues_data(season)
        pos_df = position_pool(all_df, position)
        pos_df = pos_df[~((pos_df['player'] == player_name) & (pos_df['team'] == team))]
        if pos_df.empty:
            return {'similar': []}
        if 'minutes' in pos_df.columns and min_minutes:
            mins = _num_series(pos_df['minutes']).fillna(0)
            filtered = pos_df[mins >= min_minutes]
            if len(filtered) >= 10:
                pos_df = filtered
        pos_df = pos_df.reset_index(drop=True)
        player_ref = player

    style_cats = get_playing_style_categories()

    # Distance over the position's full raw per-90 metric set, not the
    # collapsed category scores (see backend/scoring/similarity.py). pos_df
    # comes back from find_similar, possibly narrowed by its coverage guard.
    result = find_similar(pos_df, player_ref, position, style_cats, method=method)
    if result is None:
        return {'similar': [], 'error': 'Not enough metrics with data for this position'}
    pos_df = result['pos_df']
    match = result['match']
    rank_of = result['rank']
    pool_size = result['pool_size']
    method = result['method']

    # Calculate composite index for comparison pool. build_season_position_table
    # (not the bare calculate_composite_index) so the pool also carries
    # style_pctile_max/min/std for the style-spread breakdown.
    pos_df = build_season_position_table(pos_df, position, style_cats)

    # ml.style_clustering: every archetype trained for the target's position
    # group (None for GK), plus the target's own nearest-archetype
    # assignment - computed unconditionally so the response always has both.
    archetype_catalogue = style_predict.list_archetypes(position) if position != 'GK' else None
    target_archetype = None
    if archetype_catalogue:
        target_category_scores = calculate_category_scores(
            player_ref, pos_df, style_cats, position, method='percentile', empty_as_none=True,
        )
        target_archetype = style_predict.predict(target_category_scores, position, style_cats)

    # Bulk archetype label for the whole candidate pool - one vectorized
    # call, only run when the `archetype` filter was actually requested,
    # so a plain search never pays for it.
    if archetype is not None and archetype_catalogue:
        pos_df = pos_df.assign(archetype_label=style_predict.predict_bulk(pos_df, position, style_cats))

    # Hidden-gem membership, cached per league so a large pool doesn't
    # recompute it once per candidate.
    try:
        pool_gems = gem_keyset(season, position, None)
        league_gem_cache = {}
        def _is_gem(nm, tm, lg):
            if lg not in league_gem_cache:
                league_gem_cache[lg] = gem_keyset(season, position, lg)
            ident = (_norm_key(nm), tm)
            return ident in pool_gems or ident in league_gem_cache[lg]
    except Exception:
        def _is_gem(nm, tm, lg):
            return False

    try:
        avail = _availability_index(season)
    except Exception:
        avail = {}

    # Lightweight candidate record for EVERY row in the eligible pool (not
    # just a page) - filters (e.g. contract_status) and sort (e.g.
    # market_value) need to see the whole pool before pagination slices it.
    candidates = []
    for i in range(len(pos_df)):
        row = pos_df.iloc[i]
        nm = str(row.get('player', ''))
        tm = str(row.get('team', ''))
        lg = str(row.get('league', ''))
        c = {
            '_i': i,
            'player': nm,
            'team': tm,
            'league': lg,
            'age': parse_age(row.get('age', 0)),
            'minutes': safe_float(row.get('minutes', 0)),
            'composite': safe_float(row.get('composite_index', 0)),
            'match_score': float(match[i]),
            'rank': int(rank_of[i]),
            'is_gem': _is_gem(nm, tm, lg),
            'archetype_label': row.get('archetype_label') if 'archetype_label' in pos_df.columns else None,
        }
        _tag_availability(c, season, avail)
        candidates.append(c)

    def _passes(c):
        if filter_league and c['league'] != filter_league:
            return False
        if filter_team and c['team'] != filter_team:
            return False
        if archetype is not None and c['archetype_label'] != archetype:
            return False
        if age_min is not None and (c['age'] is None or c['age'] < age_min):
            return False
        if age_max is not None and (c['age'] is None or c['age'] > age_max):
            return False
        if minutes_min is not None and (c['minutes'] is None or c['minutes'] < minutes_min):
            return False
        if minutes_max is not None and (c['minutes'] is None or c['minutes'] > minutes_max):
            return False
        if contract_status and c['opportunity'] != contract_status:
            return False
        return True

    filtered = [c for c in candidates if _passes(c)]

    SORT_KEYS = {
        'match_score': (lambda c: c['match_score'], True),
        'composite': (lambda c: c['composite'] if c['composite'] is not None else -1e9, True),
        'age': (lambda c: c['age'] if c['age'] is not None else 1e9, False),
        'market_value': (lambda c: c['market_value'] if c['market_value'] is not None else -1, True),
    }
    key_fn, reverse = SORT_KEYS.get(sort, SORT_KEYS['match_score'])
    filtered.sort(key=key_fn, reverse=reverse)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start:start + page_size]

    # Full per-candidate formatting (stats, metric-by-metric comparison) only
    # for the page being returned - the ranking/filtering above already ran
    # over the whole pool, so this stays cheap regardless of pool size.
    _cols = set(pos_df.columns)
    metric_keys = _all_similar_metric_keys(position, _cols)
    metric_groups = _all_similar_metric_groups(position, _cols)
    similar = []
    for c in page_items:
        row = pos_df.iloc[c['_i']]

        sp = {
            'player': c['player'],
            'team': c['team'],
            'league': c['league'],
            'age': c['age'],
            'position': position,
            'primary_position': str(row.get('primary_position', position) or position),
            'match_score': r(c['match_score'], 1),
            'rank': c['rank'],
            'pool_size': pool_size,
            'goals': safe_float(row.get('goals', 0)),
            'assists': safe_float(row.get('assists', 0)),
            'minutes': c['minutes'],
            'seasons': int(safe_float(row.get('seasons_count', 1))) if window > 1 else 1,
            'composite': r(c['composite'], 1),
            'stats': _similar_stats(row, position, per90=(window > 1)),
            'metrics': _compare_metrics(row, player_ref, metric_keys, per90=(window > 1)),
            'is_gem': c['is_gem'],
            'archetype_label': c['archetype_label'],
            'contract_months': c['contract_months'],
            'wage': c['wage'],
            'wage_label': c['wage_label'],
            'market_value': c['market_value'],
            'market_value_label': c['market_value_label'],
            'release_clause': c['release_clause'],
            'release_clause_label': c['release_clause_label'],
            'opportunity': c['opportunity'],
        }
        similar.append(sp)

    target_summary = {
        'player': player_name,
        'team': team,
        'position': position,
        'age': parse_age(player_ref.get('age', 0)),
        'minutes': safe_float(player_ref.get('minutes', 0)),
        'seasons': int(safe_float(player_ref.get('seasons_count', 1))) if window > 1 else 1,
        'archetype_label': target_archetype['label'] if target_archetype else None,
        'archetype_cluster': target_archetype['cluster'] if target_archetype else None,
    }

    return {
        'similar': similar,
        'total': total,
        'page': page,
        'page_size': page_size,
        'method': method,
        'metrics_used': len(result['metrics_used']),
        'metric_keys': metric_keys,
        'metric_groups': metric_groups,
        'window': window,
        'min_minutes': min_minutes,
        'sort': sort,
        'archetype_options': (
            [{'position': position, 'cluster': c['cluster'], 'label': c['label']} for c in archetype_catalogue]
            if archetype_catalogue else []
        ),
        'target': target_summary,
    }


def cmd_get_career_history(req):
    """Career history across every season on file for this player, with
    composite index recomputed in each season's own league context.
    Per-season computation lives in backend/scoring/career.py."""
    player_name = req.get('player')
    if not player_name:
        return {'error': 'player required'}

    df = load_player_history(player_name)
    if df.empty:
        return {'history': [], 'player': player_name}

    style_cats = get_playing_style_categories()
    history = build_history(df, player_name, style_cats)
    return {'history': history, 'player': player_name}

def cmd_get_market_value(req):
    """Headline current_value: a verified real value wins when present, else
    the trained GBM, else the heuristic fallback. valuation_diff_eur/_pct
    (model vs. market) is populated only when method == 'verified'."""
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    player_dict = player.to_dict()

    # Merge supplementary (smart: tries player+team, then falls back to player name only)
    supp = load_supplementary(season)
    if not supp.empty:
        match = supp[(supp['player'] == player_name) & (supp['team'] == team)]
        if match.empty:
            match = supp[supp['player'] == player_name]
        if not match.empty:
            for col in ['market_value_eur', 'weekly_wage_eur', 'contract_expiry']:
                if col in match.columns:
                    player_dict[col] = match.iloc[0].get(col)

    # Build trajectory from history. Each season goes through get_market_value
    # (verified value when on file, otherwise the heuristic), on the same
    # readable, single-formula basis.
    history = load_player_history(player_name)

    # Per-season verified market values, indexed by season (preferring the
    # row whose team matches). No cross-season fallback - an old season
    # stays estimated if it has no verified value of its own.
    supp_hist = load_player_supplementary_history(player_name)
    supp_by_season = {}
    if not supp_hist.empty and 'season' in supp_hist.columns and 'market_value_eur' in supp_hist.columns:
        for _, sr in supp_hist.iterrows():
            mvv = safe_float(sr.get('market_value_eur', 0))
            if mvv > 0:
                supp_by_season.setdefault(str(sr.get('season')), []).append(
                    (_norm_key(sr.get('team', '')), mvv))

    def _real_value_for_season(s, team_hint=''):
        # team_hint is a preference, not a requirement: falls through to any
        # team's real value for the season if the exact team has none
        # (handles a mid-season transfer without losing prior valuation).
        cands = supp_by_season.get(str(s), [])
        if not cands:
            return None
        tkey = _norm_key(team_hint)
        return next((v for tk, v in cands if tk == tkey), cands[0][1])

    trajectory = []
    if not history.empty:
        for s in sorted(history['season'].unique()):
            srows = history[history['season'] == s]
            row_dict = srows.iloc[0].to_dict()
            real = _real_value_for_season(s, row_dict.get('team', ''))
            if real is not None:
                row_dict['market_value_eur'] = real
            val, is_est = get_market_value(row_dict)
            trajectory.append({
                'season': str(s),
                'age': parse_age(row_dict.get('age', 25)),
                'actual_mv': r(val, 0) if not is_est else None,
                'estimated_mv': r(val, 0) if is_est else None,
                'display_mv': r(val, 0),
                'is_estimated': is_est,
            })

    # GBM is primary; heuristic is the fallback. A verified value must come
    # from _real_value_for_season() - player_dict['market_value_eur'] can
    # silently reflect a different season via load_supplementary()'s fallback.
    real_mv = _real_value_for_season(season, team) or 0
    model_trained = mv_predict.load_model() is not None

    # prior_mv is the PRIOR season's real value (never this season's own).
    # The GBM predicts log(current_mv/prior_mv) (see ml.market_value.train),
    # so a missing prior_mv skips the GBM entirely - falls back to 'heuristic_fallback'.
    prior_season = prev_season_label(season)
    prior_mv = _real_value_for_season(prior_season, team) if prior_season else None
    has_valid_prior = prior_mv is not None and prior_mv > 0

    # prior_mv_2 (two seasons back) is optional context for GBM momentum/
    # volatility features (see ml.market_value.features.build_features).
    # Never gates whether the GBM runs - only prior_mv does that.
    prior_season_2 = prev_season_label(prior_season) if prior_season else None
    prior_mv_2 = _real_value_for_season(prior_season_2, team) if prior_season_2 else None

    ml_prediction = (mv_predict.predict(player_dict, prior_mv=prior_mv, prior_mv_2=prior_mv_2)
                      if model_trained and has_valid_prior else None)

    # How much real labeled data backs THIS prediction, not a correction to
    # it (see config.MV_PRIOR_MV_CONFIDENCE_BRACKETS). None whenever
    # ml_prediction is None.
    ml_prediction_confidence = mv_explain.prediction_confidence(prior_mv) if ml_prediction is not None else None

    if real_mv > 0:
        mv, mv_est = real_mv, False
        method, method_label = 'verified', 'Verified (on file)'
    elif model_trained and has_valid_prior:
        mv, mv_est = ml_prediction, True
        method, method_label = 'gbm', 'Trained Model (GBM)'
    elif model_trained:
        mv, mv_est = get_market_value(player_dict)
        method, method_label = 'heuristic_fallback', 'Heuristic (fallback - no prior-season value on file to anchor the model)'
    else:
        mv, mv_est = get_market_value(player_dict)
        method, method_label = 'heuristic', 'Heuristic (fallback - no trained model)'

    # Force the selected season's point to equal the headline value, so the
    # chart can never contradict it - raw history rows aren't merged with
    # supplementary verified values the way the headline is.
    cur_label = str(season)
    cur_point = {
        'actual_mv': r(mv, 0) if not mv_est else None,
        'estimated_mv': r(mv, 0) if mv_est else None,
        'display_mv': r(mv, 0),
        'is_estimated': mv_est,
    }
    matched = next((p for p in trajectory if p['season'] == cur_label), None)
    if matched is not None:
        matched.update(cur_point)
    else:
        trajectory.append({'season': cur_label,
                           'age': parse_age(player_dict.get('age', 25)),
                           **cur_point})
        trajectory.sort(key=lambda p: p['season'])

    # Valuation gap: model's estimate vs. market - only meaningful with a
    # real observed value to compare against. When method != 'verified',
    # ml_prediction already IS mv, so comparing it to itself is meaningless.
    valuation_diff_eur = None
    valuation_diff_pct = None
    if method == 'verified' and ml_prediction is not None:
        valuation_diff_eur = ml_prediction - real_mv
        valuation_diff_pct = (ml_prediction - real_mv) / real_mv * 100.0

    return {
        'player': player_name,
        'season': cur_label,
        'current_value': r(mv, 0),
        'current_value_label': format_eur(mv),
        'is_estimated': mv_est,
        'method': method,
        'method_label': method_label,
        'ml_prediction': r(ml_prediction, 0) if ml_prediction is not None else None,
        'ml_prediction_label': format_eur(ml_prediction) if ml_prediction else None,
        'ml_model_trained': model_trained,
        'ml_prediction_confidence': ml_prediction_confidence['tier'] if ml_prediction_confidence else None,
        'ml_prediction_confidence_note': ml_prediction_confidence['note'] if ml_prediction_confidence else None,
        'valuation_diff_eur': r(valuation_diff_eur, 0) if valuation_diff_eur is not None else None,
        'valuation_diff_label': _format_signed_eur(valuation_diff_eur),
        'valuation_diff_pct': round(valuation_diff_pct, 1) if valuation_diff_pct is not None else None,
        'top_contributors': mv_explain.top_contributors(),
        'trajectory': trajectory,
    }

def cmd_get_style_archetype(req):
    """Nearest style-cluster assignment (ml.style_clustering) for one
    player-season, trained per broad position group (FW/MF/DF). Unsupervised
    - see ml.style_clustering.train's docstring. GK is ineligible."""
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    position = str(player.get('primary_position', player.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'

    if position == 'GK':
        return {
            'player': player_name, 'season': season, 'position': position,
            'cluster': None, 'label': None, 'blurb': None,
            'top_categories': [], 'distance_to_centroid': None,
            'eligible': False,
            'reason': 'Goalkeepers are not covered by style-archetype clustering - '
                      'GK style categories describe a different game than outfield metrics.',
            'model_trained': style_predict.load_model('GK') is not None,
        }

    model_trained = style_predict.load_model(position) is not None

    # Same per-player pool/lookup the profile page's own style breakdown
    # (cmd_get_playing_style) uses - league_df filtered to this position,
    # percentiled within that season+league pool.
    league_df = load_league_data(season, league)
    pos_df = league_df[league_df['primary_position'] == position] if 'primary_position' in league_df.columns else league_df

    style_cats = get_playing_style_categories()
    scores = calculate_category_scores(player, pos_df, style_cats, position, method='percentile', empty_as_none=True)

    result = style_predict.predict(scores, position, style_cats) if model_trained else None
    if result is None:
        return {
            'player': player_name, 'season': season, 'position': position,
            'cluster': None, 'label': None, 'blurb': None,
            'top_categories': [], 'distance_to_centroid': None,
            'eligible': False,
            'reason': f'No trained style-cluster artifact for {position} yet - run '
                      f'scripts/retrain_style_clusters.py.' if not model_trained else
                      'Not enough style-category data on file to assign an archetype.',
            'model_trained': model_trained,
        }

    return {
        'player': player_name,
        'season': season,
        'position': position,
        'cluster': result['cluster'],
        'label': result['label'],
        'blurb': result['blurb'],
        'top_categories': result['top_categories'],
        'distance_to_centroid': result['distance_to_centroid'],
        'eligible': True,
        'model_trained': model_trained,
    }

def cmd_get_moneyball_score(req):
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    player_dict = player.to_dict()
    position = str(player.get('primary_position', player.get('position', 'MF')))

    # Merge supplementary (smart: tries player+team, then falls back to player name only)
    supp = load_supplementary(season)
    if not supp.empty:
        match = supp[(supp['player'] == player_name) & (supp['team'] == team)]
        if match.empty:
            match = supp[supp['player'] == player_name]
        if not match.empty:
            for col in ['weekly_wage_eur', 'annual_wage_eur', 'market_value_eur', 'contract_expiry', 'release_clause_eur']:
                if col in match.columns:
                    player_dict[col] = match.iloc[0].get(col)

    # Performance = full composite index (0.4 z-aggregate + 0.3 style + 0.3
    # league power) - matches the Hidden Gems detector. Plain style-category
    # average under-rates output-dominant specialists.
    league_df = load_league_data(season, league)
    league_df = merge_supplementary(league_df, season)
    pos_df = league_df[league_df['primary_position'] == position].copy() if 'primary_position' in league_df.columns else league_df.copy()
    style_cats = get_playing_style_categories()
    composite = None
    perf_zagg = perf_style = perf_power = None
    if len(pos_df) > 1:
        pos_ci = calculate_composite_index(pos_df, position, style_cats)
        crow = pos_ci[(pos_ci['player'] == player_name) & (pos_ci['team'] == team)]
        if crow.empty:
            crow = pos_ci[pos_ci['player'] == player_name]
        if not crow.empty:
            c0 = crow.iloc[0]
            composite = safe_float(c0.get('composite_index', None))
            perf_zagg = safe_float(c0.get('zscore_comp', None))
            perf_style = safe_float(c0.get('style_pctile_avg', None))
            perf_power = safe_float(c0.get('power_norm', None))
    # Fallback: style-category average if the composite couldn't be computed.
    if not composite:
        scores = calculate_category_scores(player, pos_df, style_cats, position, method='percentile')
        composite = float(np.mean(list(scores.values()))) if scores else 50

    # Value efficiency = (performance / wage percentile) x 50, capped 0-100.
    wage, wage_est = get_wage_value(player_dict)
    wages_series = pos_df.apply(lambda row: get_wage_value(row.to_dict())[0], axis=1) if not pos_df.empty else pd.Series([500])
    wage_pctl = stats.percentileofscore(wages_series.dropna(), wage, kind='rank')
    wage_pctl = max(wage_pctl, 1)
    value_ratio_raw = (composite / wage_pctl) * config.VALUE_RATIO_SCALE
    # Match the Hidden Gems detector: a value ratio is only meaningful with a
    # real wage on file - when estimated, neutralize to 50 rather than judge
    # under/overpayment on a guess.
    value_eff = 50.0 if wage_est else min(100, max(0, value_ratio_raw))

    # Contract opportunity (urgency + release-clause discount)
    contract = contract_opportunity_breakdown(player_dict)
    contract_score = contract['total']

    # Moneyball
    moneyball = calculate_moneyball(composite, value_eff, contract_score)

    method = req.get('method', 'heuristic')
    if method not in ('heuristic', 'linear', 'gbm'):
        method = 'heuristic'
    mv, mv_est = get_market_value(player_dict, method=method)

    return {
        'player': player_name,
        'position': position,
        'season': str(season),
        'moneyball_score': r(moneyball, 1),
        'performance_score': r(composite, 1),
        'perf_zaggregate': r(perf_zagg, 1) if perf_zagg is not None else None,
        'perf_style': r(perf_style, 1) if perf_style is not None else None,
        'perf_power': r(perf_power, 1) if perf_power is not None else None,
        'value_efficiency': r(value_eff, 1),
        'value_ratio_raw': r(value_ratio_raw, 1),
        'value_capped': bool(value_ratio_raw > 100),
        'wage_percentile': r(wage_pctl, 0),
        'contract_opportunity': r(contract_score, 1),
        'contract_months': contract['months'],
        'contract_urgency': contract['urgency'],
        'contract_clause': contract['clause'],
        'wage': r(wage, 0),
        'wage_label': format_eur(wage) + '/wk',
        'wage_estimated': wage_est,
        'market_value': r(mv, 0),
        'market_value_label': format_eur(mv),
        'mv_estimated': mv_est,
    }

def cmd_get_impact_score(req):
    """Impact Score: on/off-pitch team differential (backend/scoring/impact.py)
    - a structurally different signal from composite/gems/moneyball, which all
    measure individual output. Never blended into the Composite Index."""
    season = req.get('season')
    league = req.get('league')
    team = req.get('team')
    player_name = req.get('player')
    if not all([season, league, team, player_name]):
        return {'error': 'season, league, team, player required'}

    df = load_players(season, league, team)
    player_rows = df[df['player'] == player_name]
    if player_rows.empty:
        return {'error': f'Player {player_name} not found'}

    player = player_rows.iloc[0]
    position = str(player.get('primary_position', player.get('position', 'MF')))
    if position not in ['GK', 'DF', 'MF', 'FW']:
        position = 'MF'
    minutes = safe_float(player.get('minutes', 0))

    league_df = load_league_data(season, league)
    pos_df = league_df[league_df['primary_position'] == position].copy() if 'primary_position' in league_df.columns else league_df.copy()

    # Minimum-minutes filter, same convention as cmd_get_hidden_gems: drop
    # small-sample rows from the comparison pool before any percentile math
    # runs, so the pool itself is meaningful (see config.IMPACT_SCORE_MIN_MINUTES).
    min_minutes = config.IMPACT_SCORE_MIN_MINUTES.get(position, config.IMPACT_SCORE_MIN_MINUTES_DEFAULT)
    if 'minutes' in pos_df.columns:
        mins_col = _num_series(pos_df['minutes']).fillna(0)
        pos_df = pos_df[mins_col >= min_minutes].copy()

    result = impact_breakdown(player, pos_df, min_minutes, minutes)

    return {
        'player': player_name,
        'team': team,
        'league': league,
        'season': str(season),
        'position': position,
        **result,
    }

