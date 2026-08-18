// "Recruit for this gap" - every flagged issue on the squad profile page
// hands off to the existing advanced-search page rather than recommending a
// replacement itself (that logic deliberately doesn't exist here - see
// backend/scoring/squad_profile.py's module docstring). Builds a /search
// deep link pre-filled with whatever the specific gap implies: position
// always, plus an age ceiling for an aging-position gap (recruit someone
// younger) when one is given. filterState.ts's filterStateFromSearchParams
// reads these same key names back out.
export interface RecruitLinkParams {
  season: string;
  league: string;
  position: string;
  ageMax?: number;
}

export function buildRecruitHref({ season, league, position, ageMax }: RecruitLinkParams): string {
  const params = new URLSearchParams();
  params.set("season", season);
  params.set("league", league);
  params.set("position", position);
  if (ageMax != null) params.set("ageMax", String(ageMax));
  return `/search?${params.toString()}`;
}
