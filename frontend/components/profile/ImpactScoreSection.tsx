"use client";

import { useCallback } from "react";
import { motion } from "motion/react";
import { getImpactScore } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { CountUp } from "@/components/CountUp";

export function ImpactScoreSection({ id }: { id: string }) {
  const fetcher = useCallback(() => getImpactScore(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load the impact score.");

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">Impact Score</h2>
        <p className="mt-1 font-sans text-sm text-foreground/60">
          How the team performs while this player is on the pitch versus off it - team goals/xG
          for and against, and the with-or-without-you differential. This is a separate signal
          from the Composite Index above, which measures the player&apos;s own individual output.
        </p>
      </div>

      <div className="min-h-[160px] rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        {loading ? (
          <div className="flex min-h-[160px] items-center justify-center">
            <RadarSweep label="Computing impact score" />
          </div>
        ) : error ? (
          <div className="flex min-h-[160px] items-center justify-center text-center font-sans text-sm text-red-500">
            {error}
          </div>
        ) : !data ? null : !data.qualifies ? (
          <div className="flex min-h-[120px] flex-col items-center justify-center gap-1 text-center">
            <span className="font-display text-3xl text-foreground/30">—</span>
            <p className="max-w-sm font-sans text-sm text-foreground/50">
              Not enough minutes played ({Math.round(data.minutes)} of {data.min_minutes} required) for a
              reliable on/off-pitch team differential.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col items-center gap-2 text-center sm:flex-row sm:items-baseline sm:justify-center sm:gap-4">
              <CountUp
                value={data.impact_score ?? 0}
                decimals={1}
                className="font-display text-5xl font-semibold text-primary-600 dark:text-primary-400"
              />
              {data.label && (
                <span className="rounded-full bg-primary-50 px-3 py-1 font-sans text-sm font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                  {data.label}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-4">
              {data.components.map((c, i) => (
                <div key={c.metric} className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-sans text-xs text-foreground/60">{c.label}</span>
                    <span className="font-sans text-xs text-foreground/40">
                      {c.value} &middot; {c.percentile.toFixed(0)}th pctl
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-primary-50 dark:bg-primary-950">
                    <motion.div
                      className="h-full rounded-full bg-primary-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(0, Math.min(100, c.percentile))}%` }}
                      transition={{ duration: 0.6, delay: i * 0.06, ease: "easeOut" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
