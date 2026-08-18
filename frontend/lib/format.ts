// Small formatting helpers shared across homepage sections (and reusable
// later wherever the same backend value shapes show up again).

/** GET /meta's last_updated is a naive SQLite timestamp string
 * ("2026-07-13 13:16:48.448426") - not directly Date-parseable in every
 * browser, so normalize it to ISO 8601 with millisecond precision first. */
export function formatLastUpdated(raw: string): string {
  const isoish = raw.includes(" ") ? raw.replace(" ", "T") : raw;
  const trimmed = isoish.replace(/(\.\d{3})\d*$/, "$1");
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** seasons is sorted newest-first (see backend/routers/meta.py). */
export function seasonRangeLabel(seasons: string[]): string {
  if (seasons.length === 0) return "";
  const newest = seasons[0];
  const oldest = seasons[seasons.length - 1];
  if (newest === oldest) return newest;
  return `${oldest} – ${newest}`;
}
