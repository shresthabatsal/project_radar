#!/usr/bin/env python3
"""
Hidden-gem detection: the 7 methods cmd_get_hidden_gems evaluates per
player, given the position-pool stats it has already computed (composite
index, wage percentile, category percentiles, trajectory).
"""

import os
import sys

from scipy import stats

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from backend.scoring.moneyball import calculate_moneyball, calculate_contract_opportunity_score


def detect(row, idx, composite, ci_mean, ci_std, age, wage, wage_est, wages,
           mv, mv_ceiling, cat_pctile_cols, riser):
    """Evaluate the 7 hidden-gem detection methods for one player-season
    row. Returns each method's boolean, derived scores (z_score,
    value_ratio, age_potential, wage_pctl, contract_score, moneyball_score), and the qualifies flag."""
    wage_pctl = stats.percentileofscore(wages.dropna(), wage, kind='rank') if len(wages) > 1 else 50

    # 1. Percentile Outlier: composite > threshold (top ~10%, Elite tier).
    pctl_outlier = composite > config.GEM_PCTL_OUTLIER_COMPOSITE
    # 2. Z-Score: composite z-score > threshold
    z_score = (composite - ci_mean) / ci_std if ci_std > 0 else 0
    z_outlier = bool(z_score > config.GEM_ZSCORE_OUTLIER_Z)
    # 3. Value Ratio: composite / wage_percentile. Only valid on real wage
    # data - an estimated wage hits the floor, which would falsely flag
    # every no-data player as a value gem.
    value_ratio = (composite / max(wage_pctl, 1)) * config.VALUE_RATIO_SCALE
    value_gem = bool(value_ratio > config.GEM_VALUE_RATIO_THRESHOLD) and not wage_est
    # 4. Age-Weighted Potential: young + high composite
    age_potential = composite * (config.GEM_AGE_POTENTIAL_YOUNG_MULT if age < config.GEM_AGE_POTENTIAL_YOUNG_AGE
                                  else config.GEM_AGE_POTENTIAL_RISING_MULT if age < config.GEM_AGE_POTENTIAL_RISING_AGE
                                  else config.GEM_AGE_POTENTIAL_VETERAN_MULT if age > config.GEM_AGE_POTENTIAL_VETERAN_AGE
                                  else config.GEM_AGE_POTENTIAL_DEFAULT_MULT)
    age_gem = age < config.GEM_AGE_GEM_MAX_AGE and age_potential > config.GEM_AGE_GEM_MIN_POTENTIAL
    # 5. Composite Score: all factors combined
    contract_score = calculate_contract_opportunity_score(row)
    value_eff = min(100, value_ratio) if not wage_est else 50.0
    moneyball_score = calculate_moneyball(composite, value_eff, contract_score)
    composite_gem = moneyball_score > config.GEM_MONEYBALL_THRESHOLD
    # 6. Statistical Anomaly: 2+ style categories above 90th percentile
    top_categories = sum(1 for cn, cs in cat_pctile_cols.items() if cs.get(idx, 0) > config.GEM_ANOMALY_PERCENTILE)
    anomaly = top_categories >= config.GEM_ANOMALY_MIN_CATEGORIES
    # 7. Riser: improving across seasons (forward-looking). Backtesting
    # showed the other 6 methods favour peak players who regress to the
    # mean; the Riser signal surfaces players still on the way up.

    gem_methods = sum([pctl_outlier, z_outlier, value_gem, age_gem, composite_gem, anomaly, riser])

    # A hidden gem must be UNDERVALUED, not merely elite - the performance
    # methods alone would fire for any top player. Require at least one
    # value/upside signal, and exclude anyone already carrying a high real market value.
    value_signal = value_gem or age_gem or composite_gem
    # mv here is the real value if we have one, otherwise the heuristic
    # estimate. The ceiling applies to both.
    already_expensive = (mv >= mv_ceiling) or ((not wage_est) and wage_pctl >= config.GEM_ALREADY_EXPENSIVE_WAGE_PCTL)
    qualifies = gem_methods >= config.GEM_MIN_METHODS_TRIGGERED and value_signal and not already_expensive

    return {
        'methods': {
            'percentile_outlier': pctl_outlier,
            'z_score_outlier': z_outlier,
            'value_ratio': value_gem,
            'age_weighted': age_gem,
            'composite_score': composite_gem,
            'statistical_anomaly': anomaly,
            'riser': riser,
        },
        'gem_methods': gem_methods,
        'value_signal': value_signal,
        'already_expensive': already_expensive,
        'qualifies': qualifies,
        'wage_pctl': wage_pctl,
        'z_score': z_score,
        'value_ratio': value_ratio,
        'age_potential': age_potential,
        'contract_score': contract_score,
        'moneyball_score': moneyball_score,
    }
