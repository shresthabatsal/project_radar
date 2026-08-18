"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "motion/react";
import { getCareerHistory } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { CountUp } from "@/components/CountUp";
import { CareerCompositeChart } from "@/components/profile/CareerCompositeChart";

// Matches CountUp's own default duration prop - kept as one shared constant
// so the "mark the one-time animation as done" timer below can't drift out
// of sync with the animation it's timing.
const COMPOSITE_COUNT_UP_SECONDS = 1;

function seasonShort(season: string): string {
  const [a, b] = season.split("-");
  return b ? `${a}-${b.slice(-2)}` : season;
}

function Bio({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-foreground/50">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

/** Season selector/timeline built from GET /players/{id}/history - defaults
 * to the season the rest of the profile is already showing (if present in
 * the history), otherwise the most recent season on file, plus a Composite
 * Index trend chart across the real history. */
export function CareerHistorySection({ id, currentSeason }: { id: string; currentSeason?: string }) {
  const fetcher = useCallback(() => getCareerHistory(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load career history.");

  // null = no explicit click yet - default to the season the rest of the
  // profile is already showing (if present in the history), else the most
  // recent one. Derived during render, not an effect: this is plain state
  // synchronization, not a subscription to an external system.
  const [manualSelected, setManualSelected] = useState<number | null>(null);
  const defaultIndex = data && data.history.length > 0
    ? (() => {
        const currentIdx = currentSeason ? data.history.findIndex((h) => h.season === currentSeason) : -1;
        return currentIdx >= 0 ? currentIdx : data.history.length - 1;
      })()
    : null;
  const selected = manualSelected ?? defaultIndex;
  const season = data && selected != null ? data.history[selected] : null;

  // The count-up-from-zero animation should only ever play once, for
  // whichever season first has a real composite value to show - switching
  // seasons afterward (the timeline buttons above don't unmount this
  // component, so CountUp's own value-changed effect would otherwise replay
  // it every time) just fades the new number in instead. The effect's own
  // guard (bail once hasAnimatedOnce is true) means the timer is only ever
  // scheduled once per component instance, regardless of how many times
  // season.composite changes afterward.
  const [hasAnimatedOnce, setHasAnimatedOnce] = useState(false);
  useEffect(() => {
    if (hasAnimatedOnce || season?.composite == null) return;
    const timer = setTimeout(() => setHasAnimatedOnce(true), COMPOSITE_COUNT_UP_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [season?.composite, hasAnimatedOnce]);
  const isFirstAnimation = !hasAnimatedOnce;

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">Career</h2>
        <p className="mt-1 font-sans text-sm text-foreground/60">
          Step through past seasons - composite index is recomputed fresh in each season&apos;s own
          league context, not carried over from today.
        </p>
      </div>

      <div className="min-h-[240px] rounded-2xl border border-primary-100 bg-white dark:border-primary-900 dark:bg-[#111a17]">
        {loading ? (
          <div className="flex min-h-[240px] items-center justify-center">
            <RadarSweep size="lg" label="Loading career history" />
          </div>
        ) : error ? (
          <div className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-red-500">
            {error}
          </div>
        ) : !data || data.history.length === 0 ? (
          <div className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-foreground/50">
            No prior-season history on file for this player.
          </div>
        ) : (
          <div className="flex flex-col gap-6 p-6">
            <div className="flex gap-2 overflow-x-auto pb-2">
              {data.history.map((h, i) => (
                <button
                  key={h.id}
                  type="button"
                  onClick={() => setManualSelected(i)}
                  className={`flex shrink-0 flex-col items-center gap-0.5 rounded-xl border px-4 py-2 font-sans text-xs transition ${
                    selected === i
                      ? "border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-950 dark:text-primary-300"
                      : "border-primary-100 text-foreground/60 hover:bg-primary-50/60 dark:border-primary-900 dark:hover:bg-primary-950/40"
                  }`}
                >
                  <span className="font-semibold">{seasonShort(h.season)}</span>
                  <span className="text-[10px] text-foreground/40">{h.team}</span>
                </button>
              ))}
            </div>

            {season && (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-[auto_1fr]">
                <div className="flex flex-col items-center justify-center gap-1 rounded-xl border border-primary-100 px-8 py-4 dark:border-primary-900">
                  <span className="whitespace-nowrap font-sans text-xs text-foreground/50">Composite Index</span>
                  {season.composite != null ? (
                    isFirstAnimation ? (
                      <CountUp
                        value={season.composite}
                        decimals={1}
                        duration={COMPOSITE_COUNT_UP_SECONDS}
                        className="font-display text-4xl font-semibold text-primary-600 dark:text-primary-400"
                      />
                    ) : (
                      <motion.span
                        key={season.id}
                        initial={{ opacity: 0.3 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.25, ease: "easeOut" }}
                        className="font-display text-4xl font-semibold text-primary-600 dark:text-primary-400"
                      >
                        {season.composite.toFixed(1)}
                      </motion.span>
                    )
                  ) : (
                    <span className="font-display text-2xl text-foreground/30">—</span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 font-sans text-sm sm:grid-cols-3">
                  <Bio label="Team" value={season.team} />
                  <Bio label="League" value={season.league.replace(/-/g, " ")} />
                  <Bio label="Position" value={season.position} />
                  <Bio label="Age" value={season.age != null ? Math.round(season.age).toString() : "—"} />
                  <Bio
                    label="Minutes"
                    value={season.minutes != null ? Math.round(season.minutes).toLocaleString() : "—"}
                  />
                  <Bio label="Games" value={season.games != null ? Math.round(season.games).toString() : "—"} />
                  <Bio label="Goals" value={season.goals != null ? season.goals.toString() : "—"} />
                  <Bio label="Assists" value={season.assists != null ? season.assists.toString() : "—"} />
                  <Bio label="xG" value={season.xg != null ? season.xg.toFixed(1) : "—"} />
                </div>
              </div>
            )}

            {/* Composite Index trend - the full real history. Independent of
                whichever season is selected in the timeline above - this is
                a whole-career overview, not scoped to one season. */}
            <div className="border-t border-primary-100 pt-6 dark:border-primary-900">
              <span className="mb-3 block font-sans text-xs font-medium uppercase tracking-wide text-foreground/50">
                Composite Index Trend
              </span>
              <CareerCompositeChart
                history={data.history.map((h) => ({ id: h.id, season: h.season, composite: h.composite }))}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
