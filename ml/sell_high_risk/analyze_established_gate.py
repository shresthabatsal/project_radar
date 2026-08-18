#!/usr/bin/env python3
"""
Investigates whether sell_high_risk needs an "established player"
condition. Read-only: computes career_minutes_to_date and
n_real_mv_seasons_to_date as diagnostic-only proxies, without touching the model.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data import loader
from data.loader import load_player_history, load_player_supplementary_history, safe_float
from backend import config
from ml.sell_high_risk.train import build_training_rows, _apply_residual_labels, _start_year
from ml.sell_high_risk.predict import load_model

# log(0.9) - the same RISK_SELL_HIGH_PEAK_RATIO threshold risk.py's
# at_peak check uses, expressed in distance_from_peak_mv's log-space.
AT_PEAK_LOG_THRESHOLD = float(np.log(config.RISK_SELL_HIGH_PEAK_RATIO))


def _established_proxies(df):
    """Attaches career_minutes_to_date / n_real_mv_seasons_to_date to a
    (small, near-peak-only) slice of train_df - one load_player_history +
    load_player_supplementary_history call per UNIQUE player, cached."""
    hist_cache, supp_cache = {}, {}
    career_minutes, n_real_mv = [], []
    for _, r in df.iterrows():
        name = r['player_name']
        cur_start = _start_year(r['feature_season'])

        if name not in hist_cache:
            hist_cache[name] = load_player_history(name)
        h = hist_cache[name]
        cm = 0.0
        if not h.empty and 'minutes' in h.columns and 'season' in h.columns:
            prior = h[h['season'].astype(str).apply(lambda s: _start_year(s) < cur_start)]
            cm = float(pd.to_numeric(prior['minutes'], errors='coerce').fillna(0).sum())
        career_minutes.append(cm)

        if name not in supp_cache:
            supp_cache[name] = load_player_supplementary_history(name)
        s = supp_cache[name]
        nmv = 0
        if not s.empty and 'market_value_eur' in s.columns and 'season' in s.columns:
            mv = pd.to_numeric(s['market_value_eur'], errors='coerce').fillna(0)
            prior_mask = s['season'].astype(str).apply(lambda ss: _start_year(ss) < cur_start) & (mv > 0)
            nmv = int(prior_mask.sum())
        n_real_mv.append(nmv)

    df = df.copy()
    df['career_minutes_to_date'] = career_minutes
    df['n_real_mv_seasons_to_date'] = n_real_mv
    df['current_season_minutes'] = np.expm1(df['log_minutes'].values)
    return df


def _group_report(df, mask, proba, name):
    sub_y = df.loc[mask, 'label'].values
    sub_p = proba[mask.values] if hasattr(mask, 'values') else proba[mask]
    if len(sub_y) == 0:
        return {'group': name, 'n': 0}
    pred = (sub_p >= config.RISK_SELL_HIGH_DETERIORATION_PROB_THRESHOLD).astype(int)
    tp = int(((pred == 1) & (sub_y == 1)).sum())
    fp = int(((pred == 1) & (sub_y == 0)).sum())
    n_flagged = tp + fp
    precision = round(tp / n_flagged, 3) if n_flagged > 0 else None
    from sklearn.metrics import roc_auc_score
    auc = round(float(roc_auc_score(sub_y, sub_p)), 3) if len(set(sub_y.tolist())) > 1 else None
    return {
        'group': name,
        'n': int(len(sub_y)),
        'actual_positive_rate': round(float(sub_y.mean()), 3),
        'n_flagged_at_0.5': n_flagged,
        'precision_at_0.5': precision,
        'roc_auc_within_group': auc,
        'mean_predicted_probability': round(float(sub_p.mean()), 3),
    }


def run_analysis(seasons=None):
    train_df, reference = build_training_rows(seasons=seasons)
    if train_df.empty:
        print('No training rows.')
        return

    # Temporal split (same as train_sell_high_model) so labels/backtest stay
    # leakage-safe, and so the backtest section can specifically use the
    # held-out years, matching this project's standing methodology.
    label_years = train_df['label_season'].apply(_start_year).values
    distinct_years = sorted(set(label_years))
    n_holdout = config.SELL_HIGH_TEMPORAL_HOLDOUT_SEASONS
    cutoff_years = set(distinct_years[-n_holdout:])
    test_mask = pd.Series(np.isin(label_years, list(cutoff_years)), index=train_df.index)
    train_mask = ~test_mask

    _apply_residual_labels(train_df, train_mask.values, config.SELL_HIGH_DECLINE_QUANTILE)

    bundle = load_model()
    model = bundle['model']
    cols = bundle['feature_cols']
    X = train_df[cols].values.astype(float)
    proba = model.predict_proba(X)[:, 1]

    at_peak = train_df['distance_from_peak_mv'] >= AT_PEAK_LOG_THRESHOLD
    print(f"Full population: {len(train_df)} rows. At/near-peak (>= {config.RISK_SELL_HIGH_PEAK_RATIO} of "
          f"peak-to-date): {int(at_peak.sum())} rows.")

    peak_df = train_df.loc[at_peak].copy()
    peak_proba = proba[at_peak.values]
    peak_df = _established_proxies(peak_df)

    print("\n=== Established-ness proxy distributions (at/near-peak population) ===")
    for col in ('age', 'career_minutes_to_date', 'n_real_mv_seasons_to_date', 'current_season_minutes'):
        print(f"{col}: {peak_df[col].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_dict()}")

    # Four established-ness groups. Cutoffs are data-driven from the
    # printed percentiles above, not guessed.
    low_experience = (peak_df['career_minutes_to_date'] < 3000) | (peak_df['n_real_mv_seasons_to_date'] < 2)
    young = peak_df['age'] <= 21
    prime = (peak_df['age'] > 24) & (peak_df['age'] <= 30)
    aging = peak_df['age'] > 30

    groups = {
        'young_prospect (age<=21, low experience)': young & low_experience,
        'established_young_star (age<=21, NOT low experience)': young & ~low_experience,
        'established_prime_age (24<age<=30)': prime,
        'aging (age>30)': aging,
    }

    print("\n=== Group comparison (full at-peak population, all seasons) ===")
    report = {'full_population': {}}
    for name, mask in groups.items():
        r = _group_report(peak_df, mask, peak_proba, name)
        report['full_population'][name] = r
        print(json.dumps(r, indent=2))

    # Backtest: same groups, restricted to the temporal holdout - the
    # honest, forward-in-time check, not the full mix above (included
    # mainly for stable group sizes/rates).
    peak_test_mask = at_peak & test_mask
    peak_test_df = train_df.loc[peak_test_mask].copy()
    peak_test_proba = proba[peak_test_mask.values]
    peak_test_df = _established_proxies(peak_test_df)

    low_experience_t = (peak_test_df['career_minutes_to_date'] < 3000) | (peak_test_df['n_real_mv_seasons_to_date'] < 2)
    young_t = peak_test_df['age'] <= 21
    groups_t = {
        'young_prospect': young_t & low_experience_t,
        'established_young_star': young_t & ~low_experience_t,
        'established_prime_age': (peak_test_df['age'] > 24) & (peak_test_df['age'] <= 30),
        'aging': peak_test_df['age'] > 30,
    }
    print("\n=== Backtest: same groups, TEMPORAL HOLDOUT ONLY ===")
    report['temporal_holdout'] = {}
    for name, mask in groups_t.items():
        r = _group_report(peak_test_df, mask, peak_test_proba, name)
        report['temporal_holdout'][name] = r
        print(json.dumps(r, indent=2))

    # The actual proposed-rule backtest: with vs without excluding
    # low-experience rows from triggering, on the holdout's at-peak
    # population specifically (mirrors exactly what risk.py would do).
    print("\n=== Proposed rule backtest (temporal holdout, at-peak population) ===")
    pred_all = (peak_test_proba >= config.RISK_SELL_HIGH_DETERIORATION_PROB_THRESHOLD).astype(int)
    y_all = peak_test_df['label'].values
    low_exp_mask = low_experience_t.values

    def _prf(pred, y):
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else None
        recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else None
        return {'n_flagged': tp + fp, 'tp': tp, 'fp': fp, 'precision': precision, 'recall': recall}

    before = _prf(pred_all, y_all)
    pred_gated = pred_all.copy()
    pred_gated[low_exp_mask] = 0
    after = _prf(pred_gated, y_all)
    removed_flags = int(((pred_all == 1) & low_exp_mask).sum())
    removed_correct = int(((pred_all == 1) & low_exp_mask & (y_all == 1)).sum())
    rule_report = {
        'before_gate': before, 'after_gate': after,
        'flags_removed_by_gate': removed_flags,
        'of_those_removed_actually_deteriorated': removed_correct,
    }
    report['proposed_rule_backtest'] = rule_report
    print(json.dumps(rule_report, indent=2))

    return report


if __name__ == '__main__':
    loader.boot()
    run_analysis()
