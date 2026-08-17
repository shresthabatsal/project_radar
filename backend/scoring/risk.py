#!/usr/bin/env python3
"""
Player risk flags: four independent, diagnostic-only reasons - contract,
mileage/decline, sell-high (ml.sell_high_risk + rule gate), financial.
Each has its own trigger condition and detail string, never one opaque score.
"""

import os
import sys

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from data.loader import safe_float, load_player_history, load_player_supplementary_history, prev_season_label
from backend.scoring.moneyball import contract_opportunity_breakdown
from ml.sell_high_risk import predict as sell_high_predict
from ml.sell_high_risk.features import output_score as sell_high_output_score


def contract_risk(row):
    """Rule: contract expiring within CONTRACT_MONTHS_TIER_12 (same tier
    contract_opportunity_breakdown uses) while composite_index is still
    at/above COMPOSITE_TIER_GOOD - a fringe player's expiry isn't a risk."""
    months = contract_opportunity_breakdown(row)['months']
    composite = safe_float(row.get('composite_index', 0)) if row.get('composite_index') is not None else 0.0
    triggered = bool(
        months is not None and months <= config.CONTRACT_MONTHS_TIER_12
        and composite >= config.COMPOSITE_TIER_GOOD
    )
    return {
        'reason': 'contract',
        'label': 'Contract expiring soon',
        'triggered': triggered,
        'months_remaining': months,
        'composite_index': round(composite, 1) if composite else None,
        'detail': (
            f"Contract expires in {months} month(s) while rated {composite:.1f} composite - "
            f"real risk of losing a meaningful contributor for nothing."
        ) if triggered else None,
    }


def _pace_dependent_categories(position, style_categories):
    cats = (style_categories or {}).get(position, {})
    return [c for c in cats if any(kw in c.lower() for kw in config.RISK_PACE_CATEGORY_KEYWORDS)]


def _leans_on_pace(category_scores, pace_cats):
    if not pace_cats or not category_scores:
        return False
    vals = [category_scores.get(c) for c in pace_cats if category_scores.get(c) is not None]
    if not vals:
        return False
    return float(np.mean(vals)) >= config.RISK_PACE_STYLE_PERCENTILE_THRESHOLD


def mileage_decline_risk(row, position, style_categories=None, category_scores=None, career_minutes=None):
    """Rule: age >= RISK_MILEAGE_AGE_THRESHOLD, and either heavy career
    minutes (`career_minutes`, summed via load_player_history) or a style
    profile leaning on pace-dependent categories (RISK_PACE_CATEGORY_KEYWORDS)."""
    age = safe_float(row.get('age', 0))
    if age < config.RISK_MILEAGE_AGE_THRESHOLD:
        return {
            'reason': 'mileage_decline', 'label': 'Mileage / decline risk', 'triggered': False,
            'age': round(age, 1) if age else None, 'career_minutes': career_minutes,
            'pace_dependent': False, 'detail': None,
        }

    high_mileage = career_minutes is not None and career_minutes >= config.RISK_MILEAGE_CAREER_MINUTES_THRESHOLD
    pace_cats = _pace_dependent_categories(position, style_categories)
    pace_dependent = _leans_on_pace(category_scores, pace_cats)
    triggered = bool(high_mileage or pace_dependent)

    reasons = []
    if high_mileage:
        reasons.append(f"{int(career_minutes):,} career minutes on file")
    if pace_dependent:
        reasons.append("a style profile leaning on pace-dependent categories")

    return {
        'reason': 'mileage_decline',
        'label': 'Mileage / decline risk',
        'triggered': triggered,
        'age': round(age, 1),
        'career_minutes': career_minutes,
        'pace_dependent': pace_dependent,
        'detail': f"Age {age:.0f}, with " + " and ".join(reasons) + "." if triggered else None,
    }


def _start_year(season):
    """'2024-2025' -> 2024 - duplicated (not imported) from ml.sell_high_
    risk.train's own copy, same "keep independently-trained models/scoring
    modules decoupled" convention used throughout this project."""
    return int(str(season).split('-')[0])


def _output_score_peak_to_date(history, season, position_col='primary_position'):
    """Leakage-safe running max of this player's real output_score across
    qualifying seasons strictly before `season`, scored against the trained
    model's frozen reference (predict.get_reference()). None if unavailable."""
    if history is None or history.empty:
        return None
    reference = sell_high_predict.get_reference()
    if not reference:
        return None
    cur_start = _start_year(str(season))
    peak = None
    for _, hrow in history.iterrows():
        h_season = str(hrow.get('season', ''))
        if not h_season or _start_year(h_season) >= cur_start:
            continue
        if safe_float(hrow.get('minutes', 0)) < config.SELL_HIGH_MIN_MINUTES:
            continue
        h_pos = str(hrow.get(position_col, hrow.get('position', 'MF')))
        h_score = sell_high_output_score(hrow.to_dict(), h_pos, reference)
        if h_score is not None:
            peak = h_score if peak is None else max(peak, h_score)
    return peak


def sell_high_risk(row, player_name, season, position, prior_row=None, history=None):
    """ML + rule gate - ALL must hold: (1) minutes >= SELL_HIGH_MIN_MINUTES
    (the model's training floor), (2) current real market value is at/near
    its own real historical peak, (3) ml.sell_high_risk predicts a high deterioration probability."""
    meets_minutes_floor = safe_float(row.get('minutes', 0)) >= config.SELL_HIGH_MIN_MINUTES

    supp_hist = load_player_supplementary_history(player_name)
    real_by_season = {}
    if not supp_hist.empty and 'season' in supp_hist.columns and 'market_value_eur' in supp_hist.columns:
        for _, r in supp_hist.iterrows():
            mv = safe_float(r.get('market_value_eur', 0))
            if mv > 0:
                s = str(r.get('season'))
                real_by_season[s] = max(mv, real_by_season.get(s, 0))

    current_real = real_by_season.get(str(season))
    peak_real = max(real_by_season.values()) if real_by_season else None
    at_peak = bool(
        current_real is not None and peak_real is not None and peak_real > 0
        and current_real >= peak_real * config.RISK_SELL_HIGH_PEAK_RATIO
    )

    prior_season = prev_season_label(str(season))
    prior_season_2 = prev_season_label(prior_season) if prior_season else None
    prior_mv = real_by_season.get(str(prior_season)) if prior_season else None
    prior_mv_2 = real_by_season.get(str(prior_season_2)) if prior_season_2 else None
    # Peak "to date" - only seasons at/before this one, same leakage-safe
    # idea ml.sell_high_risk.train._mv_lookup_and_peaks uses for training.
    peak_to_date = max(
        (v for s, v in real_by_season.items() if _start_year(s) <= _start_year(str(season))),
        default=current_real,
    )

    prior_row_2 = None
    if history is not None and not history.empty and prior_season_2:
        p2 = history[history['season'].astype(str) == str(prior_season_2)]
        if not p2.empty:
            prior_row_2 = p2.iloc[0].to_dict()
    output_score_peak_to_date = _output_score_peak_to_date(history, season)

    deterioration_probability = (
        sell_high_predict.predict_deterioration_probability(
            row, position, prior_row=prior_row, prior_row_2=prior_row_2,
            current_mv=current_real, prior_mv=prior_mv, prior_mv_2=prior_mv_2,
            peak_mv_to_date=peak_to_date, output_score_peak_to_date=output_score_peak_to_date,
        ) if (current_real is not None and meets_minutes_floor) else None
    )
    strongly_declining = bool(
        deterioration_probability is not None
        and deterioration_probability >= config.RISK_SELL_HIGH_DETERIORATION_PROB_THRESHOLD
    )
    triggered = at_peak and strongly_declining

    return {
        'reason': 'sell_high',
        'label': 'Sell-high risk',
        'triggered': triggered,
        'deterioration_probability': round(deterioration_probability, 3) if deterioration_probability is not None else None,
        'current_real_value': current_real,
        'peak_real_value': peak_real,
        'at_peak': at_peak,
        'meets_minutes_floor': meets_minutes_floor,
        'detail': (
            f"{deterioration_probability * 100:.0f}% predicted probability of significant on-field "
            f"decline next season while at/near a real career-peak value on file (currently "
            f"{current_real:,.0f} vs. a peak of {peak_real:,.0f})."
        ) if triggered else None,
    }


def financial_risk(row):
    """Rule: value_efficiency (backend.scoring.moneyball's formula) at/below
    RISK_FINANCIAL_VALUE_EFF_THRESHOLD. Only evaluated with a real wage on
    file - an estimated wage is already neutralized to 50 by that formula."""
    wage_est = bool(row.get('wage_is_estimated', row.get('wage_estimated', False)))
    raw_eff = row.get('value_efficiency')
    if wage_est or raw_eff is None:
        return {
            'reason': 'financial', 'label': 'Financial risk', 'triggered': False,
            'value_efficiency': None, 'wage_estimated': wage_est, 'detail': None,
        }
    value_eff = safe_float(raw_eff)
    triggered = bool(value_eff <= config.RISK_FINANCIAL_VALUE_EFF_THRESHOLD)
    return {
        'reason': 'financial',
        'label': 'Financial risk',
        'triggered': triggered,
        'value_efficiency': round(value_eff, 1),
        'wage_estimated': wage_est,
        'detail': (
            f"Value efficiency {value_eff:.1f}/100 - wage high relative to output."
        ) if triggered else None,
    }


def assess_player_risk(row, player_name, season, position, style_categories=None,
                        category_scores=None, career_minutes=None, prior_row=None, history=None):
    """Run all four checks for one player. `row` must already carry
    composite_index/value_efficiency/wage_is_estimated/contract fields.
    `career_minutes`/`prior_row`/`history` are optional - each reason degrades gracefully without them."""
    reasons = [
        contract_risk(row),
        mileage_decline_risk(row, position, style_categories, category_scores, career_minutes),
        sell_high_risk(row, player_name, season, position, prior_row=prior_row, history=history),
        financial_risk(row),
    ]
    return {
        'player': player_name,
        'season': str(season),
        'position': position,
        'any_triggered': any(r['triggered'] for r in reasons),
        'triggered_reasons': [r['reason'] for r in reasons if r['triggered']],
        'reasons': reasons,
    }
