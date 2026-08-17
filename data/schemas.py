#!/usr/bin/env python3
"""
Pydantic models for player records and shared request/response shapes
used across data/, backend/, and ml/. PlayerRecord/SupplementaryRecord
type identity fields explicitly and allow the rest through as extra fields.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

# ==============================================================================
# PLAYER RECORDS
# ==============================================================================


class PlayerRecord(BaseModel):
    """One player-season row from league_season_team_player_data
    (data/data_files/players.csv.gz), post standardize_positions()."""

    model_config = ConfigDict(extra="allow")

    player: str
    team: str
    season: str
    league: str
    position: Optional[str] = None
    primary_position: Optional[str] = None
    secondary_position: Optional[str] = None
    nationality: Optional[str] = None
    age: Optional[str] = None  # raw FBref "YY-DDD" format - see scout_engine.parse_age()
    birth_year: Optional[int] = None
    power_rating: Optional[float] = None  # league-strength-adjusted rating, PL=100
    games: Optional[int] = None
    games_starts: Optional[int] = None
    minutes: Optional[float] = None
    goals: Optional[float] = None
    assists: Optional[float] = None
    xg: Optional[float] = None
    npxg: Optional[float] = None
    xg_assist: Optional[float] = None


class SupplementaryRecord(BaseModel):
    """One player-season row from player_supplementary_data
    (data/data_files/supplementary.csv.gz) - wages, contract, market value."""

    model_config = ConfigDict(extra="allow")

    player: str
    team: str
    season: str
    league: str
    weekly_wage_eur: Optional[float] = None
    annual_wage_eur: Optional[float] = None
    contract_expiry: Optional[str] = None
    contract_signed: Optional[str] = None
    release_clause_eur: Optional[float] = None
    market_value_eur: Optional[float] = None
    market_value_date: Optional[str] = None
    transfermarkt_id: Optional[float] = None


# ==============================================================================
# SHARED REQUEST SHAPES
# ==============================================================================


class PlayerLookupRequest(BaseModel):
    """season + league + team + player - the identity used by player
    profile, similar-players, moneyball, wage-benchmark, and market-value lookups."""

    season: str
    league: str
    team: str
    player: str


class PositionScopeRequest(BaseModel):
    """season + position (+ optional league) - the scope used by hidden gems,
    contract opportunities and the squad optimizer (cmd_get_hidden_gems,
    cmd_get_contract_opportunities, cmd_get_squad_optimizer)."""

    season: str
    position: str
    league: Optional[str] = None


# ==============================================================================
# SHARED RESPONSE SHAPES
# ==============================================================================


class ErrorResponse(BaseModel):
    error: str


class MarketValueEstimate(BaseModel):
    """Returned alongside get_market_value()'s (value, is_estimated) tuple."""

    market_value: float
    market_value_label: str
    mv_estimated: bool


class ContractOpportunity(BaseModel):
    """Returned by contract_opportunity_breakdown(): urgency (less time left
    = more leverage) + release-clause discount, capped 0-100."""

    months: Optional[int] = None
    urgency: float
    clause: float
    total: float


class MoneyballScore(BaseModel):
    """Returned by cmd_get_moneyball_score(): performance + value-efficiency
    + contract-opportunity, blended per config.MONEYBALL_*_WEIGHT."""

    player: str
    position: str
    season: str
    moneyball_score: float
    performance_score: float
    perf_zaggregate: Optional[float] = None
    perf_style: Optional[float] = None
    perf_power: Optional[float] = None
    value_efficiency: float
    value_ratio_raw: Optional[float] = None
    value_capped: Optional[bool] = None
    wage_percentile: Optional[float] = None
    contract_opportunity: float
    contract_months: Optional[int] = None
    contract_urgency: Optional[float] = None
    contract_clause: Optional[float] = None
    wage: float
    wage_label: str
    wage_estimated: bool
    market_value: float
    market_value_label: str
    mv_estimated: bool


# ==============================================================================
# PLAYER LISTING / PROFILE
# ==============================================================================


class PlayerSummary(BaseModel):
    """One row of a GET /players listing. id is an opaque, decodable token
    (see backend/routers/_ids.py) - there's no real player ID, only the
    (season, league, team, player) tuple it encodes."""

    id: str
    player: str
    team: str
    league: str
    season: str
    position: str
    secondary_position: Optional[str] = None
    age: Optional[float] = None
    minutes: Optional[float] = None
    goals: Optional[float] = None
    assists: Optional[float] = None
    is_gem: Optional[bool] = None


class PlayersListResponse(BaseModel):
    players: List[PlayerSummary]
    total: int


class PlayerSearchResult(BaseModel):
    """One row of GET /players/search - a richer PlayerSummary with the
    nationality/market-value/wage/contract fields the advanced filters need,
    and composite_index (the default sort key)."""

    id: str
    player: str
    team: str
    league: str
    season: str
    position: str
    secondary_position: Optional[str] = None
    nationality: Optional[str] = None
    age: Optional[float] = None
    minutes: Optional[float] = None
    goals: Optional[float] = None
    assists: Optional[float] = None
    composite_index: Optional[float] = None
    market_value: Optional[float] = None
    market_value_label: Optional[str] = None
    wage: Optional[float] = None
    wage_label: Optional[str] = None
    contract_expiry: Optional[str] = None
    contract_months_remaining: Optional[int] = None
    release_clause: Optional[float] = None
    release_clause_label: Optional[str] = None
    # ml.style_clustering nearest-archetype label - only populated when the
    # `archetype` filter was actually requested: null here doesn't mean "no
    # archetype", it means this search call didn't ask for one.
    archetype_label: Optional[str] = None
    is_gem: Optional[bool] = None


class PlayerSearchResponse(BaseModel):
    players: List[PlayerSearchResult]
    total: int
    limit: int
    offset: int


class ArchetypeOption(BaseModel):
    """One selectable ml.style_clustering archetype - `label` is a real
    generated cluster label, never hardcoded. `position` scopes it to a
    broad position group (FW/MF/DF - GK has none)."""

    position: str
    cluster: int
    label: str


class PlayerFiltersResponse(BaseModel):
    """Returned by GET /players/filters: distinct team/nationality/league/
    position values present in the loaded dataset. archetypes comes from
    the currently-trained ml.style_clustering artifacts instead, season/league-independent."""

    teams: List[str] = []
    nationalities: List[str] = []
    leagues: List[str] = []
    positions: List[str] = []
    archetypes: List[ArchetypeOption] = []


class CategoryScore(BaseModel):
    category: str
    score: Optional[float] = None


class PlayerProfileBasic(BaseModel):
    player: str
    team: str
    league: str
    season: str
    position: str
    age: Optional[float] = None
    minutes: Optional[float] = None
    games: Optional[float] = None
    goals: Optional[float] = None
    assists: Optional[float] = None
    xg: Optional[float] = None
    xg_assist: Optional[float] = None
    weekly_wage_eur: Optional[float] = None
    annual_wage_eur: Optional[float] = None
    weekly_wage_label: Optional[str] = None
    annual_wage_label: Optional[str] = None
    contract_expiry: Optional[str] = None
    contract_signed: Optional[str] = None
    contract_months_remaining: Optional[int] = None
    release_clause_eur: Optional[float] = None
    release_clause_label: Optional[str] = None


class RiskReason(BaseModel):
    """One of backend.scoring.risk's four independent risk checks (contract/
    mileage_decline/sell_high/financial), each with its own trigger
    condition. Only fields relevant to `reason` are populated. Diagnostic only."""

    reason: str
    label: str
    triggered: bool
    detail: Optional[str] = None

    # contract
    months_remaining: Optional[int] = None
    composite_index: Optional[float] = None
    # mileage_decline
    age: Optional[float] = None
    career_minutes: Optional[float] = None
    pace_dependent: Optional[bool] = None
    # sell_high (ML + rule gate)
    deterioration_probability: Optional[float] = None
    current_real_value: Optional[float] = None
    peak_real_value: Optional[float] = None
    at_peak: Optional[bool] = None
    meets_minutes_floor: Optional[bool] = None
    # financial
    value_efficiency: Optional[float] = None
    wage_estimated: Optional[bool] = None


class PlayerRiskAssessment(BaseModel):
    """backend.scoring.risk.assess_player_risk's result for one player -
    all four reasons, whichever did or didn't trigger. squad-profile's
    high_risk_players shows only triggered ones; GET /players/{id} shows all four."""

    player: str
    id: Optional[str] = None
    season: str
    position: str
    any_triggered: bool
    triggered_reasons: List[str] = []
    reasons: List[RiskReason] = []


class PlayerProfileResponse(BaseModel):
    """Returned by GET /players/{id}: basic stats, the radar (measurable
    style categories only), the composite index breakdown, and risk factors (diagnostic only)."""

    id: str
    profile: PlayerProfileBasic
    radar: List[CategoryScore]
    composite_index: Optional[float] = None
    composite_description: Optional[str] = None
    zscore_comp: Optional[float] = None
    style_pctile_avg: Optional[float] = None
    power_norm: Optional[float] = None
    category_scores: Dict[str, Optional[float]]
    risk: Optional[PlayerRiskAssessment] = None


# ==============================================================================
# SIMILAR PLAYERS
# ==============================================================================


class SimilarPlayerMatch(BaseModel):
    """One candidate from GET /players/{id}/similar - Mahalanobis distance
    over the position's raw per-90 metric set. match_score (0-100) is
    normalized against the full eligible candidate pool, stable across page/filter/sort."""

    id: str
    player: str
    team: str
    league: str
    age: Optional[float] = None
    position: str
    primary_position: Optional[str] = None
    match_score: float
    rank: int
    pool_size: int
    goals: Optional[float] = None
    assists: Optional[float] = None
    minutes: Optional[float] = None
    seasons: Optional[int] = None
    composite: Optional[float] = None
    stats: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    is_gem: Optional[bool] = None
    contract_months: Optional[int] = None
    wage: Optional[float] = None
    wage_label: Optional[str] = None
    market_value: Optional[float] = None
    market_value_label: Optional[str] = None
    release_clause: Optional[float] = None
    release_clause_label: Optional[str] = None
    opportunity: Optional[str] = None
    # ml.style_clustering nearest-archetype label - only populated when the
    # `archetype` filter was actually requested.
    archetype_label: Optional[str] = None


class SimilarPlayersResponse(BaseModel):
    similar: List[SimilarPlayerMatch]
    total: int = 0
    page: int = 1
    page_size: int = 20
    method: str
    metrics_used: int
    metric_keys: List[str] = []
    metric_groups: List[Dict[str, Any]] = []
    window: int
    min_minutes: float
    sort: str = 'match_score'
    # `target` carries archetype_label/archetype_cluster (None for GK).
    # archetype_options is every archetype trained for the target's
    # position group - pass a label to filter "only players of this archetype".
    archetype_options: List[ArchetypeOption] = []
    target: Dict[str, Any]
    error: Optional[str] = None


class SimilarityMethodInfo(BaseModel):
    """One entry of backend/scoring/similarity.py's SIMILARITY_METHODS -
    the frontend's method-selector reasoning/tooltip copy, sourced from the
    backend so it can't drift from the engine's own justification."""

    key: str
    label: str
    description: str
    best_for: str


class SimilarityMethodsResponse(BaseModel):
    """GET /similarity-methods - static (season/player-independent), so the
    frontend can fetch it once rather than parsing it back out of every
    GET /players/{id}/similar response."""

    methods: List[SimilarityMethodInfo]
    default: str


# ==============================================================================
# HIDDEN GEMS
# ==============================================================================


class GemMethods(BaseModel):
    """Which of the 7 hidden-gem detection methods fired for this player -
    see backend/scoring/gems.py:detect()."""

    percentile_outlier: bool
    z_score_outlier: bool
    value_ratio: bool
    age_weighted: bool
    composite_score: bool
    statistical_anomaly: bool
    riser: bool


class GemResult(BaseModel):
    id: str
    player: str
    team: str
    league: str
    age: Optional[float] = None
    position: str
    composite: Optional[float] = None
    market_value: Optional[float] = None
    market_value_label: Optional[str] = None
    mv_estimated: Optional[bool] = None
    wage: Optional[float] = None
    wage_label: Optional[str] = None
    wage_estimated: Optional[bool] = None
    moneyball_score: Optional[float] = None
    z_score: Optional[float] = None
    value_ratio: Optional[float] = None
    age_potential: Optional[float] = None
    methods_triggered: int
    methods: GemMethods
    goals: Optional[float] = None
    assists: Optional[float] = None
    minutes: Optional[float] = None
    games: Optional[int] = None
    games_starts: Optional[int] = None
    display_stats: List[Dict[str, Any]] = []
    composite_components: Dict[str, Any] = {}
    top_categories: List[Dict[str, Any]] = []
    bottom_categories: List[Dict[str, Any]] = []
    anomaly_categories: List[Dict[str, Any]] = []
    position_pool_size: Optional[int] = None
    position_mean_composite: Optional[float] = None
    position_std_composite: Optional[float] = None
    wage_percentile: Optional[float] = None
    output_per_mv: Optional[float] = None
    value_residual: Optional[float] = None
    predicted_value: Optional[float] = None
    predicted_value_label: Optional[str] = None
    verdict: Dict[str, Any] = {}


class GemsResponse(BaseModel):
    gems: List[GemResult] = []
    total: int
    min_minutes: Optional[float] = None
    season: Optional[str] = None
    mv_method: Optional[str] = None
    error: Optional[str] = None


# ==============================================================================
# MARKET VALUE
# ==============================================================================


class MarketValueTrajectoryPoint(BaseModel):
    season: str
    age: Optional[float] = None
    actual_mv: Optional[float] = None
    estimated_mv: Optional[float] = None
    display_mv: Optional[float] = None
    is_estimated: bool


class FeatureContribution(BaseModel):
    feature: str
    importance: float
    weight_pct: float


class MarketValueResponse(BaseModel):
    """Returned by GET /players/{id}/market-value - a single valuation:
    verified real value wins when present, else the trained GBM
    (ml.market_value.predict), else the heuristic fallback. valuation_diff_eur/_pct is set only when method == 'verified'."""

    player: str
    season: str

    # Headline valuation: verified real value > GBM prediction > heuristic.
    current_value: Optional[float] = None
    current_value_label: Optional[str] = None
    is_estimated: Optional[bool] = None
    method: Optional[str] = None
    method_label: Optional[str] = None

    # The GBM's own prediction, specifically - and what drives it.
    ml_prediction: Optional[float] = None
    ml_prediction_label: Optional[str] = None
    ml_model_trained: bool = False
    ml_prediction_confidence: Optional[str] = None
    ml_prediction_confidence_note: Optional[str] = None

    # Model-implied valuation vs. observed market value - see this class's
    # docstring. Only populated when method == 'verified'.
    valuation_diff_eur: Optional[float] = None
    valuation_diff_label: Optional[str] = None
    valuation_diff_pct: Optional[float] = None

    top_contributors: List[FeatureContribution] = []

    # Real/estimated historical market values by season, nothing projected -
    # see this class's docstring for why a future/trend point is never
    # appended here.
    trajectory: List[MarketValueTrajectoryPoint] = []

    error: Optional[str] = None


class StyleArchetypeCategory(BaseModel):
    category: str
    percentile: float


class StyleArchetypeResponse(BaseModel):
    """Returned by GET /players/{id}/style-archetype: nearest style-cluster
    assignment (ml.style_clustering), trained per broad position group and
    unsupervised. eligible=False covers GK (out of scope) or no trained artifact."""

    player: str
    season: str
    position: str

    cluster: Optional[int] = None
    label: Optional[str] = None
    blurb: Optional[str] = None
    top_categories: List[StyleArchetypeCategory] = []
    distance_to_centroid: Optional[float] = None

    eligible: bool = True
    reason: Optional[str] = None
    model_trained: bool = False

    error: Optional[str] = None

    error: Optional[str] = None


# ==============================================================================
# POSITION BENCHMARK  ("vs. the league's best")
# ==============================================================================


class MetricLeaderEntry(BaseModel):
    """One row of GET /players/{id}/benchmark's metric_leaders - a headline
    metric, who holds the league-best value, and (if a reference player was
    given) that player's own value on the same metric."""

    metric: str
    best_value: float
    best_player: str
    best_player_id: Optional[str] = None
    player_value: Optional[float] = None


class CategoryLeaderEntry(BaseModel):
    """One style category's league-best envelope: the highest category
    score in the pool and who holds it."""

    category: str
    score: float
    player: str
    team: str
    player_id: Optional[str] = None


class BenchmarkBest(BaseModel):
    """The league's standout performer (by z-score aggregate, not composite)
    and their own radar - the profile's radar overlay."""

    player: str
    team: str
    player_id: Optional[str] = None
    zscore_comp: Optional[float] = None
    radar: List[CategoryScore] = []


class PositionBenchmarkResponse(BaseModel):
    """Returned by GET /players/{id}/benchmark: backend/scoring/benchmark.py,
    relocated unchanged from the original engine's cmd_get_position_benchmark."""

    position: str
    league: str
    season: str
    sample_size: int
    league_average: float
    best: Optional[BenchmarkBest] = None
    category_leaders: List[CategoryLeaderEntry] = []
    metric_leaders: List[MetricLeaderEntry] = []
    error: Optional[str] = None


# ==============================================================================
# PLAYING STYLE BREAKDOWN
# ==============================================================================


class StyleMetricDetail(BaseModel):
    metric: str
    value: float
    percentile: float


class StyleCategoryBreakdown(BaseModel):
    name: str
    percentile_score: Optional[float] = None
    normalized_score: Optional[float] = None
    metrics: List[StyleMetricDetail] = []
    no_data: bool = False


class StyleDriverMetric(BaseModel):
    """One metric driving a strength/weakness highlight - metric is the raw
    column key, label a lightweight humanized caption (see
    backend/scoring/style_breakdown.py._humanize_metric)."""

    metric: str
    label: str
    value: float
    percentile: float


class StyleHighlight(BaseModel):
    """One strength or weakness: the category, its percentile, the 1-2
    metrics driving it, and a generated one-line description."""

    category: str
    percentile: float
    drivers: List[StyleDriverMetric] = []
    text: str


class PlayingStyleResponse(BaseModel):
    """Returned by GET /players/{id}/style: backend/scoring/style_breakdown.py,
    relocated unchanged from the original engine's cmd_get_playing_style, plus
    a new strengths/weaknesses summary layered on top of that same data."""

    position: str
    categories: List[StyleCategoryBreakdown] = []
    strengths: List[StyleHighlight] = []
    weaknesses: List[StyleHighlight] = []
    error: Optional[str] = None


# ==============================================================================
# CAREER HISTORY
# ==============================================================================


class CareerSeason(BaseModel):
    """One season+team row of GET /players/{id}/history - composite_index is
    recomputed against THAT season's own league/position pool, not carried
    over from the current profile's."""

    season: str
    team: str
    id: str
    league: str
    position: str
    age: Optional[float] = None
    games: Optional[float] = None
    minutes: Optional[float] = None
    goals: Optional[float] = None
    assists: Optional[float] = None
    xg: Optional[float] = None
    xg_assist: Optional[float] = None
    composite: Optional[float] = None


class CareerHistoryResponse(BaseModel):
    """Returned by GET /players/{id}/history: backend/scoring/career.py,
    relocated unchanged from the original engine's cmd_get_career_history."""

    player: str
    history: List[CareerSeason] = []
    error: Optional[str] = None


# ==============================================================================
# ADMIN
# ==============================================================================


class ModelStatus(BaseModel):
    """One of the three currently-trained models' status, for the admin
    panel's Model Management section. `meta` is each model's raw meta.json
    sidecar (untyped Dict); `config` is populated only when relevant."""

    key: str
    label: str
    trained: bool
    meta: Dict[str, Any] = {}
    config: Optional[Dict[str, Any]] = None


class ModelManagementResponse(BaseModel):
    models: List[ModelStatus]


class ModelRetrainRequest(BaseModel):
    """Shared across all three /admin/models/{key}/retrain endpoints - each
    model's retrain script only reads the fields it accepts (seasons for
    market-value/sell-high; seasons/min_minutes/k_min/k_max for style-clustering)."""

    seasons: Optional[List[str]] = None
    min_minutes: Optional[float] = None
    k_min: Optional[int] = None
    k_max: Optional[int] = None


class ModelRetrainResponse(BaseModel):
    key: str
    meta: Dict[str, Any] = {}
    error: Optional[str] = None


class BacktestResponse(BaseModel):
    seasons_tested: List[str] = []
    positions_tested: List[str] = []
    horizon: Optional[int] = None
    league: Optional[str] = None
    n_runs: int = 0
    n_skipped: int = 0
    skipped: List[Dict[str, Any]] = []
    runs: List[Dict[str, Any]] = []
    pooled: Dict[str, Any] = {}
    available_seasons: Optional[List[str]] = None
    error: Optional[str] = None


class SensitivityScenario(BaseModel):
    scenario: str
    weights: Dict[str, float]
    spearman: Optional[float] = None
    top_n_overlap_pct: Optional[float] = None
    mean_abs_rank_change: Optional[float] = None


class SensitivityResponse(BaseModel):
    season: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    pool_size: Optional[int] = None
    min_minutes: Optional[float] = None
    perturbation_pct: Optional[float] = None
    top_n: Optional[int] = None
    composite_sensitivity: List[SensitivityScenario] = []
    moneyball_sensitivity: List[SensitivityScenario] = []
    error: Optional[str] = None


class ConfigEntry(BaseModel):
    """One tunable constant from backend/config.py, parsed by
    backend/config_inspector.py - `value` is its live resolved value,
    `explanation` is the file's own comment, `section` is its raw header name."""

    name: str
    value: Any
    section: Optional[str] = None
    explanation: Optional[str] = None
    line: int


class ConfigGroup(BaseModel):
    """One feature-area section of the admin panel's Configuration view -
    not always 1:1 with a config.py section header (some merge or split,
    see config_inspector.py). `entries` may be empty; shown explicitly rather than omitted."""

    group: str
    entries: List[ConfigEntry]


class ConfigGroupsResponse(BaseModel):
    groups: List[ConfigGroup]


# ==============================================================================
# META  (dataset coverage - not tied to any one scoring feature)
# ==============================================================================


class LeagueInfo(BaseModel):
    key: str
    label: str


class MetaResponse(BaseModel):
    """Returned by GET /meta: seasons + leagues present in the loaded
    dataset, plus a last-updated freshness signal. Used by the homepage's
    data description and the hero search bar's default season."""

    seasons: List[str]
    leagues: List[LeagueInfo]


# ==============================================================================
# SQUAD PROFILE  (backend/scoring/squad_profile.py, GET /teams/{team}/squad-profile)
# ==============================================================================


class PositionDepthEntry(BaseModel):
    """One position's roster count + composite-index distribution.
    is_thin is True when count is below config.SQUAD_PROFILE_MIN_DEPTH."""

    position: str
    count: int
    avg_composite: Optional[float] = None
    best_composite: Optional[float] = None
    best_player: Optional[str] = None
    best_player_id: Optional[str] = None
    is_thin: bool


class AgeCurvePlayer(BaseModel):
    player: str
    id: str
    age: Optional[float] = None


class AgeCurveEntry(BaseModel):
    """One position's age distribution. is_top_heavy is True when a strict
    majority of the position's rostered players are at/above
    config.SQUAD_PROFILE_AGING_THRESHOLD."""

    position: str
    count: int
    avg_age: Optional[float] = None
    aging_count: int
    is_top_heavy: bool
    players: List[AgeCurvePlayer] = []


class ContractCliffEntry(BaseModel):
    """One rostered player whose contract expires within
    config.SQUAD_PROFILE_CONTRACT_CLIFF_LONG_MONTHS - ranked composite
    index first, then minutes."""

    player: str
    id: str
    position: str
    age: Optional[float] = None
    minutes: Optional[float] = None
    composite_index: Optional[float] = None
    contract_expiry: Optional[str] = None
    contract_months_remaining: int
    within_short_window: bool
    within_long_window: bool


class ArchetypeCount(BaseModel):
    """One ml.style_clustering archetype and how many of this squad's
    rostered players at that position were assigned to it - 0 included,
    so an empty archetype is still listed."""

    cluster: int
    label: str
    count: int


class StyleDiversityEntry(BaseModel):
    """One position's archetype breakdown - concrete counts per
    ml.style_clustering archetype. is_style_similar is True when every
    assignable player landed in the same archetype; None if no catalogue or <2 assignable."""

    position: str
    count: int
    archetypes: List[ArchetypeCount] = []
    is_style_similar: Optional[bool] = None


class WageOutputPoint(BaseModel):
    """One rostered player's composite index against their wage and
    value-efficiency (backend/scoring/moneyball.py's formula) - plots across
    the whole squad show under/over-paid players relative to output."""

    player: str
    id: str
    position: str
    composite_index: Optional[float] = None
    weekly_wage_eur: Optional[float] = None
    annual_wage_eur: Optional[float] = None
    wage_is_estimated: Optional[bool] = None
    value_efficiency: Optional[float] = None


class SquadProfileResponse(BaseModel):
    """Returned by GET /teams/{team}/squad-profile: a read-only diagnostic
    snapshot (position depth, age curve, contract cliff, style diversity,
    wage-vs-output, high-risk players) - never recommends a replacement or ranks candidates."""

    team: str
    season: str
    league: str
    roster_size: int
    position_depth: List[PositionDepthEntry] = []
    age_curve: List[AgeCurveEntry] = []
    contract_cliff: List[ContractCliffEntry] = []
    style_diversity: List[StyleDiversityEntry] = []
    wage_output: List[WageOutputPoint] = []
    high_risk_players: List[PlayerRiskAssessment] = []
    aging_threshold: int
    min_depth: int
    error: Optional[str] = None
    last_updated: Optional[str] = None


class ImpactMetricDetail(BaseModel):
    """One of the 7 on/off-pitch differential metrics feeding the Impact
    Score, with its raw value and where it lands in the position+league pool."""

    metric: str
    label: str
    value: float
    percentile: float


class ImpactScoreResponse(BaseModel):
    """Returned by GET /players/{id}/impact: average percentile across 7
    on/off-pitch differential metrics, against a minutes-gated
    position+league pool. Structurally different from Composite Index; qualifies=False if under the minutes gate."""

    player: str
    team: str
    league: str
    season: str
    position: str
    qualifies: bool
    min_minutes: int
    minutes: float
    impact_score: Optional[float] = None
    label: Optional[str] = None
    components: List[ImpactMetricDetail] = []


# ==============================================================================
# RAW DATA TAB
# ==============================================================================


class RawMetricEntry(BaseModel):
    key: str
    label: str
    value: str


class RawDataCategory(BaseModel):
    """One style category (backend/scoring/composite.py's
    get_playing_style_categories) and this player's own raw, un-scored value
    for each of that category's metrics."""

    category: str
    metrics: List[RawMetricEntry]


class RawDataResponse(BaseModel):
    """Returned by GET /players/{id}/raw-data: the player's full raw per-90/
    per-season metric set, grouped by their own position's style categories -
    a plain breakdown, not a new categorization scheme."""

    position: str
    season: str
    categories: List[RawDataCategory] = []
    error: Optional[str] = None
