"use client";

import { useCallback } from "react";
import { motion } from "motion/react";
import { getMoneyballScore } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { CountUp } from "@/components/CountUp";

// Weights match backend/config.py's MONEYBALL_*_WEIGHT constants (50/30/20) -
// static labels, not fetched, since these are stable scoring constants (the
// homepage's "How it works" section describes the same blend in prose).
// Descriptions are worded to match what each score actually measures in the
// backend: performance_score is the composite index (backend/scoring/
// composite.py), value_efficiency is performance-vs-wage
// (value_ratio_raw/value_eff in scout_engine.cmd_get_moneyball_score), and
// contract_opportunity is contract_opportunity_breakdown()'s urgency +
// release-clause discount (backend/scoring/moneyball.py).
const COMPONENTS: { key: "performance_score" | "value_efficiency" | "contract_opportunity"; label: string; weight: string; description: string }[] = [
  {
    key: "performance_score",
    label: "Performance",
    weight: "50%",
    description:
      "How well this player performs relative to others in their position and league, combining output, playing style, and league strength.",
  },
  {
    key: "value_efficiency",
    label: "Value Efficiency",
    weight: "30%",
    description:
      "How much performance this player delivers relative to their cost - high efficiency means strong output for a relatively low wage.",
  },
  {
    key: "contract_opportunity",
    label: "Contract Opportunity",
    weight: "20%",
    description:
      "How favorable the timing is for a move - factoring in months remaining on their contract and any release clause.",
  },
];

export function MoneyballSection({ id }: { id: string }) {
  const fetcher = useCallback(() => getMoneyballScore(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load moneyball score.");

  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold text-foreground">Moneyball Score</h2>

      <div className="min-h-[160px] rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        {loading ? (
          <div className="flex min-h-[160px] items-center justify-center">
            <RadarSweep label="Computing moneyball score" />
          </div>
        ) : error ? (
          <div className="flex min-h-[160px] items-center justify-center text-center font-sans text-sm text-red-500">
            {error}
          </div>
        ) : !data ? null : (
          <div className="flex flex-col gap-6">
            <CountUp
              value={data.moneyball_score}
              decimals={1}
              className="font-display text-5xl font-semibold text-primary-600 dark:text-primary-400"
            />
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              {COMPONENTS.map((c, i) => {
                const value = data[c.key];
                return (
                  <div key={c.key} className="flex flex-col gap-2">
                    <div className="flex items-baseline justify-between">
                      <span className="font-sans text-xs text-foreground/60">{c.label}</span>
                      <span className="font-sans text-[10px] text-foreground/35">{c.weight} weight</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-primary-50 dark:bg-primary-950">
                      <motion.div
                        className="h-full rounded-full bg-primary-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                        transition={{ duration: 0.6, delay: i * 0.08, ease: "easeOut" }}
                      />
                    </div>
                    <span className="font-display text-lg font-semibold text-foreground">{value.toFixed(1)}</span>
                    <p className="font-sans text-xs leading-snug text-foreground/50">{c.description}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
