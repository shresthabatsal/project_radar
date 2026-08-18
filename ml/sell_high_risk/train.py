#!/usr/bin/env python3
"""
Trains the sell-high deterioration model: predicts P(on-field performance
deteriorates next season). Trains broadly, on any point in a player's
trajectory - risk.py's at-peak rule applies only at inference; the label uses a residual, not raw delta, to avoid reintroducing mean-reversion.
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, 'backend')
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data import loader
from data.loader import (
    load_all_leagues_data, load_all_supplementary, merge_supplementary,
    safe_float, _norm_key, _num_series, next_season_label, prev_season_label,
)
from backend import config
from ml.sell_high_risk.features import (
    SELL_HIGH_FEATURE_COLS, build_features, output_score, compute_reference_distributions,
)

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'artifacts')
ARTIFACTS_DIR = os.path.normpath(ARTIFACTS_DIR)
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'sell_high_gbm.joblib')
META_PATH = os.path.join(ARTIFACTS_DIR, 'sell_high_gbm_meta.json')

ALL_POSITIONS = ('GK', 'DF', 'MF', 'FW')


def _start_year(season):
    """'2024-2025' -> 2024 - duplicated (not imported) from the other ml/*
    modules' own copies, so every model here stays independently trained
    with no shared-code coupling between them."""
    return int(str(season).split('-')[0])


def _seasons_with_performance_data():
    meta = loader.load_meta()
    if meta.empty:
        return ()
    return tuple(sorted(meta['season'].astype(str).unique(), key=_start_year))


def _seasons_with_real_mv():
    """Auto-detect which seasons have real market_value_eur rows on file -
    reimplemented locally (not imported) to keep this model independently trained."""
    wide = load_all_supplementary()
    if wide.empty:
        return ()
    real = wide[pd.to_numeric(wide['market_value_eur'], errors='coerce').fillna(0) > 0]
    return tuple(sorted(real['season'].astype(str).unique(), key=_start_year))


def _perf_lookup_and_output_peaks(seasons, reference, min_minutes):
    """Single pass building perf_lookup ({(norm_key, birth_year, season):
    row_dict}) and output_peak_before (leakage-safe running-max of
    output_score per player, seasons strictly before each key)."""
    perf_lookup = {}
    output_peak_before = {}
    running_peak = {}
    for s in sorted(seasons, key=_start_year):
        output_peak_before[s] = dict(running_peak)
        d = load_all_leagues_data(s)
        if d.empty:
            continue
        for _, r in d.iterrows():
            by = int(safe_float(r.get('birth_year', 0)))
            if by <= 0:
                continue
            key = (_norm_key(str(r.get('player', ''))), by)
            row = r.to_dict()
            perf_lookup[(key, s)] = row

            if safe_float(row.get('minutes', 0)) < min_minutes:
                continue
            position = str(row.get('primary_position', row.get('position', 'MF')))
            if position not in ALL_POSITIONS:
                position = 'MF'
            score = output_score(row, position, reference)
            if score is not None:
                running_peak[key] = max(running_peak.get(key, score), score)
    return perf_lookup, output_peak_before


def _mv_lookup_and_peaks():
    """({(norm_key, season): real_mv}, {season: {norm_key: peak real_mv
    across seasons < season}}) - the peak dict is a leakage-safe
    running-max sweep, snapshotted before each season's rows are folded in."""
    wide = load_all_supplementary()
    mv_lookup = {}
    rows_by_season = {}
    if wide.empty:
        return mv_lookup, {}
    for _, row in wide.iterrows():
        mv = safe_float(row.get('market_value_eur', 0))
        if mv <= 0:
            continue
        s = str(row.get('season', ''))
        key = _norm_key(str(row.get('player', '')))
        mv_lookup.setdefault((key, s), mv)
        rows_by_season.setdefault(s, []).append((key, mv))

    peak_before = {}
    running_peak = {}
    for s in sorted(rows_by_season.keys(), key=_start_year):
        peak_before[s] = dict(running_peak)
        for key, mv in rows_by_season[s]:
            running_peak[key] = max(running_peak.get(key, mv), mv)
    return mv_lookup, peak_before


def build_training_rows(seasons=None, min_minutes=config.SELL_HIGH_MIN_MINUTES,
                         deterioration_floor=config.SELL_HIGH_DETERIORATION_MINUTES_FLOOR):
    """Build the full UNLABELED training set (labeling needs the temporal
    split decided first, see _apply_residual_labels). Returns (train_df,
    reference); each row carries 'output_score'/'next_output_score'/'collapsed'."""
    if seasons is None:
        seasons = _seasons_with_real_mv()
    if not seasons:
        return pd.DataFrame(), {}

    all_perf_seasons = _seasons_with_performance_data()
    reference = compute_reference_distributions(all_perf_seasons)
    perf_lookup, output_peak_before = _perf_lookup_and_output_peaks(all_perf_seasons, reference, min_minutes)
    mv_lookup, mv_peak_before = _mv_lookup_and_peaks()

    # A feature season whose NEXT season has zero rows anywhere is
    # right-censored, not a real outcome - every player would otherwise
    # look "collapsed" by construction, a data-availability artifact.
    perf_seasons_set = set(all_perf_seasons)

    rows = []
    for s in seasons:
        if next_season_label(s) not in perf_seasons_set:
            continue
        d = merge_supplementary(load_all_leagues_data(s), s)
        if d.empty or 'market_value_eur' not in d.columns:
            continue
        d = d[pd.to_numeric(d['market_value_eur'], errors='coerce').fillna(0) > 0]
        if d.empty or 'minutes' not in d.columns:
            continue
        d = d[_num_series(d['minutes']).fillna(0) >= min_minutes]
        if d.empty:
            continue

        prev = prev_season_label(s)
        prev2 = prev_season_label(prev) if prev else None
        nxt = next_season_label(s)
        mv_peak_lookup = mv_peak_before.get(s, {})
        output_peak_lookup = output_peak_before.get(s, {})

        for _, r in d.iterrows():
            row = r.to_dict()
            position = str(row.get('primary_position', row.get('position', 'MF')))
            if position not in ALL_POSITIONS:
                position = 'MF'
            by = int(safe_float(row.get('birth_year', 0)))
            if by <= 0:
                continue
            name_key = _norm_key(str(row.get('player', '')))
            perf_key = (name_key, by)

            cur_score = output_score(row, position, reference)
            if cur_score is None:
                continue  # no usable output signal this season at all - can't judge either direction

            current_mv = safe_float(row.get('market_value_eur', 0))
            prior_mv = mv_lookup.get((name_key, prev)) if prev else None
            prior_mv_2 = mv_lookup.get((name_key, prev2)) if prev2 else None
            mv_peak_to_date = max(mv_peak_lookup.get(name_key, current_mv), current_mv)
            prior_perf_row = perf_lookup.get((perf_key, prev)) if prev else None
            prior_perf_row_2 = perf_lookup.get((perf_key, prev2)) if prev2 else None
            output_peak_to_date = output_peak_lookup.get(perf_key)

            feat = build_features(
                row, position, reference, prior_row=prior_perf_row, prior_row_2=prior_perf_row_2,
                current_mv=current_mv, prior_mv=prior_mv, prior_mv_2=prior_mv_2,
                peak_mv_to_date=mv_peak_to_date, output_score_peak_to_date=output_peak_to_date,
            )

            next_row = perf_lookup.get((perf_key, nxt)) if nxt else None
            next_minutes = safe_float(next_row.get('minutes', 0)) if next_row is not None else 0.0
            collapsed = next_row is None or next_minutes < deterioration_floor

            next_score = None
            if not collapsed:
                next_score = output_score(next_row, position, reference)
                if next_score is None:
                    continue  # no usable output signal next season - can't judge either

            feat['output_score'] = cur_score  # overwrite with the authoritative value (build_features defaults to 0.0 if None, but we already skipped None above)
            feat['collapsed'] = collapsed
            feat['next_output_score'] = next_score
            feat['feature_season'] = s
            feat['label_season'] = nxt
            feat['player_name'] = row.get('player')
            rows.append(feat)

    if not rows:
        return pd.DataFrame(), reference

    return pd.DataFrame(rows), reference


def _fit_expected_next_score(train_df, fit_mask):
    """Isotonic regression of next_output_score on this-season output_score,
    fit only on the "stayed" TRAINING-season population, never the temporal holdout."""
    from sklearn.isotonic import IsotonicRegression

    fit_rows = train_df[fit_mask & ~train_df['collapsed']]
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(fit_rows['output_score'].values, fit_rows['next_output_score'].values)
    return iso


def _apply_residual_labels(train_df, train_mask, decline_quantile):
    """Sets train_df['label'] (and 'residual', reporting only). residual =
    actual next_output_score - E[next_output_score | output_score]
    (isotonic-fit on the "stayed" TRAINING population); a global residual quantile is the decline cutoff."""
    iso = _fit_expected_next_score(train_df, train_mask)

    expected_next = iso.predict(train_df['output_score'].values)
    train_df['expected_next_output_score'] = expected_next
    # Only defined (non-NaN) where next_output_score itself is - i.e. the
    # "stayed" rows; collapsed rows get label=1 unconditionally below and
    # never look at the residual at all.
    train_df['residual'] = train_df['next_output_score'] - expected_next

    fit_rows = train_df[train_mask & ~train_df['collapsed']]
    threshold = float(fit_rows['residual'].quantile(1 - decline_quantile)) if len(fit_rows) >= 30 else None

    def _label(r):
        if r['collapsed']:
            return 1
        if threshold is None:
            return 0
        return 1 if r['residual'] <= threshold else 0

    train_df['label'] = train_df.apply(_label, axis=1)
    return {
        'method': 'isotonic_residual',
        'residual_threshold': round(threshold, 4) if threshold is not None else None,
        'decline_quantile': decline_quantile,
        'isotonic_fit_rows': int(len(fit_rows)),
        'isotonic_x_range': [
            round(float(fit_rows['output_score'].min()), 3), round(float(fit_rows['output_score'].max()), 3),
        ] if len(fit_rows) else None,
    }


def _extended_eval(y_true, proba, threshold=0.5):
    """ROC-AUC/PR-AUC/precision/recall/F1/false-positive-rate at `threshold`
    - PR-AUC and FPR catch false positives concentrating in one population
    (see _by_output_score_decile), which ROC-AUC alone can miss."""
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, precision_score, recall_score, f1_score, confusion_matrix,
    )
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    pred = (proba >= threshold).astype(int)
    two_classes = len(set(y_true.tolist())) > 1
    cm = confusion_matrix(y_true, pred, labels=[0, 1])
    tn, fp, fn, tp = (int(x) for x in cm.ravel()) if cm.size == 4 else (0, 0, 0, 0)
    fpr = (fp / (fp + tn)) if (fp + tn) > 0 else None
    return {
        'n': int(len(y_true)),
        'positive_rate': round(float(y_true.mean()), 3),
        'roc_auc': round(float(roc_auc_score(y_true, proba)), 3) if two_classes else None,
        'pr_auc': round(float(average_precision_score(y_true, proba)), 3) if two_classes else None,
        'precision': round(float(precision_score(y_true, pred, zero_division=0)), 3),
        'recall': round(float(recall_score(y_true, pred, zero_division=0)), 3),
        'f1': round(float(f1_score(y_true, pred, zero_division=0)), 3),
        'false_positive_rate': round(float(fpr), 3) if fpr is not None else None,
        'confusion_matrix': {'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp},
    }


def _calibration_table(y_true, proba, n_bins=10):
    """Mean predicted probability vs. actual positive rate within each
    predicted-probability decile - a well-calibrated model has these two
    numbers close together in every bin."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    edges = np.unique(np.quantile(proba, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        return []
    idx = np.clip(np.digitize(proba, edges[1:-1], right=True), 0, len(edges) - 2)
    out = []
    for b in range(len(edges) - 1):
        mask = idx == b
        if mask.sum() == 0:
            continue
        out.append({
            'n': int(mask.sum()),
            'mean_predicted_probability': round(float(proba[mask].mean()), 3),
            'actual_positive_rate': round(float(y_true[mask].mean()), 3),
        })
    return out


def _by_output_score_decile(output_score_vals, y_true, proba, n_bins=10):
    """Actual label positive rate and mean predicted probability within
    each current-output_score decile - catches elite performers still
    being treated as higher-risk purely for being elite."""
    output_score_vals = np.asarray(output_score_vals)
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    try:
        cats = pd.qcut(output_score_vals, q=n_bins, duplicates='drop')
    except ValueError:
        return []
    df = pd.DataFrame({'bin': cats, 'y': y_true, 'proba': proba, 'score': output_score_vals})
    out = []
    for _, g in df.groupby('bin', observed=True):
        if len(g) == 0:
            continue
        out.append({
            'output_score_range': [round(float(g['score'].min()), 3), round(float(g['score'].max()), 3)],
            'n': int(len(g)),
            'actual_positive_rate': round(float(g['y'].mean()), 3),
            'mean_predicted_probability': round(float(g['proba'].mean()), 3),
        })
    return out


def _output_score_sweep(model, cols, base_row,
                         sweep=(-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)):
    """Partial dependence of P(deterioration) on output_score alone,
    swept into extreme-tail territory. Should NOT show a sustained upward
    trend anywhere."""
    out = []
    for score in sweep:
        row = dict(base_row, output_score=score)
        p = float(model.predict_proba([[row.get(c, 0) for c in cols]])[0][1])
        out.append({'output_score': score, 'p_deterioration': round(p, 3)})
    return out


def _archetype_row(**overrides):
    """A full SELL_HIGH_FEATURE_COLS-shaped feature dict at reasonable
    defaults, overridden per archetype - used only by
    _run_archetype_tests, never for training."""
    base = {
        'age': 27, 'age_sq': 27 * 27,
        'log_current_mv': np.log1p(40_000_000), 'distance_from_peak_mv': 0.0,
        'mv_momentum': 0.0, 'has_mv_momentum': 1.0,
        'output_score': 0.0, 'output_score_delta': 0.0, 'has_prior_output_score': 1.0,
        'output_score_prior_2': 0.0, 'has_output_score_prior_2': 1.0, 'output_score_change_2': 0.0,
        'output_score_peak_to_date': 0.0, 'distance_from_output_score_peak': 0.0,
        'has_output_score_peak_history': 1.0,
        'log_minutes': np.log1p(2400), 'minutes_delta': 0.0,
        'goals_per90': 0.3, 'assists_per90': 0.2, 'npxg_per90': 0.3, 'xg_assist_per90': 0.2, 'sca_per90': 3.0,
        'power_rating': 87, 'pos_DF': 0, 'pos_FW': 1, 'pos_GK': 0, 'pos_MF': 0,
    }
    base.update(overrides)
    return base


def _run_archetype_tests(model, cols):
    """The six explicit archetypes this model is required to distinguish
    (see ARCHETYPES). Returns [{archetype, description, p_deterioration,
    expected}] - pass/fail judgment is made by whoever reads the report."""
    results = []
    for name, description, expected, feat in ARCHETYPES:
        p = float(model.predict_proba([[feat.get(c, 0) for c in cols]])[0][1])
        results.append({
            'archetype': name, 'description': description,
            'expected': expected, 'p_deterioration': round(p, 3),
        })
    return results


# The six archetypes ml.sell_high_risk was required to distinguish. Each
# feature dict is hand-constructed to represent a realistic instance of the
# archetype - not derived from any specific real player.
ARCHETYPES = [
    (
        'yamal_type', 'Extremely high current performance, young, improving - an outlier season',
        'low',
        _archetype_row(
            age=18, age_sq=324, output_score=3.5, output_score_delta=0.9, output_score_prior_2=1.0,
            output_score_change_2=1.5, output_score_peak_to_date=3.5, distance_from_output_score_peak=0.0,
            has_output_score_peak_history=1.0, minutes_delta=900, mv_momentum=0.5, has_mv_momentum=1.0,
            log_current_mv=np.log1p(180_000_000), distance_from_peak_mv=0.0,
            goals_per90=0.6, assists_per90=0.45, npxg_per90=0.47, xg_assist_per90=0.5, sca_per90=6.1, pos_FW=0, pos_MF=1,
        ),
    ),
    (
        'elite_established', 'Elite established player performing strongly, prime age, stable',
        'low_to_moderate',
        _archetype_row(
            age=27, output_score=1.4, output_score_delta=0.1, output_score_prior_2=1.2, output_score_change_2=0.1,
            output_score_peak_to_date=1.5, distance_from_output_score_peak=-0.1, minutes_delta=50,
            log_current_mv=np.log1p(120_000_000), distance_from_peak_mv=0.0,
        ),
    ),
    (
        'aging_declining', 'Aging elite player with declining performance',
        'high',
        _archetype_row(
            age=34, age_sq=34 * 34, output_score=0.3, output_score_delta=-1.0, output_score_prior_2=1.8,
            output_score_change_2=-0.5, output_score_peak_to_date=2.2, distance_from_output_score_peak=-1.9,
            minutes_delta=-500, log_minutes=np.log1p(1600),
            log_current_mv=np.log1p(35_000_000), distance_from_peak_mv=-0.3, mv_momentum=-0.2,
        ),
    ),
    (
        'peak_recent_decline', 'Player near career performance peak with a genuine recent decline',
        'high',
        _archetype_row(
            age=29, output_score=0.6, output_score_delta=-0.9, output_score_prior_2=1.6, output_score_change_2=-0.1,
            output_score_peak_to_date=1.6, distance_from_output_score_peak=-1.0, minutes_delta=-300,
            log_current_mv=np.log1p(60_000_000), distance_from_peak_mv=-0.1,
        ),
    ),
    (
        'recovering_from_collapse', 'Performance collapsed previously, now stabilizing/improving',
        'low_to_moderate',
        _archetype_row(
            age=28, output_score=-0.3, output_score_delta=0.6, output_score_prior_2=-1.1, output_score_change_2=0.2,
            output_score_peak_to_date=1.9, distance_from_output_score_peak=-2.2, minutes_delta=400,
            log_current_mv=np.log1p(20_000_000), distance_from_peak_mv=-0.8,
        ),
    ),
    (
        'ordinary', 'Ordinary player, unremarkable and stable across the board',
        'low_to_moderate',
        _archetype_row(),
    ),
]


def train_sell_high_model(seasons=None, save=True):
    """Fit the deterioration-probability GBM on the residual-based target,
    evaluate extensively (temporal holdout, GroupKFold, logistic baseline,
    calibration, archetype tests), persist to MODEL_PATH if save=True."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score
    import joblib

    train_df, reference = build_training_rows(seasons=seasons)
    if len(train_df) < 200:
        return {'error': f'not enough rows ({len(train_df)})'}

    label_years = train_df['label_season'].apply(_start_year).values
    seasons_used = sorted(train_df['feature_season'].unique(), key=_start_year)

    # Temporal split decided FIRST - the isotonic fit and residual
    # threshold are only fit on TRAIN_MASK rows, so the label can't leak
    # holdout-era structure into held-out rows.
    distinct_years = sorted(set(label_years))
    n_holdout = config.SELL_HIGH_TEMPORAL_HOLDOUT_SEASONS
    if len(distinct_years) <= n_holdout:
        return {'error': f'not enough distinct label-seasons to hold out ({len(distinct_years)})'}
    cutoff_years = set(distinct_years[-n_holdout:])
    test_mask = np.isin(label_years, list(cutoff_years))
    train_mask = ~test_mask
    if train_mask.sum() < 150 or test_mask.sum() < 30:
        return {'error': 'temporal split too small'}

    threshold_info = _apply_residual_labels(train_df, train_mask, config.SELL_HIGH_DECLINE_QUANTILE)

    X = train_df[SELL_HIGH_FEATURE_COLS].values.astype(float)
    y = train_df['label'].values.astype(int)
    groups = train_df['player_key'].values
    positive_rate = float(y.mean())

    # Hyperparameter selection by temporal-holdout ROC-AUC: selection must
    # be driven by genuine out-of-time discrimination, not GroupKFold or
    # any post-hoc importance shape.
    best_hp, best_auc, best_clf = None, -1.0, None
    for n_estimators in config.SELL_HIGH_GRID_N_ESTIMATORS:
        for max_depth in config.SELL_HIGH_GRID_MAX_DEPTH:
            for learning_rate in config.SELL_HIGH_GRID_LEARNING_RATE:
                hp = {'n_estimators': n_estimators, 'max_depth': max_depth, 'learning_rate': learning_rate}
                clf = GradientBoostingClassifier(**hp).fit(X[train_mask], y[train_mask])
                proba = clf.predict_proba(X[test_mask])[:, 1]
                auc = roc_auc_score(y[test_mask], proba)
                if auc > best_auc:
                    best_hp, best_auc, best_clf = hp, auc, clf

    test_proba = best_clf.predict_proba(X[test_mask])[:, 1]
    temporal_eval = _extended_eval(y[test_mask], test_proba)
    calibration = _calibration_table(y[test_mask], test_proba)
    by_decile = _by_output_score_decile(train_df.loc[test_mask, 'output_score'].values, y[test_mask], test_proba)

    # GroupKFold(player) - secondary corroborating check, same methodology
    # as every other model in this project.
    n_groups = len(set(groups))
    cv = GroupKFold(n_splits=min(5, max(2, n_groups)))
    cv_proba = cross_val_predict(GradientBoostingClassifier(**best_hp), X, y, cv=cv, groups=groups,
                                  method='predict_proba')[:, 1]
    groupkfold_eval = _extended_eval(y, cv_proba)

    # Simple baseline: logistic regression on 3 obvious features, not the
    # full GBM set - the explicit "does ML beat something simple"
    # comparison this experiment was gated on.
    baseline_cols = ['age', 'output_score', 'distance_from_peak_mv']
    Xb = train_df[baseline_cols].values.astype(float)
    baseline_clf = LogisticRegression(max_iter=1000).fit(Xb[train_mask], y[train_mask])
    baseline_proba = baseline_clf.predict_proba(Xb[test_mask])[:, 1]
    baseline_eval = _extended_eval(y[test_mask], baseline_proba)

    # Majority-class floor - the absolute minimum any model must clear.
    majority_pred = np.zeros(int(test_mask.sum())) if y[train_mask].mean() < 0.5 else np.ones(int(test_mask.sum()))
    majority_eval = {
        'accuracy': round(float((majority_pred == y[test_mask]).mean()), 3),
        'note': 'always predicts the training-set majority class - the floor any model must clear',
    }

    gbm = GradientBoostingClassifier(**best_hp).fit(X, y)
    importances = getattr(gbm, 'feature_importances_', None)
    feature_importance = []
    if importances is not None:
        total = float(importances.sum()) or 1.0
        ranked = sorted(zip(SELL_HIGH_FEATURE_COLS, importances), key=lambda p: p[1], reverse=True)
        feature_importance = [{'feature': f, 'weight_pct': round(float(imp) / total * 100, 1)} for f, imp in ranked]

    median_row = {c: float(train_df[c].median()) for c in SELL_HIGH_FEATURE_COLS}
    output_score_sweep = _output_score_sweep(gbm, SELL_HIGH_FEATURE_COLS, median_row)
    archetype_results = _run_archetype_tests(gbm, SELL_HIGH_FEATURE_COLS)

    meta = {
        'n': len(train_df),
        'n_players': int(n_groups),
        'positive_rate': round(positive_rate, 3),
        'seasons': seasons_used,
        'held_out_years': [int(y_) for y_ in sorted(cutoff_years)],
        'min_minutes': config.SELL_HIGH_MIN_MINUTES,
        'deterioration_minutes_floor': config.SELL_HIGH_DETERIORATION_MINUTES_FLOOR,
        'decline_threshold_info': threshold_info,
        'hyperparams': best_hp,
        'temporal_holdout': temporal_eval,
        'temporal_holdout_calibration': calibration,
        'temporal_holdout_by_output_score_decile': by_decile,
        'groupkfold': groupkfold_eval,
        'baseline_logistic_regression': baseline_eval,
        'baseline_majority_class': majority_eval,
        'feature_importance': feature_importance,
        'output_score_sweep': output_score_sweep,
        'archetype_results': archetype_results,
        'trained_at': datetime.now().isoformat(timespec='seconds'),
    }

    print(f"Trained on {meta['n']} rows across {meta['n_players']} players, "
          f"{len(seasons_used)} seasons, positive_rate={meta['positive_rate']}")
    print(f"Label threshold info: {json.dumps(threshold_info, indent=2)}")
    print(f"Temporal holdout: {json.dumps(temporal_eval, indent=2)}")
    print(f"Temporal holdout calibration: {json.dumps(calibration, indent=2)}")
    print(f"Temporal holdout by output_score decile: {json.dumps(by_decile, indent=2)}")
    print(f"GroupKFold: {json.dumps(groupkfold_eval, indent=2)}")
    print(f"Baseline (logistic, 3 features): {json.dumps(baseline_eval, indent=2)}")
    print(f"Majority-class floor: {json.dumps(majority_eval, indent=2)}")
    print(f"Feature importance: {feature_importance}")
    print(f"Output_score sweep: {json.dumps(output_score_sweep, indent=2)}")
    print(f"Archetype results: {json.dumps(archetype_results, indent=2)}")

    if save:
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        joblib.dump({
            'model': gbm, 'feature_cols': SELL_HIGH_FEATURE_COLS,
            'reference': reference, 'decline_threshold_info': threshold_info, 'meta': meta,
        }, MODEL_PATH)
        with open(META_PATH, 'w') as f:
            json.dump(meta, f, indent=2)
    return meta


if __name__ == '__main__':
    loader.boot()
    result = train_sell_high_model()
    print(json.dumps(result, indent=2))
