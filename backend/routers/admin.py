#!/usr/bin/env python3
"""
Admin routes - operational/research actions, gated behind X-Admin-Token.
Call the same plain functions scripts/*.py's CLI entrypoints call.
Set ADMIN_TOKEN in production; falls back to a dev token locally.
"""

import json
import os
import sys

_ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_ROUTERS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

import config as backend_config
from backend.config_inspector import get_config_groups
from data.schemas import (
    BacktestResponse, ConfigGroupsResponse, ModelManagementResponse, ModelRetrainRequest,
    ModelRetrainResponse, ModelStatus, SensitivityResponse,
)
from scripts.retrain_market_value import retrain_market_value
from scripts.retrain_sell_high_risk import retrain_sell_high_risk
from scripts.retrain_style_clusters import retrain_style_clusters
from scripts.run_backtest import run_backtest, ALL_POSITIONS
from scripts.run_sensitivity import run_sensitivity
from ml.market_value import train as mv_train, predict as mv_predict
from ml.sell_high_risk import train as sell_high_train, predict as sell_high_predict
from ml.style_clustering import train as style_train, predict as style_predict
from ml.style_clustering.features import POSITION_GROUPS, EXCLUDED_CLUSTER_CATEGORIES_BY_POS

ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'dev-admin-token')


def require_admin_token(x_admin_token: Optional[str] = Header(None)):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail='missing or invalid X-Admin-Token header')


router = APIRouter(prefix='/admin', tags=['admin'], dependencies=[Depends(require_admin_token)])


def _read_json(path):
    """The raw contents of a meta.json sidecar, or None if missing or
    unparseable - either way the admin panel should show "not trained"
    rather than a 500."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _market_value_status() -> ModelStatus:
    meta = _read_json(mv_train.META_PATH)
    return ModelStatus(
        key='market_value',
        label='Market Value (GBM)',
        trained=meta is not None,
        meta=meta or {},
        config={
            'prior_mv_confidence_brackets': list(backend_config.MV_PRIOR_MV_CONFIDENCE_BRACKETS),
            'confidence_tier_high_min_n': backend_config.MV_CONFIDENCE_TIER_HIGH_MIN_N,
            'confidence_tier_medium_min_n': backend_config.MV_CONFIDENCE_TIER_MEDIUM_MIN_N,
        },
    )


def _sell_high_risk_status() -> ModelStatus:
    meta = _read_json(sell_high_train.META_PATH)
    return ModelStatus(
        key='sell_high_risk',
        label='Sell-High Risk (GBM Classifier)',
        trained=meta is not None,
        meta=meta or {},
    )


def _style_clustering_status() -> ModelStatus:
    # One meta.json per position group (FW/MF/DF - GK is never clustered,
    # see ml.style_clustering.features' module docstring), so `meta` here
    # is {position: that position's own meta_dict}, not a single flat dict.
    per_position = {}
    for pos in POSITION_GROUPS:
        m = _read_json(style_train.meta_path(pos))
        if m is not None:
            per_position[pos] = m
    config_by_position = {
        pos: {
            'distance_metric': backend_config.STYLE_CLUSTER_DISTANCE_METRIC.get(pos, 'euclidean'),
            'negative_weight': backend_config.STYLE_CLUSTER_NEGATIVE_WEIGHT.get(pos),
            'excluded_categories': list(EXCLUDED_CLUSTER_CATEGORIES_BY_POS.get(pos, ())),
            'k_override': backend_config.STYLE_CLUSTER_K_OVERRIDE.get(pos),
        }
        for pos in POSITION_GROUPS
    }
    return ModelStatus(
        key='style_clustering',
        label='Style Clustering (K-means)',
        trained=bool(per_position),
        meta=per_position,
        config=config_by_position,
    )


@router.get('/models', response_model=ModelManagementResponse)
def admin_models():
    """Last-training-run status for all three currently-trained models -
    read directly from each training script's own meta.json sidecar(s),
    nothing recomputed here (see ModelStatus's docstring)."""
    return ModelManagementResponse(models=[
        _market_value_status(),
        _sell_high_risk_status(),
        _style_clustering_status(),
    ])


def _retrain_style_clustering(body: ModelRetrainRequest):
    k_range = None
    if body.k_min is not None or body.k_max is not None:
        default_range = list(backend_config.STYLE_CLUSTER_K_RANGE)
        k_min = body.k_min if body.k_min is not None else default_range[0]
        k_max = body.k_max if body.k_max is not None else default_range[-1]
        k_range = range(k_min, k_max + 1)
    return retrain_style_clusters(seasons=body.seasons, min_minutes=body.min_minutes, k_range=k_range)


# (internal model key, retrain callable, predict-module reload callable) -
# one entry per /admin/models/{key}/retrain route. The reload callable
# makes a retrain take effect without a server restart.
_MODEL_RETRAIN_HANDLERS = {
    'market-value': ('market_value', lambda body: retrain_market_value(seasons=body.seasons), mv_predict.reload_model),
    'sell-high-risk': (
        'sell_high_risk', lambda body: retrain_sell_high_risk(seasons=body.seasons), sell_high_predict.reload_model,
    ),
    'style-clustering': ('style_clustering', _retrain_style_clustering, style_predict.reload_model),
}


@router.post('/models/{key}/retrain', response_model=ModelRetrainResponse)
def admin_retrain_model(key: str, body: ModelRetrainRequest = ModelRetrainRequest()):
    """Retrain one of the three models via its existing retrain script,
    then reload the fresh artifact into this process's live model cache -
    takes effect in predictions immediately, not just on disk."""
    if key not in _MODEL_RETRAIN_HANDLERS:
        raise HTTPException(status_code=404, detail=f'unknown model key: {key!r}')
    model_key, retrain_fn, reload_fn = _MODEL_RETRAIN_HANDLERS[key]

    meta = retrain_fn(body)
    reload_fn()

    if isinstance(meta, dict) and 'error' in meta:
        return ModelRetrainResponse(key=model_key, error=meta['error'])
    if key == 'style-clustering' and isinstance(meta, dict) and meta and all(
        isinstance(v, dict) and 'error' in v for v in meta.values()
    ):
        # Every position group failed (e.g. not enough data at all) -
        # surface that as a top-level error too, in addition to the
        # per-position errors already inside meta.
        return ModelRetrainResponse(key=model_key, meta=meta, error='every position group failed to train')
    return ModelRetrainResponse(key=model_key, meta=meta if isinstance(meta, dict) else {})


@router.get('/backtest', response_model=BacktestResponse)
def admin_backtest(
    season: Optional[List[str]] = Query(None, description='Flag season(s) to test (default: all available)'),
    position: Optional[List[str]] = Query(None, description='Position(s) to test (default: all four)'),
    horizon: int = 1,
    league: Optional[str] = None,
):
    """Backtest the hidden-gem detector across every available season pair
    (or the given ones) and position(s), via scripts.run_backtest."""
    positions = position or None
    if positions:
        bad = [p for p in positions if p not in ALL_POSITIONS]
        if bad:
            raise HTTPException(status_code=422, detail=f'invalid position(s): {bad}')
    report = run_backtest(seasons=season, positions=positions, horizon=horizon, league=league)
    return BacktestResponse(**report)


@router.get('/sensitivity', response_model=SensitivityResponse)
def admin_sensitivity(
    season: str,
    position: str,
    league: Optional[str] = None,
    pct: float = 0.20,
    top_n: int = 10,
    min_minutes: float = 450,
):
    """Composite/moneyball weight rank-stability report for one
    (season, position[, league]) pool, via scripts.run_sensitivity."""
    report = run_sensitivity(season, position, league=league, pct=pct, top_n=top_n, min_minutes=min_minutes)
    return SensitivityResponse(**report)


@router.get('/config', response_model=ConfigGroupsResponse)
def admin_config():
    """Read-only, grouped view of every tunable constant in
    backend/config.py, parsed live from the file (see config_inspector.py).
    No editing here - several constants only take effect on the next retrain (see scripts.retrain_*)."""
    return ConfigGroupsResponse(groups=get_config_groups(backend_config))
