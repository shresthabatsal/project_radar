import type { PlayerSearchSort, SearchPlayersParams } from "@/lib/api";

// Every input is kept as a string (controlled-input friendly) and only
// parsed/converted to the API's units when a search actually runs.
export interface FilterState {
  position: string;
  ageMin: string;
  ageMax: string;
  nationality: string;
  league: string;
  team: string;
  season: string;
  minMinutes: string;
  marketValueMinM: string; // millions of EUR
  marketValueMaxM: string;
  wageMinM: string; // millions of EUR/year
  wageMaxM: string;
  contractExpiringMonths: string;
  hasReleaseClause: "any" | "yes" | "no";
  minGoalsPer90: string;
  minAssistsPer90: string;
  minXgPer90: string;
  minNpxgPer90: string;
  minProgressivePasses: string;
  minTackles: string;
  minScaPer90: string;
  minGcaPer90: string;
  // ml.style_clustering archetype label - position-scoped, cleared
  // whenever position changes, same rule `team` follows when `league` changes.
  archetype: string;
  sort: PlayerSearchSort;
}

export function emptyFilterState(season: string): FilterState {
  return {
    position: "",
    ageMin: "",
    ageMax: "",
    nationality: "",
    league: "",
    team: "",
    season,
    minMinutes: "",
    marketValueMinM: "",
    marketValueMaxM: "",
    wageMinM: "",
    wageMaxM: "",
    contractExpiringMonths: "",
    hasReleaseClause: "any",
    minGoalsPer90: "",
    minAssistsPer90: "",
    minXgPer90: "",
    minNpxgPer90: "",
    minProgressivePasses: "",
    minTackles: "",
    minScaPer90: "",
    minGcaPer90: "",
    archetype: "",
    sort: "composite_index",
  };
}

// Reverse of emptyFilterState - builds initial filter state from URL
// query params for deep-linking into advanced search. Keys match
// FilterState's field names; unrecognized/absent keys fall back to defaults.
const STRING_KEYS = [
  "position", "ageMin", "ageMax", "nationality", "league", "team",
  "minMinutes", "marketValueMinM", "marketValueMaxM", "wageMinM", "wageMaxM",
  "contractExpiringMonths", "archetype",
] as const satisfies readonly (keyof FilterState)[];

export function filterStateFromSearchParams(params: URLSearchParams, defaultSeason: string): FilterState {
  const base = emptyFilterState(params.get("season") || defaultSeason);
  const next: FilterState = { ...base };
  for (const key of STRING_KEYS) {
    const v = params.get(key);
    if (v !== null) next[key] = v;
  }
  const clause = params.get("hasReleaseClause");
  if (clause === "yes" || clause === "no" || clause === "any") next.hasReleaseClause = clause;
  const sort = params.get("sort");
  if (sort === "composite_index" || sort === "market_value" || sort === "name") {
    next.sort = sort;
  }
  return next;
}

function num(s: string): number | undefined {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
}

function millionsToEur(s: string): number | undefined {
  const n = num(s);
  return n === undefined ? undefined : n * 1_000_000;
}

/** Builds the GET /players/search query from filter state + pagination.
 * Team only takes effect when paired with a league - the form disables
 * the team input until then, so this never silently drops an active filter. */
export function toSearchParams(
  filters: FilterState,
  pagination: { limit: number; offset: number },
): SearchPlayersParams {
  return {
    season: filters.season,
    position: filters.position || undefined,
    league: filters.league || undefined,
    team: filters.league ? filters.team || undefined : undefined,
    age_min: num(filters.ageMin),
    age_max: num(filters.ageMax),
    nationality: filters.nationality || undefined,
    min_minutes: num(filters.minMinutes),
    market_value_min: millionsToEur(filters.marketValueMinM),
    market_value_max: millionsToEur(filters.marketValueMaxM),
    wage_min: millionsToEur(filters.wageMinM),
    wage_max: millionsToEur(filters.wageMaxM),
    contract_expiring_months: num(filters.contractExpiringMonths),
    has_release_clause:
      filters.hasReleaseClause === "any" ? undefined : filters.hasReleaseClause === "yes",
    min_goals_per90: num(filters.minGoalsPer90),
    min_assists_per90: num(filters.minAssistsPer90),
    min_xg_per90: num(filters.minXgPer90),
    min_npxg_per90: num(filters.minNpxgPer90),
    min_progressive_passes: num(filters.minProgressivePasses),
    min_tackles: num(filters.minTackles),
    min_sca_per90: num(filters.minScaPer90),
    min_gca_per90: num(filters.minGcaPer90),
    archetype: filters.archetype || undefined,
    sort: filters.sort,
    limit: pagination.limit,
    offset: pagination.offset,
  };
}
