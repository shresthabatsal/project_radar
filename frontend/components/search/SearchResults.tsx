"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import type { PlayerSearchResult } from "@/lib/types";
import type { PlayerSearchSort } from "@/lib/api";
import { RadarSweep } from "@/components/RadarSweep";
import { GemBadge } from "@/components/GemBadge";
import { listContainer, listItem } from "@/lib/motion";

type SearchResultsProps = {
  results: PlayerSearchResult[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  error: string | null;
  sort: PlayerSearchSort;
  onSortChange: (sort: PlayerSearchSort) => void;
  onPageChange: (offset: number) => void;
  /** Changes on every new search so the stagger animation replays instead
   * of only firing once on first mount. */
  searchKey: string;
};

function formatAge(age: number | null): string {
  return age != null ? String(Math.round(age)) : "—";
}

function formatContract(result: PlayerSearchResult): string {
  if (!result.contract_expiry) return "—";
  if (result.contract_months_remaining != null) {
    return `${result.contract_expiry} (${result.contract_months_remaining}mo)`;
  }
  return result.contract_expiry;
}

export function SearchResults({
  results,
  total,
  limit,
  offset,
  loading,
  error,
  sort,
  onSortChange,
  onPageChange,
  searchKey,
}: SearchResultsProps) {
  const router = useRouter();
  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-sans text-sm text-foreground/60">
          {loading ? "Searching…" : `${total.toLocaleString()} player${total === 1 ? "" : "s"} found`}
        </p>
        <label className="flex items-center gap-2 font-sans text-sm text-foreground/60">
          Sort by
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as PlayerSearchSort)}
            className="rounded-lg border border-primary-100 bg-white px-3 py-1.5 text-sm text-foreground outline-none ring-primary-400 focus:ring-2 dark:border-primary-900 dark:bg-[#111a17]"
          >
            <option value="composite_index">Composite index</option>
            <option value="market_value">Market value</option>
            <option value="name">Name</option>
          </select>
        </label>
      </div>

      <div className="min-h-[240px] rounded-2xl border border-primary-100 bg-white dark:border-primary-900 dark:bg-[#111a17]">
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex min-h-[240px] items-center justify-center py-16"
            >
              <RadarSweep size="lg" label="Searching players" />
            </motion.div>
          ) : error ? (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-red-500"
            >
              {error}
            </motion.div>
          ) : results.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-foreground/50"
            >
              No players match these filters. Try widening the range or clearing a few.
            </motion.div>
          ) : (
            <motion.div key={`results-${searchKey}`} className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse font-sans text-sm">
                <thead>
                  <tr className="border-b border-primary-100 text-left text-xs text-foreground/50 dark:border-primary-900">
                    <th className="px-4 py-3 font-medium">Player</th>
                    <th className="px-4 py-3 font-medium">Pos</th>
                    <th className="px-4 py-3 font-medium">Age</th>
                    <th className="px-4 py-3 font-medium">Nat.</th>
                    <th className="px-4 py-3 font-medium">League</th>
                    <th className="px-4 py-3 font-medium">Market value</th>
                    <th className="px-4 py-3 font-medium">Wage /yr</th>
                    <th className="px-4 py-3 font-medium">Contract</th>
                    <th className="px-4 py-3 font-medium">Composite</th>
                  </tr>
                </thead>
                <motion.tbody initial="hidden" animate="visible" variants={listContainer}>
                  {results.map((r) => (
                    <motion.tr
                      key={r.id}
                      variants={listItem}
                      onClick={() => router.push(`/players/${r.id}`)}
                      className="cursor-pointer border-b border-primary-50 transition hover:bg-primary-50/60 dark:border-primary-950 dark:hover:bg-primary-950/40"
                    >
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <span className="flex items-center gap-1.5">
                            <Link
                              href={`/players/${r.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-medium text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                            >
                              {r.player}
                            </Link>
                            {r.is_gem && <GemBadge />}
                          </span>
                          <span className="text-xs text-foreground/50">{r.team}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-foreground/70">{r.position}</td>
                      <td className="px-4 py-3 text-foreground/70">{formatAge(r.age)}</td>
                      <td className="px-4 py-3 text-foreground/70">{r.nationality ?? "—"}</td>
                      <td className="px-4 py-3 text-foreground/70">{r.league.replace(/-/g, " ")}</td>
                      <td className="px-4 py-3 text-foreground/70">{r.market_value_label ?? "—"}</td>
                      <td className="px-4 py-3 text-foreground/70">{r.wage_label ?? "—"}</td>
                      <td className="px-4 py-3 text-foreground/70">{formatContract(r)}</td>
                      <td className="px-4 py-3 font-medium text-primary-600 dark:text-primary-400">
                        {r.composite_index != null ? r.composite_index.toFixed(1) : "—"}
                      </td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {!loading && total > limit && (
        <div className="flex items-center justify-center gap-4 font-sans text-sm">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            className="rounded-full border border-primary-200 px-4 py-1.5 text-foreground/70 transition hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-primary-800 dark:hover:bg-primary-950"
          >
            Previous
          </button>
          <span className="text-foreground/50">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => onPageChange(offset + limit)}
            className="rounded-full border border-primary-200 px-4 py-1.5 text-foreground/70 transition hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-primary-800 dark:hover:bg-primary-950"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
