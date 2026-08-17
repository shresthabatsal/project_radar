#!/usr/bin/env python3
"""
Position benchmark: per-metric league leaders (the "vs the league's best"
table), per-category leaders, and the league's standout performer's own
radar. Powers the Player Profile radar overlay and leader table.
"""

import os
import sys

from data.loader import safe_float

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.scoring.composite import calculate_composite_index, calculate_category_scores


# Headline output metrics per position for the "vs the league's best" table.
# (column, label, per90) - per90=True means compute value/minutes*90 (fair to
# low-minute players); already-per90 or % columns use per90=False.
POSITION_LEADER_METRICS = {
    'FW': [('goals_per90', 'Goals /90', False), ('npxg_per90', 'npxG /90', False), ('xg_assist_per90', 'xA /90', False), ('shots_on_target_per90', 'Shots on Target /90', False), ('xg_per90', 'xG /90', False), ('xgot_per90', 'xGOT /90', False)],
    'MF': [('assists_per90', 'Assists /90', False), ('xg_assist_per90', 'xA /90', False), ('xg_per90', 'xG /90', False), ('npxg_per90', 'npxG /90', False), ('shots_on_target_per90', 'Shots on Target /90', False), ('goals_per90', 'Goals /90', False)],
    'DF': [('tackles', 'Tackles /90', True), ('interceptions', 'Interceptions /90', True), ('tackles_interceptions', 'Tackles + Int /90', True), ('clearances', 'Clearances /90', True), ('ball_recoveries', 'Ball Recoveries /90', True), ('xg_assist_per90', 'xA /90', False)],
    'GK': [('gk_save_pct', 'Save %', False), ('gk_saves', 'Saves /90', True), ('gk_clean_sheets_pct', 'Clean Sheet %', False), ('gk_psxg_net_per90', 'PSxG +/- /90', False), ('gk_clean_sheets', 'Clean Sheets /90', True), ('gk_goals_against_per90', 'Goals Against /90', False)],
}


def metric_leaders(pos_df, position, player_row, min_minutes=500):
    """Per-metric league leaders: for each headline metric, the best value + who
    holds it, plus the selected player's own value. Leaders must have >= min_minutes
    so a cameo can't top a per-90 rate."""
    specs = POSITION_LEADER_METRICS.get(position, [])
    if not specs or pos_df is None or pos_df.empty:
        return []
    mins = pos_df['minutes'].apply(safe_float) if 'minutes' in pos_df.columns else None
    p_min = safe_float(player_row.get('minutes', 0)) if player_row is not None else 0
    out = []
    for col, label, per90 in specs:
        if col not in pos_df.columns:
            continue
        vals = pos_df[col].apply(safe_float)
        series = (vals / mins.replace(0, float('nan')) * 90.0) if (per90 and mins is not None) else vals
        if mins is not None:
            series = series.where(mins >= min_minutes)
        clean = series.dropna()
        if clean.empty:
            continue
        best_i = clean.idxmax()
        row = {
            'metric': label,
            'best_value': round(float(clean.loc[best_i]), 2),
            'best_player': str(pos_df.loc[best_i, 'player']) if 'player' in pos_df.columns else '',
            'best_player_team': str(pos_df.loc[best_i, 'team']) if 'team' in pos_df.columns else '',
        }
        if player_row is not None:
            pv = safe_float(player_row.get(col, 0))
            if per90 and p_min > 0:
                pv = pv / p_min * 90.0
            row['player_value'] = round(pv, 2)
        out.append(row)
    return out


def category_leaders(pos_df, position, style_cats, min_minutes=900):
    """Per-category 'league best' envelope: for each style category, the
    highest score in the pool and who owns it. Only genuine regulars
    (>= min_minutes) can hold a category."""
    if pos_df is None or pos_df.empty:
        return []
    elig = pos_df
    if 'minutes' in pos_df.columns:
        f = pos_df[pos_df['minutes'].apply(safe_float) >= min_minutes]
        if len(f) >= 5:
            elig = f
    elig = elig.reset_index(drop=True)
    best = {}  # category -> (score, player, team)
    for _, row in elig.iterrows():
        scores = calculate_category_scores(
            row, pos_df, style_cats, position, method='percentile', empty_as_none=True)
        for cat, v in scores.items():
            if v is None:
                continue
            if cat not in best or v > best[cat][0]:
                best[cat] = (v, str(row.get('player', '')), str(row.get('team', '')))
    # preserve the category order the profile radar uses
    out = []
    for cat in style_cats.get(position, {}).keys():
        if cat in best:
            sc, pl, tm = best[cat]
            out.append({'category': cat, 'score': round(sc, 1), 'player': pl, 'team': tm})
    return out


def league_best(pos_df, position, style_cats, min_minutes=900):
    """The league's standout performer (for the radar overlay), picked by
    z-score aggregate (raw output), not composite - composite can crown a
    well-rounded player over an elite scorer. None if the pool can't support it."""
    try:
        pos_df_ci = calculate_composite_index(pos_df.copy(), position, style_cats)
        if 'zscore_comp' not in pos_df_ci.columns or pos_df_ci.empty:
            return None
        elig = pos_df_ci
        if 'minutes' in pos_df_ci.columns:
            filt = pos_df_ci[pos_df_ci['minutes'].apply(safe_float) >= min_minutes]
            if not filt.empty:
                elig = filt
        elig = elig.reset_index(drop=True)
        bi = int(elig['zscore_comp'].fillna(-1).values.argmax())
        brow = elig.iloc[bi]
        bscores = calculate_category_scores(brow, pos_df, style_cats, position, method='percentile', empty_as_none=True)
        return {
            'player': str(brow.get('player', '')),
            'team': str(brow.get('team', '')),
            'zscore_comp': round(safe_float(brow.get('zscore_comp', 0)), 1),
            'radar': [{'category': k, 'score': round(v, 1)} for k, v in bscores.items() if v is not None],
        }
    except Exception:
        return None
