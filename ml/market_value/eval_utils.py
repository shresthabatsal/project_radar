#!/usr/bin/env python3
"""
Shared evaluation machinery for the market-value model (predicts
log(current_mv / prior_mv), reconstructed as prior_mv * exp(pred)). Every
function takes a `model_factory` so the same methodology can target a different algorithm.
"""

import numpy as np

from backend import config


def start_year(season):
    """'2024-2025' -> 2024, for chronological sorting - same convention
    ml.style_clustering.train._all_seasons() uses."""
    return int(str(season).split('-')[0])


def _default_model_factory():
    from sklearn.ensemble import GradientBoostingRegressor
    return GradientBoostingRegressor


def select_hyperparams(X, y, groups, cv, model_factory=None):
    """Small grid search over (n_estimators, max_depth, learning_rate),
    scored by mean GroupKFold(player) R2. Returns (best_params, best_r2);
    best_params includes config.MV_GBM_RANDOM_STATE as 'random_state'."""
    from sklearn.model_selection import cross_val_score

    model_factory = model_factory or _default_model_factory()
    best_params, best_r2 = None, float('-inf')
    for n_estimators in config.GBM_GRID_N_ESTIMATORS:
        for max_depth in config.GBM_GRID_MAX_DEPTH:
            for learning_rate in config.GBM_GRID_LEARNING_RATE:
                params = {'n_estimators': n_estimators, 'max_depth': max_depth, 'learning_rate': learning_rate,
                          'random_state': config.MV_GBM_RANDOM_STATE}
                r2 = float(cross_val_score(model_factory(**params),
                                            X, y, cv=cv, groups=groups, scoring='r2').mean())
                if r2 > best_r2:
                    best_params, best_r2 = params, r2
    return best_params, best_r2


def evaluate(pred_eur, actual_eur, positions, anchor_eur):
    """Turn reconstructed-to-euro predictions into the full evaluation dict
    (MAE/RMSE/R2/MdAPE/directional-accuracy, by-position/by-bracket).
    MdAPE is the headline metric; directional accuracy catches wrong-sign predictions MdAPE alone can hide."""
    ape_pct = np.abs(pred_eur - actual_eur) / actual_eur * 100.0
    signed_pct = (pred_eur - actual_eur) / actual_eur * 100.0

    pred_dir = np.sign(np.where(np.abs(pred_eur - anchor_eur) / anchor_eur < 0.01, 0.0, pred_eur - anchor_eur))
    actual_dir = np.sign(np.where(np.abs(actual_eur - anchor_eur) / anchor_eur < 0.01, 0.0, actual_eur - anchor_eur))
    dir_match = pred_dir == actual_dir

    overall = round(float(np.median(ape_pct)), 1)
    by_position = {
        pos: round(float(np.median(ape_pct[positions == pos])), 1)
        for pos in sorted(set(positions)) if (positions == pos).sum() > 0
    }

    edges = config.MV_PRIOR_MV_CONFIDENCE_BRACKETS
    by_bracket = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (anchor_eur >= lo) & (anchor_eur < hi if hi is not None else True)
        if mask.sum() == 0:
            continue
        n = int(mask.sum())
        tier = ('high' if n >= config.MV_CONFIDENCE_TIER_HIGH_MIN_N
                else 'medium' if n >= config.MV_CONFIDENCE_TIER_MEDIUM_MIN_N else 'low')
        by_bracket.append({
            'anchor_mv_min': lo, 'anchor_mv_max': hi, 'n': n, 'tier': tier,
            'mdape_pct': round(float(np.median(ape_pct[mask])), 1),
            'mean_signed_pct': round(float(np.mean(signed_pct[mask])), 1),
            'directional_accuracy_pct': round(float(dir_match[mask].mean() * 100), 1),
        })

    mae = float(np.mean(np.abs(pred_eur - actual_eur)))
    rmse = float(np.sqrt(np.mean((pred_eur - actual_eur) ** 2)))
    ss_res = float(np.sum((actual_eur - pred_eur) ** 2))
    ss_tot = float(np.sum((actual_eur - actual_eur.mean()) ** 2))
    r2_euro = round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else None

    return {
        'n': int(len(actual_eur)),
        'mae_eur': round(mae, 0),
        'rmse_eur': round(rmse, 0),
        'r2_euro_space': r2_euro,
        'mdape_pct': overall,
        'directional_accuracy_pct': round(float(dir_match.mean() * 100), 1),
        'mdape_pct_by_position': by_position,
        'mdape_pct_by_bracket': by_bracket,
        'mdape_summary': f"Predictions are typically within {overall:.1f}% of actual market value.",
    }


def oof_evaluation_report(X, y_target, actual_eur, positions, anchor_eur, groups, cv, hyperparams,
                           model_factory=None):
    """Out-of-fold GroupKFold(player) predictions (never in-sample, which
    would understate error on a genuinely new player), reconstructed to
    euros via anchor_eur * exp(pred), then scored by evaluate()."""
    from sklearn.model_selection import cross_val_predict

    model_factory = model_factory or _default_model_factory()
    pred_log = cross_val_predict(model_factory(**hyperparams), X, y_target, cv=cv, groups=groups)
    pred_eur = anchor_eur * np.exp(pred_log)
    result = evaluate(pred_eur, actual_eur, positions, anchor_eur)
    result['cv'] = 'GroupKFold(player)'
    return result


def temporal_holdout_report(X, y_target, actual_eur, positions, anchor_eur, gate_years, hyperparams,
                             holdout_seasons=None, model_factory=None):
    """Genuine forward-in-time check: fit on rows outside the held-out
    `gate_years` window, evaluate on rows inside it. `gate_years` MUST be
    the row's LABEL-season year, or a future value leaks into training."""
    model_factory = model_factory or _default_model_factory()
    n_holdout = holdout_seasons if holdout_seasons is not None else config.MV_TEMPORAL_HOLDOUT_SEASONS
    distinct_years = sorted(set(gate_years))
    if len(distinct_years) <= n_holdout:
        return None
    cutoff_years = set(distinct_years[-n_holdout:])

    test_mask = np.isin(gate_years, list(cutoff_years))
    train_mask = ~test_mask
    if train_mask.sum() < 100 or test_mask.sum() < 20:
        return None

    model = model_factory(**hyperparams).fit(X[train_mask], y_target[train_mask])
    pred_eur = anchor_eur[test_mask] * np.exp(model.predict(X[test_mask]))
    result = evaluate(pred_eur, actual_eur[test_mask], positions[test_mask], anchor_eur[test_mask])
    # int(), not just sorted() - gate_years came through a pandas/numpy
    # column, so its elements are numpy.int64, not JSON-serializable.
    result['held_out_years'] = [int(y) for y in sorted(cutoff_years)]
    result['train_rows'] = int(train_mask.sum())
    return result
