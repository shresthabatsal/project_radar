// Mirrors data/schemas.py's Pydantic response models one-for-one, so
// lib/api.ts's return types match what the API sends. Dict[str, Any]
// fields stay as Record<string, unknown> here too.

export type Json = Record<string, unknown>;

export interface MoneyballScore {
  player: string;
  position: string;
  season: string;
  moneyball_score: number;
  performance_score: number;
  perf_zaggregate: number | null;
  perf_style: number | null;
  perf_power: number | null;
  value_efficiency: number;
  value_ratio_raw: number | null;
  value_capped: boolean | null;
  wage_percentile: number | null;
  contract_opportunity: number;
  contract_months: number | null;
  contract_urgency: number | null;
  contract_clause: number | null;
  wage: number;
  wage_label: string;
  wage_estimated: boolean;
  market_value: number;
  market_value_label: string;
  mv_estimated: boolean;
}

export interface ImpactMetricDetail {
  metric: string;
  label: string;
  value: number;
  percentile: number;
}

export interface ImpactScoreResponse {
  player: string;
  team: string;
  league: string;
  season: string;
  position: string;
  qualifies: boolean;
  min_minutes: number;
  minutes: number;
  impact_score: number | null;
  label: string | null;
  components: ImpactMetricDetail[];
}

// ---- Player listing / profile ----------------------------------------

export interface PlayerSummary {
  id: string;
  player: string;
  team: string;
  league: string;
  season: string;
  position: string;
  secondary_position: string | null;
  age: number | null;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  is_gem: boolean | null;
}

export interface PlayersListResponse {
  players: PlayerSummary[];
  total: number;
}

export interface PlayerSearchResult {
  id: string;
  player: string;
  team: string;
  league: string;
  season: string;
  position: string;
  secondary_position: string | null;
  nationality: string | null;
  age: number | null;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  composite_index: number | null;
  market_value: number | null;
  market_value_label: string | null;
  wage: number | null;
  wage_label: string | null;
  contract_expiry: string | null;
  contract_months_remaining: number | null;
  release_clause: number | null;
  release_clause_label: string | null;
  // ml.style_clustering nearest-archetype label - only populated when the
  // `archetype` filter was actually requested.
  archetype_label: string | null;
  is_gem: boolean | null;
}

export interface PlayerSearchResponse {
  players: PlayerSearchResult[];
  total: number;
  limit: number;
  offset: number;
}

// One selectable ml.style_clustering archetype - `label` is a real
// generated cluster label, never hardcoded, scoped to a broad position group (FW/MF/DF - GK has none).
export interface ArchetypeOption {
  position: string;
  cluster: number;
  label: string;
}

export interface PlayerFiltersResponse {
  teams: string[];
  nationalities: string[];
  leagues: string[];
  positions: string[];
  archetypes: ArchetypeOption[];
}

export interface CategoryScore {
  category: string;
  score: number | null;
}

export interface PlayerProfileBasic {
  player: string;
  team: string;
  league: string;
  season: string;
  position: string;
  age: number | null;
  minutes: number | null;
  games: number | null;
  goals: number | null;
  assists: number | null;
  xg: number | null;
  xg_assist: number | null;
  weekly_wage_eur: number | null;
  annual_wage_eur: number | null;
  weekly_wage_label: string | null;
  annual_wage_label: string | null;
  contract_expiry: string | null;
  contract_signed: string | null;
  contract_months_remaining: number | null;
  release_clause_eur: number | null;
  release_clause_label: string | null;
}

// backend/scoring/risk.py: four independent risk reasons (contract/
// mileage_decline/sell_high/financial). Only fields relevant to `reason`
// are non-null. Diagnostic only.
export interface RiskReason {
  reason: "contract" | "mileage_decline" | "sell_high" | "financial";
  label: string;
  triggered: boolean;
  detail: string | null;

  // contract
  months_remaining: number | null;
  composite_index: number | null;
  // mileage_decline
  age: number | null;
  career_minutes: number | null;
  pace_dependent: boolean | null;
  // sell_high (ML + rule gate)
  deterioration_probability: number | null;
  current_real_value: number | null;
  peak_real_value: number | null;
  at_peak: boolean | null;
  meets_minutes_floor: boolean | null;
  // financial
  value_efficiency: number | null;
  wage_estimated: boolean | null;
}

export interface PlayerRiskAssessment {
  player: string;
  id: string | null;
  season: string;
  position: string;
  any_triggered: boolean;
  triggered_reasons: string[];
  reasons: RiskReason[];
}

export interface PlayerProfileResponse {
  id: string;
  profile: PlayerProfileBasic;
  radar: CategoryScore[];
  composite_index: number | null;
  composite_description: string | null;
  zscore_comp: number | null;
  style_pctile_avg: number | null;
  power_norm: number | null;
  category_scores: Record<string, number | null>;
  risk: PlayerRiskAssessment | null;
}

// ---- Position benchmark ("vs. the league's best") ----------------------

export interface MetricLeaderEntry {
  metric: string;
  best_value: number;
  best_player: string;
  best_player_id: string | null;
  player_value: number | null;
}

export interface CategoryLeaderEntry {
  category: string;
  score: number;
  player: string;
  team: string;
  player_id: string | null;
}

export interface BenchmarkBest {
  player: string;
  team: string;
  player_id: string | null;
  zscore_comp: number | null;
  radar: CategoryScore[];
}

export interface PositionBenchmarkResponse {
  position: string;
  league: string;
  season: string;
  sample_size: number;
  league_average: number;
  best: BenchmarkBest | null;
  category_leaders: CategoryLeaderEntry[];
  metric_leaders: MetricLeaderEntry[];
  error: string | null;
}

// ---- Playing style breakdown --------------------------------------------

export interface StyleMetricDetail {
  metric: string;
  value: number;
  percentile: number;
}

export interface StyleCategoryBreakdown {
  name: string;
  percentile_score: number | null;
  normalized_score: number | null;
  metrics: StyleMetricDetail[];
  no_data: boolean;
}

export interface StyleDriverMetric {
  metric: string;
  label: string;
  value: number;
  percentile: number;
}

export interface StyleHighlight {
  category: string;
  percentile: number;
  drivers: StyleDriverMetric[];
  text: string;
}

export interface PlayingStyleResponse {
  position: string;
  categories: StyleCategoryBreakdown[];
  strengths: StyleHighlight[];
  weaknesses: StyleHighlight[];
  error: string | null;
}

// ml.style_clustering - nearest style archetype for this player-season.
// eligible=false covers a goalkeeper (never clustered) or a position group with no trained artifact yet.
export interface StyleArchetypeCategory {
  category: string;
  percentile: number;
}

export interface StyleArchetypeResponse {
  player: string;
  season: string;
  position: string;
  cluster: number | null;
  label: string | null;
  blurb: string | null;
  top_categories: StyleArchetypeCategory[];
  distance_to_centroid: number | null;
  eligible: boolean;
  reason: string | null;
  model_trained: boolean;
  error: string | null;
}

// ---- Career history ------------------------------------------------------

export interface CareerSeason {
  season: string;
  team: string;
  id: string;
  league: string;
  position: string;
  age: number | null;
  games: number | null;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  xg: number | null;
  xg_assist: number | null;
  composite: number | null;
}

export interface CareerHistoryResponse {
  player: string;
  history: CareerSeason[];
  error: string | null;
}

// ---- Similar players ---------------------------------------------------

// One raw metric's value for both players in a similarity match -
// value/target are pre-formatted display strings. diff is target minus
// value, a plain factual delta shown as the "Difference" column.
export interface SimilarMetricComparison {
  value: string;
  target: string;
  diff: string | null;
  better: "player" | "target" | "tie" | null;
}

export interface SimilarMetricGroupItem {
  key: string;
  label: string;
}

export interface SimilarMetricGroup {
  category: string;
  metrics: SimilarMetricGroupItem[];
}

export interface SimilarPlayerMatch {
  id: string;
  player: string;
  team: string;
  league: string;
  age: number | null;
  position: string;
  primary_position: string | null;
  match_score: number;
  rank: number;
  pool_size: number;
  goals: number | null;
  assists: number | null;
  minutes: number | null;
  seasons: number | null;
  composite: number | null;
  stats: Json[];
  metrics: Record<string, SimilarMetricComparison>;
  is_gem: boolean | null;
  contract_months: number | null;
  wage: number | null;
  wage_label: string | null;
  market_value: number | null;
  market_value_label: string | null;
  release_clause: number | null;
  release_clause_label: string | null;
  opportunity: string | null;
  // ml.style_clustering nearest-archetype label - only populated when the
  // `archetype` filter was actually requested.
  archetype_label: string | null;
}

export interface SimilarPlayersTarget {
  player: string;
  team: string;
  position: string;
  age: number | null;
  minutes: number | null;
  seasons: number | null;
  // The target's own ml.style_clustering assignment - null for a GK target
  // (never clustered) or a position group with no trained artifact.
  archetype_label: string | null;
  archetype_cluster: number | null;
}

export interface SimilarPlayersResponse {
  similar: SimilarPlayerMatch[];
  total: number;
  page: number;
  page_size: number;
  method: string;
  metrics_used: number;
  metric_keys: string[];
  metric_groups: SimilarMetricGroup[];
  window: number;
  min_minutes: number;
  sort: string;
  // Every archetype trained for the target's own position group - the
  // `archetype` filter accepts any of these labels. Empty for a GK target or an untrained position group.
  archetype_options: ArchetypeOption[];
  target: SimilarPlayersTarget;
  error: string | null;
}

// backend/scoring/similarity.py's SIMILARITY_METHODS, served statically by
// GET /similarity-methods - the reasoning/"best for" copy behind each of
// the 4 distance methods GET /players/{id}/similar accepts.
export interface SimilarityMethodInfo {
  key: string;
  label: string;
  description: string;
  best_for: string;
}

export interface SimilarityMethodsResponse {
  methods: SimilarityMethodInfo[];
  default: string;
}

// ---- Market value ----------------------------------------------------

export interface MarketValueTrajectoryPoint {
  season: string;
  age: number | null;
  actual_mv: number | null;
  estimated_mv: number | null;
  display_mv: number | null;
  is_estimated: boolean;
}

export interface FeatureContribution {
  feature: string;
  importance: number;
  weight_pct: number;
}

// A single valuation model, not two competing estimates - see
// data/schemas.py's MarketValueResponse docstring for the full contract.
export interface MarketValueResponse {
  player: string;
  season: string;

  // Headline valuation: verified real value > GBM prediction > heuristic.
  current_value: number | null;
  current_value_label: string | null;
  is_estimated: boolean | null;
  method: "verified" | "gbm" | "heuristic_fallback" | "heuristic" | null;
  method_label: string | null;

  // The GBM's own prediction, specifically - and what drives it.
  ml_prediction: number | null;
  ml_prediction_label: string | null;
  ml_model_trained: boolean;
  ml_prediction_confidence: "high" | "medium" | "low" | null;
  ml_prediction_confidence_note: string | null;

  // Model-implied valuation vs. observed market value - only populated
  // when method === "verified" (comparing the model to itself otherwise
  // would be meaningless, since it IS the headline in that case).
  valuation_diff_eur: number | null;
  valuation_diff_label: string | null;
  valuation_diff_pct: number | null;

  top_contributors: FeatureContribution[];

  // Real/estimated historical market values by season - nothing projected.
  trajectory: MarketValueTrajectoryPoint[];

  error: string | null;
}

// ---- Raw data tab --------------------------------------------------------

export interface RawMetricEntry {
  key: string;
  label: string;
  value: string;
}

export interface RawDataCategory {
  category: string;
  metrics: RawMetricEntry[];
}

export interface RawDataResponse {
  position: string;
  season: string;
  categories: RawDataCategory[];
  error: string | null;
}

// ---- Admin -------------------------------------------------------------

// One of the three trained models' last-run status. `meta` is that
// model's own meta.json sidecar, read back verbatim (untyped). `config`
// carries whatever config-in-effect the admin panel shows alongside metrics.
export interface ModelStatus {
  key: string;
  label: string;
  trained: boolean;
  meta: Json;
  config: Json | null;
}

export interface ModelManagementResponse {
  models: ModelStatus[];
}

export interface ModelRetrainRequest {
  seasons?: string[] | null;
  min_minutes?: number | null;
  k_min?: number | null;
  k_max?: number | null;
}

export interface ModelRetrainResponse {
  key: string;
  meta: Json;
  error: string | null;
}

export interface BacktestResponse {
  seasons_tested: string[];
  positions_tested: string[];
  horizon: number | null;
  league: string | null;
  n_runs: number;
  n_skipped: number;
  skipped: Json[];
  runs: Json[];
  pooled: Json;
  available_seasons: string[] | null;
  error: string | null;
}

export interface SensitivityScenario {
  scenario: string;
  weights: Record<string, number>;
  spearman: number | null;
  top_n_overlap_pct: number | null;
  mean_abs_rank_change: number | null;
}

export interface SensitivityResponse {
  season: string | null;
  league: string | null;
  position: string | null;
  pool_size: number | null;
  min_minutes: number | null;
  perturbation_pct: number | null;
  top_n: number | null;
  composite_sensitivity: SensitivityScenario[];
  moneyball_sensitivity: SensitivityScenario[];
  error: string | null;
}

// One tunable constant from backend/config.py, parsed by
// backend/config_inspector.py - `value` is its live resolved value,
// `explanation` is the file's comment, `section` is its raw header name.
export interface ConfigEntry {
  name: string;
  value: unknown; // any JSON-safe value: number | string | boolean | null | object | array
  section: string | null;
  explanation: string | null;
  line: number;
}

export interface ConfigGroup {
  group: string;
  entries: ConfigEntry[];
}

export interface ConfigGroupsResponse {
  groups: ConfigGroup[];
}

// ---- Meta (dataset coverage) --------------------------------------------

export interface LeagueInfo {
  key: string;
  label: string;
}

export interface MetaResponse {
  seasons: string[];
  leagues: LeagueInfo[];
  last_updated: string | null;
}

// ---- Squad profile (backend/scoring/squad_profile.py) -------------------

export interface PositionDepthEntry {
  position: string;
  count: number;
  avg_composite: number | null;
  best_composite: number | null;
  best_player: string | null;
  best_player_id: string | null;
  is_thin: boolean;
}

export interface AgeCurvePlayer {
  player: string;
  id: string;
  age: number | null;
}

export interface AgeCurveEntry {
  position: string;
  count: number;
  avg_age: number | null;
  aging_count: number;
  is_top_heavy: boolean;
  players: AgeCurvePlayer[];
}

export interface ContractCliffEntry {
  player: string;
  id: string;
  position: string;
  age: number | null;
  minutes: number | null;
  composite_index: number | null;
  contract_expiry: string | null;
  contract_months_remaining: number;
  within_short_window: boolean;
  within_long_window: boolean;
}

export interface ArchetypeCount {
  cluster: number;
  label: string;
  count: number;
}

export interface StyleDiversityEntry {
  position: string;
  count: number;
  archetypes: ArchetypeCount[];
  is_style_similar: boolean | null;
}

export interface WageOutputPoint {
  player: string;
  id: string;
  position: string;
  composite_index: number | null;
  weekly_wage_eur: number | null;
  annual_wage_eur: number | null;
  wage_is_estimated: boolean | null;
  value_efficiency: number | null;
}

export interface SquadProfileResponse {
  team: string;
  season: string;
  league: string;
  roster_size: number;
  position_depth: PositionDepthEntry[];
  age_curve: AgeCurveEntry[];
  contract_cliff: ContractCliffEntry[];
  style_diversity: StyleDiversityEntry[];
  wage_output: WageOutputPoint[];
  high_risk_players: PlayerRiskAssessment[];
  aging_threshold: number;
  min_depth: number;
  error: string | null;
}

// ---- Status / upload (main.py, not a routers/ module) --------------------

export interface StatusResponse {
  player_rows: number;
  supplementary_rows: number;
  last_updated: string | null;
}

export interface UploadResponse {
  ok: boolean;
  player_rows?: number;
  supplementary_rows?: number;
  error?: string;
}
