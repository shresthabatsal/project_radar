"use client";

import { useCallback } from "react";
import { getRawData } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";

/** Every raw per-90/per-season metric on file, grouped by this player's OWN
 * position's style categories - same category set, order, and emphasis
 * backend/scoring/composite.py's radar/composite index already use for that
 * position (a forward leads with Finishing, a defender with Defensive
 * Actions, etc.). Deliberately un-scored: no percentiles, no composite -
 * just the underlying numbers, numbered in the order this position's own
 * categories carry weight. */
export function RawDataSection({ id }: { id: string }) {
  const fetcher = useCallback(() => getRawData(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load raw data.");

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">Profile</h2>
        <p className="mt-1 font-sans text-sm text-foreground/60">
          {data
            ? `Every raw metric on file for this ${data.season} season, grouped by the same ${data.position} style categories - in the same order - the composite index and radar already use. No scores here, just the numbers.`
            : "Every raw metric on file, grouped by this position's own style categories."}
        </p>
      </div>

      <div className="min-h-[200px] rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        {loading ? (
          <div className="flex min-h-[160px] items-center justify-center">
            <RadarSweep size="lg" label="Loading raw data" />
          </div>
        ) : error ? (
          <p className="text-center font-sans text-sm text-red-500">{error}</p>
        ) : !data || data.categories.length === 0 ? (
          <p className="text-center font-sans text-sm text-foreground/50">
            No raw metric data on file for this player-season.
          </p>
        ) : (
          <div className="flex flex-col gap-6">
            {data.categories.map((cat, i) => (
              <div key={cat.category} className="flex flex-col gap-3">
                <h3 className="flex items-center gap-2 font-sans text-xs font-semibold uppercase tracking-wide text-foreground/50">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary-100 text-[10px] font-bold text-primary-700 dark:bg-primary-900 dark:text-primary-300">
                    {i + 1}
                  </span>
                  {cat.category}
                </h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {cat.metrics.map((m) => (
                    <div
                      key={m.key}
                      className="flex flex-col gap-0.5 rounded-lg border border-primary-50 px-3 py-2 font-sans dark:border-primary-950"
                    >
                      <span className="text-xs text-foreground/50">{m.label}</span>
                      <span className="text-sm font-medium text-foreground">{m.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
