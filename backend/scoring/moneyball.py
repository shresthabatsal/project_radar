#!/usr/bin/env python3
"""
Moneyball score (performance + value-efficiency + contract-opportunity
blend) and its contract-opportunity component. contract_opportunity_
breakdown() uses the trained market-value model for its release-clause input.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config
from data.loader import safe_float, contract_months_remaining
from ml.market_value import predict


def _resolve_market_value(row):
    """Real market_value_eur if on file, else the ML-predicted estimate
    (trained GBM, falling back to the heuristic internally if no model has
    been trained yet - see ml/market_value/predict.py)."""
    mv = safe_float(row.get('market_value_eur', 0))
    if mv > 0:
        return mv
    return predict.predict(row)


def contract_opportunity_breakdown(row):
    """Contract-opportunity score split into its two parts so the lab can show
    the working: urgency (less time left = more leverage) + release-clause
    discount (a clause below market value = a bargain exit). Capped 0-100."""
    months = contract_months_remaining(row)
    mv = _resolve_market_value(row)
    rc = safe_float(row.get('release_clause_eur', 0))
    if months is None: urgency = config.CONTRACT_URGENCY_UNKNOWN
    elif months <= 0: urgency = config.CONTRACT_URGENCY_EXPIRED
    elif months <= config.CONTRACT_MONTHS_TIER_6: urgency = config.CONTRACT_URGENCY_LT_6M
    elif months <= config.CONTRACT_MONTHS_TIER_12: urgency = config.CONTRACT_URGENCY_LT_12M
    elif months <= config.CONTRACT_MONTHS_TIER_18: urgency = config.CONTRACT_URGENCY_LT_18M
    elif months <= config.CONTRACT_MONTHS_TIER_24: urgency = config.CONTRACT_URGENCY_LT_24M
    else: urgency = config.CONTRACT_URGENCY_GE_24M
    clause_score = config.CONTRACT_CLAUSE_SCORE_NONE
    if rc > 0 and mv > 0:
        ratio = rc / mv
        if ratio < config.CONTRACT_CLAUSE_RATIO_50: clause_score = config.CONTRACT_CLAUSE_SCORE_50
        elif ratio < config.CONTRACT_CLAUSE_RATIO_75: clause_score = config.CONTRACT_CLAUSE_SCORE_75
        elif ratio < config.CONTRACT_CLAUSE_RATIO_100: clause_score = config.CONTRACT_CLAUSE_SCORE_100
        elif ratio < config.CONTRACT_CLAUSE_RATIO_125: clause_score = config.CONTRACT_CLAUSE_SCORE_125
    return {
        'months': months,
        'urgency': urgency,
        'clause': clause_score,
        'total': round(min(100, urgency + clause_score), 1),
    }


def calculate_contract_opportunity_score(row):
    return contract_opportunity_breakdown(row)['total']


def calculate_moneyball(perf, val_eff, contract):
    return round(perf * config.MONEYBALL_PERFORMANCE_WEIGHT
                 + val_eff * config.MONEYBALL_VALUE_EFFICIENCY_WEIGHT
                 + contract * config.MONEYBALL_CONTRACT_WEIGHT, 1)
