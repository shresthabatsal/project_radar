#!/usr/bin/env python3
"""
Composite index: the position's style categories, negative-metric
handling, and the 40% z-score / 30% style-percentile / 30% power-rating
blend every other scoring module builds on.
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from data.loader import safe_float, _num_series

# ==============================================================================
# PLAYING STYLE CATEGORIES
# ==============================================================================

# Metrics retired since FBref's Opta feed ended, leaving these with no
# free data source - stripped from style categories (cascades to composite
# index and similar-players search). Empty this set to un-retire.
RETIRED_METRICS = frozenset({
    # shot- & goal-creating actions
    'sca', 'sca_per90', 'sca_passes_live', 'sca_passes_dead', 'sca_take_ons',
    'sca_shots', 'sca_fouled', 'sca_defense',
    'gca', 'gca_per90', 'gca_passes_live', 'gca_passes_dead', 'gca_take_ons',
    'gca_shots', 'gca_fouled', 'gca_defense', 'shot_creating_actions_per90',
    # deep possession - progression
    'progressive_passes', 'progressive_carries', 'progressive_passes_received',
    'progressive_passes_per90', 'progressive_carries_per90',
    'passes_into_final_third', 'passes_into_penalty_area',
    'passes_into_final_third_per90', 'passes_progressive_distance',
    # deep possession - touches by zone
    'touches', 'touches_def_pen_area', 'touches_def_3rd', 'touches_mid_3rd',
    'touches_att_3rd', 'touches_att_pen_area', 'touches_att_pen_area_per90',
    'touches_live_ball',
    # deep possession - carries
    'carries', 'carries_distance', 'carries_progressive_distance',
    'carries_into_final_third', 'carries_into_penalty_area',
    # discipline counting stats FotMob has no full-season source for (fouls IS
    # backfilled from FotMob and kept; these three are not available anywhere free)
    'offsides', 'offsides_per90', 'errors', 'errors_per90',
    'own_goals', 'own_goals_per90',
})

# No free full-season source for these detail metrics (NULLed in the wide
# table by harmonize_xg.py) - excluded from the radar so it only shows
# real data. Must stay in sync with harmonize_xg.py's NULL lists.
ORPHAN_METRICS = frozenset({
    'aerials_won', 'aerials_lost', 'aerials_won_pct', 'miscontrols', 'dispossessed',
    'through_balls', 'tackles_won', 'tackles_def_3rd', 'tackles_mid_3rd', 'tackles_att_3rd',
    'challenge_tackles', 'challenge_tackles_pct', 'challenges', 'challenges_lost',
    'blocks', 'blocked_shots', 'blocked_passes', 'misc_tackles_won', 'misc_interceptions', 'misc_crosses',
    'passes', 'passes_pct', 'passes_short', 'passes_medium', 'passes_long',
    'passes_completed_short', 'passes_completed_medium', 'passes_completed_long',
    'passes_pct_short', 'passes_pct_medium', 'passes_pct_long', 'passes_total_distance',
    'passes_free_kicks', 'passes_switches', 'corner_kicks_in', 'corner_kicks_out',
    'corner_kicks_straight', 'crosses_into_penalty_area', 'take_ons', 'take_ons_tackled',
    'take_ons_tackled_pct', 'take_ons_won_pct', 'average_shot_distance', 'shots_free_kicks',
    'shot_xg', 'shot_npxg', 'fouled', 'passes_received', 'pass_xa', 'pass_xg_assist',
    'on_xg_against', 'xg_plus_minus', 'xg_plus_minus_per90',
})
ORPHAN_GK_METRICS = frozenset({
    'gk_goal_kicks', 'gk_goal_kick_length_avg', 'gk_pct_goal_kicks_launched',
    'gk_passes', 'gk_passes_throws', 'gk_passes_length_avg', 'gk_passes_launched',
    'gk_passes_completed_launched', 'gk_pct_passes_launched', 'gk_crosses_stopped',
    'gk_crosses_stopped_pct', 'gk_def_actions_outside_pen_area',
    'gk_def_actions_outside_pen_area_per90', 'gk_avg_distance_def_actions',
    'gk_shots_on_target_against', 'gk_psnpxg_per_shot_on_target_against',
    'gk_wins', 'gk_losses', 'gk_ties', 'gk_pens_att', 'gk_pens_allowed',
    'gk_pens_saved', 'gk_pens_missed', 'gk_pens_save_pct', 'gk_free_kick_goals_against',
    'gk_corner_kick_goals_against', 'points_per_game', 'on_goals_for', 'on_goals_against',
})

# Everything the radar must not use (retired + 2025-26-unavailable).
EXCLUDED_METRICS = RETIRED_METRICS | ORPHAN_METRICS | ORPHAN_GK_METRICS


def get_playing_style_categories():
    raw = {
        'GK': {
            'Shot Stopping & Saves': ['gk_saves', 'gk_save_pct', 'gk_shots_on_target_against', 'gk_goals_against', 'gk_goals_against_per90', 'gk_psnpxg_per_shot_on_target_against'],
            'Post-Shot xG & Advanced': ['gk_psxg', 'gk_psxg_net', 'gk_psxg_net_per90', 'gk_psnpxg_per_shot_on_target_against'],
            'Distribution & Passing': ['passes_completed', 'passes_pct', 'passes_completed_short', 'passes_pct_short', 'passes_completed_medium', 'passes_pct_medium', 'passes_completed_long', 'passes_pct_long', 'progressive_passes', 'pass_xa', 'gk_passes', 'gk_passes_throws', 'gk_passes_length_avg'],
            'Goal Kicks & Long Distribution': ['gk_goal_kicks', 'gk_goal_kick_length_avg', 'gk_pct_goal_kicks_launched', 'gk_passes_launched', 'gk_passes_completed_launched', 'gk_pct_passes_launched'],
            'Sweeping & Modern Play': ['gk_crosses_stopped', 'gk_crosses_stopped_pct', 'gk_def_actions_outside_pen_area', 'gk_def_actions_outside_pen_area_per90', 'gk_avg_distance_def_actions', 'touches', 'touches_def_pen_area', 'touches_def_3rd', 'touches_mid_3rd', 'touches_att_3rd', 'touches_att_pen_area', 'touches_live_ball'],
            'Penalties & Set Pieces': ['gk_pens_saved', 'gk_pens_allowed', 'gk_pens_save_pct', 'gk_pens_att', 'gk_pens_missed', 'pens_conceded', 'gk_free_kick_goals_against', 'gk_corner_kick_goals_against'],
            'Expected Goals (xG) Conceded': ['on_xg_against', 'gk_psxg_net', 'xg_plus_minus', 'xg_plus_minus_per90'],
            'Command & Presence': ['gk_clean_sheets', 'gk_clean_sheets_pct', 'gk_games', 'gk_games_starts', 'gk_minutes', 'gk_wins', 'gk_ties', 'gk_losses', 'minutes', 'minutes_per_game', 'points_per_game', 'on_goals_against', 'on_goals_for'],
        },
        'DF': {
            'Defensive Actions & Tackles': ['tackles', 'tackles_won', 'tackles_def_3rd', 'tackles_mid_3rd', 'tackles_att_3rd', 'challenge_tackles', 'challenge_tackles_pct', 'challenges', 'challenges_lost', 'tackles_interceptions', 'misc_tackles_won'],
            'Interceptions & Blocks': ['interceptions', 'blocks', 'blocked_shots', 'blocked_passes', 'clearances', 'misc_interceptions'],
            'Aerial Duels & Physical': ['aerials_won', 'aerials_lost', 'aerials_won_pct', 'fouled'],
            'Ball Playing & Passing': ['passes_completed', 'passes', 'passes_pct', 'passes_completed_short', 'passes_short', 'passes_pct_short', 'passes_completed_medium', 'passes_medium', 'passes_pct_medium', 'passes_completed_long', 'passes_long', 'passes_pct_long', 'progressive_passes', 'pass_xa', 'passes_total_distance', 'passes_progressive_distance'],
            'Progressive Play & Build-Up': ['passes_into_final_third', 'passes_into_penalty_area', 'progressive_carries', 'carries_into_final_third', 'carries_into_penalty_area', 'carries', 'carries_distance', 'carries_progressive_distance', 'progressive_passes_received'],
            'Dribbling & Take-Ons': ['take_ons', 'take_ons_won', 'take_ons_won_pct', 'take_ons_tackled', 'take_ons_tackled_pct', 'miscontrols', 'dispossessed'],
            'Attacking Contribution': ['goals', 'goals_per90', 'assists', 'assists_per90', 'goals_assists', 'goals_assists_per90', 'shots', 'shots_on_target', 'shots_per90', 'shots_on_target_per90', 'shots_on_target_pct', 'sca', 'sca_per90', 'gca', 'gca_per90'],
            'Expected Goals (xG) & xA': ['xg', 'xg_per90', 'xg_assist', 'xg_assist_per90', 'npxg', 'npxg_per90', 'npxg_xg_assist', 'npxg_xg_assist_per90', 'xgot', 'xgot_per90'],
            'Crosses & Set Pieces': ['through_balls', 'crosses_into_penalty_area', 'passes_switches', 'misc_crosses', 'pens_made', 'pens_att', 'pens_won', 'corner_kicks_in', 'corner_kicks_out', 'corner_kicks_straight', 'passes_free_kicks', 'shots_free_kicks'],
            'Touches & Ball Control': ['touches', 'touches_def_pen_area', 'touches_def_3rd', 'touches_mid_3rd', 'touches_att_3rd', 'touches_att_pen_area', 'touches_live_ball', 'ball_recoveries', 'passes_received'],
            'Discipline & Errors': ['fouls', 'cards_yellow', 'cards_red', 'cards_yellow_red', 'errors', 'own_goals', 'offsides', 'pens_conceded'],
        },
        'MF': {
            'Creativity & Chance Creation': ['assists', 'assists_per90', 'through_balls', 'sca', 'sca_per90', 'sca_passes_live', 'sca_passes_dead', 'sca_take_ons', 'sca_shots', 'sca_fouled', 'gca', 'gca_per90', 'gca_passes_live', 'gca_passes_dead'],
            'Expected Assists (xA)': ['xg_assist', 'xg_assist_per90', 'pass_xa', 'assisted_shots', 'pass_xg_assist', 'xg_assist_net'],
            'Passing & Distribution': ['passes_completed', 'passes', 'passes_pct', 'passes_completed_short', 'passes_short', 'passes_pct_short', 'passes_completed_medium', 'passes_medium', 'passes_pct_medium', 'passes_completed_long', 'passes_long', 'passes_pct_long', 'progressive_passes', 'passes_total_distance', 'passes_progressive_distance'],
            'Final Third & Penetration': ['passes_into_final_third', 'passes_into_penalty_area', 'crosses_into_penalty_area', 'passes_switches', 'corner_kicks_in', 'corner_kicks_out', 'corner_kicks_straight', 'misc_crosses'],
            'Ball Carrying & Progressive Play': ['progressive_carries', 'carries_into_final_third', 'carries_into_penalty_area', 'carries', 'carries_distance', 'carries_progressive_distance', 'ball_recoveries', 'progressive_passes_received'],
            'Dribbling & Take-Ons': ['take_ons', 'take_ons_won', 'take_ons_won_pct', 'take_ons_tackled', 'take_ons_tackled_pct', 'miscontrols', 'dispossessed'],
            'Goal Threat & Shooting': ['goals', 'goals_per90', 'shots', 'shots_on_target', 'shots_per90', 'shots_on_target_per90', 'shots_on_target_pct', 'goals_per_shot', 'goals_per_shot_on_target', 'shots_free_kicks', 'average_shot_distance', 'xgot_net'],
            'Expected Goals (xG)': ['xg', 'xg_per90', 'npxg', 'npxg_per90', 'xg_net', 'npxg_xg_assist', 'npxg_xg_assist_per90', 'npxg_per_shot', 'xg_xg_assist_per90', 'xgot', 'xgot_per90'],
            'Defensive Contribution': ['tackles', 'tackles_won', 'tackles_def_3rd', 'tackles_mid_3rd', 'tackles_att_3rd', 'interceptions', 'blocks', 'blocked_shots', 'blocked_passes', 'challenge_tackles', 'challenges', 'tackles_interceptions'],
            'Aerial & Physical Duels': ['aerials_won', 'aerials_lost', 'aerials_won_pct', 'fouls', 'fouled', 'challenges', 'challenges_lost'],
            'Touches & Positioning': ['touches', 'touches_def_pen_area', 'touches_def_3rd', 'touches_mid_3rd', 'touches_att_3rd', 'touches_att_pen_area', 'touches_live_ball', 'passes_received'],
            'Discipline & Game Management': ['cards_yellow', 'cards_red', 'cards_yellow_red', 'offsides', 'errors', 'own_goals', 'pens_conceded'],
        },
        'FW': {
            'Finishing & Clinical': ['goals', 'goals_per90', 'goals_per_shot', 'goals_per_shot_on_target', 'shots', 'shots_on_target', 'shots_per90', 'shots_on_target_per90', 'shots_on_target_pct', 'shots_free_kicks', 'average_shot_distance', 'goals_pens', 'goals_pens_per90', 'xgot_net'],
            'Expected Goals (xG) & Efficiency': ['xg', 'xg_per90', 'npxg', 'npxg_per90', 'xg_net', 'npxg_net', 'npxg_per_shot', 'npxg_xg_assist', 'npxg_xg_assist_per90', 'shot_xg', 'shot_npxg', 'xgot', 'xgot_per90'],
            'Creativity & Assists': ['assists', 'assists_per90', 'through_balls', 'sca', 'sca_per90', 'sca_passes_live', 'sca_passes_dead', 'sca_take_ons', 'gca', 'gca_per90', 'gca_passes_live', 'gca_passes_dead'],
            'Expected Assists (xA)': ['xg_assist', 'xg_assist_per90', 'pass_xa', 'assisted_shots', 'pass_xg_assist', 'xg_assist_net', 'xg_xg_assist_per90'],
            'Dribbling & 1v1 Skills': ['take_ons', 'take_ons_won', 'take_ons_won_pct', 'take_ons_tackled', 'take_ons_tackled_pct'],
            'Ball Control & Touch': ['touches', 'touches_att_pen_area', 'touches_att_3rd', 'touches_live_ball', 'miscontrols', 'dispossessed', 'ball_recoveries', 'passes_received'],
            'Progressive Play & Carries': ['progressive_carries', 'carries_into_penalty_area', 'carries_into_final_third', 'carries', 'carries_distance', 'carries_progressive_distance', 'progressive_passes_received'],
            'Penalties & Set Pieces': ['pens_made', 'pens_att', 'pens_won', 'shots_free_kicks', 'corner_kicks_in', 'corner_kicks_out', 'corner_kicks_straight', 'passes_free_kicks'],
            'Aerial & Heading': ['aerials_won', 'aerials_lost', 'aerials_won_pct', 'fouled'],
            'Link-Up & Passing': ['passes_completed', 'passes', 'passes_pct', 'passes_into_penalty_area', 'passes_into_final_third', 'progressive_passes', 'pass_xa', 'crosses_into_penalty_area', 'passes_total_distance', 'passes_progressive_distance'],
            'Defensive Work': ['tackles', 'tackles_won', 'interceptions', 'blocks', 'challenge_tackles', 'challenges', 'tackles_interceptions'],
            'Discipline': ['cards_yellow', 'cards_red', 'cards_yellow_red', 'fouls', 'offsides', 'errors', 'own_goals', 'pens_conceded'],
        }
    }
    # Build the radar on only real, available metrics: strip retired +
    # unavailable metrics, keep any category with >=1 real metric, drop
    # fully-empty ones.
    result = {
        pos: {cat: kept
              for cat, metrics in cats.items()
              if len(kept := [m for m in metrics if m not in EXCLUDED_METRICS]) >= 1}
        for pos, cats in raw.items()
    }
    # Drop remnant categories that survive with 1 metric but are junk
    # (mislabeled or a duplicate of another category).
    for pos, cat in [('DF', 'Touches & Ball Control'),
                     ('GK', 'Expected Goals (xG) Conceded'),
                     ('GK', 'Penalties & Set Pieces'),
                     ('MF', 'Aerial & Physical Duels'),
                     ('MF', 'Ball Carrying & Progressive Play')]:  # only ball_recoveries left
        result.get(pos, {}).pop(cat, None)
    return result


def get_negative_metrics():
    return [
        'cards_yellow', 'cards_red', 'cards_yellow_red', 'second_yellow', 'straight_red',
        'errors', 'errors_per90', 'own_goals', 'own_goals_per90', 'offsides', 'offsides_per90',
        'fouls', 'fouls_per90', 'miscontrols', 'miscontrols_per90', 'dispossessed', 'dispossessed_per90',
        'dribbled_past', 'dribbled_past_per90', 'goals_against', 'goals_against_per90',
        'gk_goals_against_per90', 'gk_goals_against', 'goals_against_gk',
        'gk_shots_on_target_against', 'gk_losses', 'gk_own_goals_against',
        'gk_pens_allowed', 'gk_free_kick_goals_against', 'gk_corner_kick_goals_against',
        'on_goals_against', 'on_xg_against',
        'shots_against', 'shots_on_target_against', 'on_goal_against', 'on_goal_against_per90',
        'xg_against', 'xg_against_per90',
        'pk_allow', 'pens_allow', 'pens_missed', 'pens_saved_against', 'pens_conceded',
        'free_kicks_against', 'corners_against', 'crosses_into_box_against',
        'aerials_lost', 'aerials_lost_per90',
        'take_ons_tackled', 'take_ons_tackled_pct',
        'challenges_lost', 'challenges_lost_per90',
        # Shooting from closer is the better finishing signal, so lower avg shot
        # distance -> higher percentile in the Finishing/Shooting categories.
        'average_shot_distance',
    ]


def invert_negative_metrics(value, metric_name):
    if metric_name in get_negative_metrics():
        if value <= 0:
            return 100
        return max(0, 100 / (1 + value))
    return value


# ==============================================================================
# PERCENTILE SCORING
# ==============================================================================

def calculate_percentile_score(value, comparison_values):
    if len(comparison_values) == 0 or pd.isna(value):
        return 0
    clean = [v for v in comparison_values if not pd.isna(v)]
    if len(clean) == 0:
        return 0
    return stats.percentileofscore(clean, value, kind='rank')


def calculate_category_scores(player_data, comparison_data, style_categories, position, method='percentile', empty_as_none=False):
    """empty_as_none=True marks a category with no measurable metrics as
    None instead of 0, so the profile radar can show 'no data' rather
    than a misleading zero. Off by default so other callers keep numeric scores."""
    if position not in style_categories:
        return {}
    empty_val = None if empty_as_none else 0
    category_scores = {}
    neg_metrics = get_negative_metrics()
    for cat_name, metrics in style_categories[position].items():
        available = [m for m in metrics if m in comparison_data.columns]
        if not available:
            category_scores[cat_name] = empty_val
            continue
        if method == 'percentile':
            percentiles = []
            for metric in available:
                pv = safe_float(player_data.get(metric, 0)) if isinstance(player_data, dict) else safe_float(player_data[metric]) if metric in player_data.index else 0
                # _num_series, NOT safe_float, for the comparison POOL -
                # safe_float coerces missing to 0.0, which would fabricate a
                # zero and inflate the pool; _num_series preserves NaN so .dropna() excludes it.
                comp = _num_series(comparison_data[metric]).dropna()
                # Skip columns with no signal (all identical / structurally N/A,
                # e.g. average_shot_distance that is 0 for a whole season) so they
                # don't inject a flat ~50 into the category score.
                if len(comp) > 0 and comp.min() != comp.max():
                    pctl = calculate_percentile_score(pv, comp.tolist())
                    if metric in neg_metrics:
                        pctl = 100 - pctl
                    percentiles.append(pctl)
            category_scores[cat_name] = float(np.mean(percentiles)) if percentiles else empty_val
        elif method == 'normalized':
            norms = []
            for metric in available:
                pv = safe_float(player_data.get(metric, 0)) if isinstance(player_data, dict) else safe_float(player_data[metric]) if metric in player_data.index else 0
                comp = _num_series(comparison_data[metric]).dropna()
                if len(comp) > 0:
                    mn, mx = comp.min(), comp.max()
                    if mx > mn:
                        n = ((pv - mn) / (mx - mn)) * 100
                        n = max(0, min(100, n))
                        if metric in neg_metrics:
                            n = 100 - n
                        norms.append(n)
            category_scores[cat_name] = float(np.mean(norms)) if norms else empty_val
    return category_scores


# ==============================================================================
# COMPOSITE INDEX
# ==============================================================================

def _get_position_metrics_for_composite(pos):
    """Per-90 / key metrics used in composite z-score by position."""
    if pos == 'GK':
        # only 2025-26-available keeper metrics (crosses/sweeping/passes_pct unavailable)
        return ['gk_save_pct', 'gk_clean_sheets_pct', 'gk_psxg_net_per90',
                'gk_goals_against_per90', 'gk_saves', 'gk_clean_sheets']
    elif pos == 'DF':
        # only 2025-26-available metrics (blocks/aerials/passes_pct/etc. unavailable)
        return ['tackles', 'interceptions', 'clearances', 'tackles_interceptions',
                'ball_recoveries', 'xg_assist_per90', 'xg_per90', 'goals_per90', 'assists_per90']
    elif pos == 'MF':
        return ['xg_per90', 'npxg_per90', 'xg_assist_per90', 'shots_on_target_per90',
                'goals_per90', 'assists_per90', 'xgot_per90', 'take_ons_won']
    else:  # FW
        return ['goals_per90', 'assists_per90', 'xg_per90', 'npxg_per90', 'shots_per90',
                'shots_on_target_pct', 'xg_assist_per90', 'npxg_per_shot',
                'xgot_per90', 'goals_per_shot', 'take_ons_won']


def calculate_composite_index(pos_df, pos, style_categories):
    """Composite = 40% z-score aggregate + 30% style-category percentile
    avg + 30% power rating (normalised), negative metrics inverted.
    Returns pos_df with extra columns: zscore_comp, style_pctile_avg, power_norm, composite_index."""
    neg_metrics = get_negative_metrics()
    metrics = _get_position_metrics_for_composite(pos)

    # --- 1. Z-score aggregation (40%) ---
    available = [m for m in metrics if m in pos_df.columns]
    zscore_sums = pd.Series(0.0, index=pos_df.index)
    valid_count = pd.Series(0, index=pos_df.index)

    for m in available:
        col = _num_series(pos_df[m])
        non_null = ~col.isna()
        mean_val = col.mean()
        std_val = col.std()
        if std_val > 0:
            z = (col - mean_val) / std_val
            if m in neg_metrics:
                z = -z
            zscore_sums += z.fillna(0)
            valid_count += non_null.astype(int)

    avg_z = zscore_sums / valid_count.replace(0, 1)
    # Percentile rank, not min-max: min-max is squashed by small-sample
    # outliers (a freak per-90 crushes everyone else). Percentile rank is
    # outlier-immune and comparable across seasons.
    if len(avg_z) > 1:
        zscore_norm = avg_z.rank(pct=True) * 100
    else:
        zscore_norm = pd.Series(50.0, index=pos_df.index)

    # --- 2. Style-category percentile average (30%) ---
    # Coverage-aware: only count categories where the player has data for
    # >= 50% of that category's metrics - avoids crediting low-minutes
    # players with median (50) for every missing stat.
    position_cats = style_categories.get(pos, {})
    cat_sums = pd.Series(0.0, index=pos_df.index)
    cat_valid_per_player = pd.Series(0, index=pos_df.index)

    for cat_name, cat_metrics in position_cats.items():
        avail_cat = [m for m in cat_metrics if m in pos_df.columns]
        if not avail_cat:
            continue
        cat_pctile_sum = pd.Series(0.0, index=pos_df.index)
        cat_pctile_present = pd.Series(0, index=pos_df.index)
        for m in avail_cat:
            col = _num_series(pos_df[m])
            pctile = col.rank(pct=True, na_option='keep') * 100
            if m in neg_metrics:
                pctile = 100 - pctile
            non_null = ~pctile.isna()
            cat_pctile_sum += pctile.fillna(0)
            cat_pctile_present += non_null.astype(int)
        coverage_threshold = max(1, len(avail_cat) // config.CATEGORY_COVERAGE_DIVISOR)
        sufficient = cat_pctile_present >= coverage_threshold
        cat_avg = cat_pctile_sum / cat_pctile_present.replace(0, 1)
        cat_sums += cat_avg.where(sufficient, 0)
        cat_valid_per_player += sufficient.astype(int)

    style_avg = cat_sums / cat_valid_per_player.replace(0, 1)
    style_avg = style_avg.where(cat_valid_per_player > 0, 50)
    style_avg = style_avg.clip(0, 100)

    # --- 3. Power rating (30%) ---
    # Each league's quality is already on a 0-100 scale - use it directly.
    # Min-max normalization only made sense over a multi-league pool; a
    # single-league cohort collapsed everyone to the same score.
    if 'power_rating' not in pos_df.columns:
        pos_df = pos_df.copy()
        pos_df['power_rating'] = 0
    pr = pos_df['power_rating'].apply(safe_float)
    power_norm = pr.clip(0, 100)

    # --- Composite ---
    composite = (zscore_norm * config.COMPOSITE_ZSCORE_WEIGHT
                 + style_avg * config.COMPOSITE_STYLE_WEIGHT
                 + power_norm * config.COMPOSITE_POWER_WEIGHT)

    pos_df = pos_df.copy()
    pos_df['zscore_comp'] = zscore_norm.round(1)
    pos_df['style_pctile_avg'] = style_avg.round(1)
    pos_df['power_norm'] = power_norm.round(1)
    pos_df['composite_index'] = composite.round(1)
    return pos_df


def style_category_matrix(pos_df, pos, style_categories):
    """Per-player, per-category style percentile - the same coverage-aware
    computation calculate_composite_index uses, kept as a full matrix.
    Used by ml.style_clustering and build_season_position_table's spread columns."""
    neg_metrics = get_negative_metrics()
    position_cats = style_categories.get(pos, {})
    cat_matrix = {}
    for cat_name, cat_metrics in position_cats.items():
        avail = [m for m in cat_metrics if m in pos_df.columns]
        if not avail:
            continue
        pctile_sum = pd.Series(0.0, index=pos_df.index)
        pctile_present = pd.Series(0, index=pos_df.index)
        for m in avail:
            col = _num_series(pos_df[m])
            pctile = col.rank(pct=True, na_option='keep') * 100
            if m in neg_metrics:
                pctile = 100 - pctile
            non_null = ~pctile.isna()
            pctile_sum += pctile.fillna(0)
            pctile_present += non_null.astype(int)
        coverage_threshold = max(1, len(avail) // config.CATEGORY_COVERAGE_DIVISOR)
        sufficient = pctile_present >= coverage_threshold
        cat_avg = pctile_sum / pctile_present.replace(0, 1)
        cat_matrix[cat_name] = cat_avg.where(sufficient, np.nan)
    return pd.DataFrame(cat_matrix, index=pos_df.index)


def build_season_position_table(pos_df, pos, style_categories):
    """Score one (season, position) pool at once: composite_index plus
    per-category style spread (max/min/std - how spiky vs. balanced a
    profile is). `pos_df` must already be filtered to one position/season."""
    pos_df = calculate_composite_index(pos_df, pos, style_categories)
    cat_df = style_category_matrix(pos_df, pos, style_categories)
    pos_df = pos_df.copy()
    pos_df['style_pctile_max'] = cat_df.max(axis=1)
    pos_df['style_pctile_min'] = cat_df.min(axis=1)
    pos_df['style_pctile_std'] = cat_df.std(axis=1)
    # A player with zero qualifying categories has nothing to compute
    # max/min/std from - fill with neutral values matching
    # calculate_composite_index's own fallback, not NaN (which corrupts downstream feature vectors).
    pos_df['style_pctile_max'] = pos_df['style_pctile_max'].fillna(50.0)
    pos_df['style_pctile_min'] = pos_df['style_pctile_min'].fillna(50.0)
    pos_df['style_pctile_std'] = pos_df['style_pctile_std'].fillna(0.0)
    return pos_df


def get_power_rating(player_data):
    """Get league-level power rating from player data."""
    if isinstance(player_data, dict):
        return safe_float(player_data.get('power_rating', 0))
    if 'power_rating' in player_data.index:
        return safe_float(player_data['power_rating'])
    return 0.0


def composite_description(score):
    """Describe composite index score."""
    if score >= config.COMPOSITE_TIER_WORLD_CLASS: return "World Class"
    if score >= config.COMPOSITE_TIER_ELITE: return "Elite"
    if score >= config.COMPOSITE_TIER_EXCELLENT: return "Excellent"
    if score >= config.COMPOSITE_TIER_GOOD: return "Good"
    if score >= config.COMPOSITE_TIER_AVERAGE: return "Average"
    if score >= config.COMPOSITE_TIER_BELOW_AVERAGE: return "Below Average"
    return "Poor"
