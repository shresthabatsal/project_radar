// Typed client for the FastAPI routers (backend/routers/*.py) - one
// function per endpoint, matching each route's params and Pydantic
// response_model (mirrored in lib/types.ts).

import type {
  BacktestResponse,
  CareerHistoryResponse,
  ConfigGroupsResponse,
  ImpactScoreResponse,
  MarketValueResponse,
  MetaResponse,
  ModelManagementResponse,
  ModelRetrainRequest,
  ModelRetrainResponse,
  MoneyballScore,
  PlayerFiltersResponse,
  PlayerProfileResponse,
  PlayerSearchResponse,
  PlayersListResponse,
  PlayingStyleResponse,
  PositionBenchmarkResponse,
  RawDataResponse,
  SensitivityResponse,
  SimilarPlayersResponse,
  SimilarityMethodsResponse,
  SquadProfileResponse,
  StatusResponse,
  StyleArchetypeResponse,
  UploadResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: { params?: Record<string, unknown> | object; init?: RequestInit } = {},
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) url.searchParams.append(key, String(v));
    } else {
      url.searchParams.set(key, String(value));
    }
  }

  const res = await fetch(url, options.init);
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

// ---- players.py --------------------------------------------------------

export interface ListPlayersParams {
  season: string;
  league?: string;
  team?: string;
  position?: string;
  name?: string;
  min_minutes?: number;
  limit?: number;
  offset?: number;
}

export function listPlayers(
  params: ListPlayersParams,
  init?: RequestInit,
): Promise<PlayersListResponse> {
  return request<PlayersListResponse>("/players", { params, init });
}

export function getPlayerProfile(id: string): Promise<PlayerProfileResponse> {
  return request<PlayerProfileResponse>(`/players/${encodeURIComponent(id)}`);
}

// ---- benchmark.py / style.py / history.py ---------------------------------

export function getPositionBenchmark(id: string): Promise<PositionBenchmarkResponse> {
  return request<PositionBenchmarkResponse>(`/players/${encodeURIComponent(id)}/benchmark`);
}

export function getPlayingStyle(id: string): Promise<PlayingStyleResponse> {
  return request<PlayingStyleResponse>(`/players/${encodeURIComponent(id)}/style`);
}

// ml.style_clustering - nearest style archetype for this player-season.
// eligible=false for a goalkeeper (never clustered) or a position group with no trained artifact yet.
export function getStyleArchetype(id: string): Promise<StyleArchetypeResponse> {
  return request<StyleArchetypeResponse>(`/players/${encodeURIComponent(id)}/style-archetype`);
}

export function getRawData(id: string): Promise<RawDataResponse> {
  return request<RawDataResponse>(`/players/${encodeURIComponent(id)}/raw-data`);
}

export function getCareerHistory(id: string): Promise<CareerHistoryResponse> {
  return request<CareerHistoryResponse>(`/players/${encodeURIComponent(id)}/history`);
}

export type PlayerSearchSort = "composite_index" | "market_value" | "name";

export interface SearchPlayersParams {
  season: string;
  position?: string;
  league?: string;
  team?: string;
  age_min?: number;
  age_max?: number;
  nationality?: string;
  min_minutes?: number;
  market_value_min?: number;
  market_value_max?: number;
  wage_min?: number;
  wage_max?: number;
  contract_expiring_months?: number;
  has_release_clause?: boolean;
  min_goals_per90?: number;
  min_assists_per90?: number;
  min_xg_per90?: number;
  min_npxg_per90?: number;
  min_progressive_passes?: number;
  min_tackles?: number;
  min_sca_per90?: number;
  min_gca_per90?: number;
  // ml.style_clustering: an exact match against one of GET
  // /players/filters' archetypes[].label.
  archetype?: string;
  sort?: PlayerSearchSort;
  limit?: number;
  offset?: number;
}

export function searchPlayers(
  params: SearchPlayersParams,
  init?: RequestInit,
): Promise<PlayerSearchResponse> {
  return request<PlayerSearchResponse>("/players/search", { params, init });
}

export interface GetPlayerFiltersParams {
  season?: string;
  league?: string;
}

export function getPlayerFilters(
  params: GetPlayerFiltersParams = {},
  init?: RequestInit,
): Promise<PlayerFiltersResponse> {
  return request<PlayerFiltersResponse>("/players/filters", { params, init });
}

// ---- similarity.py -------------------------------------------------------

export type SimilarPlayersSort = "match_score" | "composite" | "age" | "market_value";
export type ContractStatus = "free" | "expiring" | "clause";
// Restored alongside mahalanobis (the default) - backend/scoring/
// similarity.py's SIMILARITY_METHODS/DEFAULT_SIMILARITY_METHOD.
export type SimilarityMethod = "mahalanobis" | "cosine" | "euclidean" | "manhattan";

export interface GetSimilarPlayersParams {
  min_minutes?: number;
  window?: number;
  league?: string;
  team?: string;
  age_min?: number;
  age_max?: number;
  minutes_min?: number;
  minutes_max?: number;
  contract_status?: ContractStatus;
  // ml.style_clustering: an exact match against one of this response's
  // own archetype_options[].label.
  archetype?: string;
  method?: SimilarityMethod;
  sort?: SimilarPlayersSort;
  page?: number;
  page_size?: number;
}

export function getSimilarPlayers(
  id: string,
  params: GetSimilarPlayersParams = {},
): Promise<SimilarPlayersResponse> {
  return request<SimilarPlayersResponse>(`/players/${encodeURIComponent(id)}/similar`, { params });
}

// Static (season/player-independent) - the method picker's reasoning copy,
// fetched once rather than re-parsed out of every similarity response.
export function getSimilarityMethods(): Promise<SimilarityMethodsResponse> {
  return request<SimilarityMethodsResponse>("/similarity-methods");
}

// ---- market_value.py -------------------------------------------------------

export function getMarketValue(id: string): Promise<MarketValueResponse> {
  return request<MarketValueResponse>(`/players/${encodeURIComponent(id)}/market-value`);
}

// ---- moneyball.py -------------------------------------------------------

export function getMoneyballScore(id: string): Promise<MoneyballScore> {
  return request<MoneyballScore>(`/players/${encodeURIComponent(id)}/moneyball`);
}

// ---- impact.py ------------------------------------------------------------

export function getImpactScore(id: string): Promise<ImpactScoreResponse> {
  return request<ImpactScoreResponse>(`/players/${encodeURIComponent(id)}/impact`);
}

// ---- admin.py (token-gated: X-Admin-Token header) -------------------------

function adminInit(token: string, init: RequestInit = {}): RequestInit {
  return {
    ...init,
    headers: { ...(init.headers ?? {}), "X-Admin-Token": token },
  };
}

// ---- admin.py: Model Management ------------------------------------------

export function adminModelStatus(token: string): Promise<ModelManagementResponse> {
  return request<ModelManagementResponse>("/admin/models", { init: adminInit(token) });
}

export type AdminModelKey = "market-value" | "sell-high-risk" | "style-clustering";

export function adminRetrainModel(
  token: string,
  key: AdminModelKey,
  body: ModelRetrainRequest = {},
): Promise<ModelRetrainResponse> {
  return request<ModelRetrainResponse>(`/admin/models/${key}/retrain`, {
    init: adminInit(token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  });
}

export interface AdminBacktestParams {
  season?: string[];
  position?: string[];
  horizon?: number;
  league?: string;
}

export function adminBacktest(
  token: string,
  params: AdminBacktestParams = {},
): Promise<BacktestResponse> {
  return request<BacktestResponse>("/admin/backtest", { params, init: adminInit(token) });
}

export interface AdminSensitivityParams {
  season: string;
  position: string;
  league?: string;
  pct?: number;
  top_n?: number;
  min_minutes?: number;
}

export function adminSensitivity(
  token: string,
  params: AdminSensitivityParams,
): Promise<SensitivityResponse> {
  return request<SensitivityResponse>("/admin/sensitivity", { params, init: adminInit(token) });
}

export function adminConfig(token: string): Promise<ConfigGroupsResponse> {
  return request<ConfigGroupsResponse>("/admin/config", { init: adminInit(token) });
}

// ---- squad.py --------------------------------------------------------------

export interface GetSquadProfileParams {
  season: string;
  league: string;
}

export function getSquadProfile(
  team: string,
  params: GetSquadProfileParams,
): Promise<SquadProfileResponse> {
  return request<SquadProfileResponse>(`/teams/${encodeURIComponent(team)}/squad-profile`, { params });
}

// ---- meta.py -------------------------------------------------------------

export function getMeta(): Promise<MetaResponse> {
  return request<MetaResponse>("/meta");
}

// ---- status / upload (main.py directly, not a routers/ module) -----------

export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/status");
}

export function uploadSnapshot(files: { players?: File; supplementary?: File }): Promise<UploadResponse> {
  const formData = new FormData();
  if (files.players) formData.append("players", files.players);
  if (files.supplementary) formData.append("supplementary", files.supplementary);
  // No Content-Type header here - the browser sets the multipart boundary
  // itself from the FormData body; setting it manually would break the parse.
  return request<UploadResponse>("/upload", { init: { method: "POST", body: formData } });
}
