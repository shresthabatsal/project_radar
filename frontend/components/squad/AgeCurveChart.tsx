"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { AgeCurveEntry } from "@/lib/types";
import { buildRecruitHref } from "./recruitLink";

const POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeeper",
  DF: "Defender",
  MF: "Midfielder",
  FW: "Forward",
};

type AgeCurveChartProps = {
  data: AgeCurveEntry[];
  season: string;
  league: string;
  agingThreshold: number;
};

/** Age distribution per position as a dot-strip along a shared age axis (not
 * just an average) - each rostered player is one dot, colored amber past
 * the aging threshold (marked with a dashed reference line). A position
 * where a strict majority sit past that line is flagged "top-heavy". */
export function AgeCurveChart({ data, season, league, agingThreshold }: AgeCurveChartProps) {
  const allAges = data.flatMap((d) => d.players.map((p) => p.age).filter((a): a is number => a != null));
  const rawMin = allAges.length ? Math.min(...allAges) : 18;
  const rawMax = allAges.length ? Math.max(...allAges) : 35;
  const axisMin = Math.max(15, Math.floor(rawMin / 5) * 5 - 2);
  const axisMax = Math.ceil(rawMax / 5) * 5 + 2;
  const span = Math.max(1, axisMax - axisMin);
  const pctFor = (age: number) => Math.max(0, Math.min(100, ((age - axisMin) / span) * 100));
  const thresholdPct = pctFor(agingThreshold);

  return (
    <div className="flex flex-col gap-3">
      {data.map((d, i) => (
        <motion.div
          key={d.position}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: i * 0.08, ease: "easeOut" }}
          className={`flex flex-col gap-3 rounded-xl border p-4 ${
            d.is_top_heavy
              ? "border-amber-300 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-950/20"
              : "border-primary-100 dark:border-primary-900"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-lg font-semibold text-foreground">
                {POSITION_LABELS[d.position] ?? d.position}
              </span>
              <span className="font-sans text-xs text-foreground/40">{d.position}</span>
              {d.is_top_heavy && (
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 font-sans text-[11px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  Top-heavy · {d.aging_count}/{d.count} at {agingThreshold}+
                </span>
              )}
            </div>
            <span className="font-sans text-xs text-foreground/50">
              Avg age {d.avg_age != null ? d.avg_age.toFixed(1) : "—"}
            </span>
          </div>

          <div className="relative h-8">
            <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-primary-100 dark:bg-primary-900" />
            <div
              className="absolute top-0 h-full border-l border-dashed border-amber-400/70"
              style={{ left: `${thresholdPct}%` }}
              title={`Aging threshold: ${agingThreshold}`}
            />
            {d.players.map((p, pi) =>
              p.age == null ? null : (
                <motion.div
                  key={`${p.player}-${pi}`}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3, delay: i * 0.08 + pi * 0.02, ease: "easeOut" }}
                  className="group absolute top-1/2 z-0 -translate-x-1/2 -translate-y-1/2 focus:z-20 hover:z-20"
                  style={{ left: `${pctFor(p.age)}%` }}
                >
                  {/* The point itself is passive - hover/focus only, never a
                   * navigation target (see PositionDepthChart/WageOutputScatter
                   * for the same pattern). Only the player's name inside the
                   * tooltip below is a real link. */}
                  <div
                    tabIndex={0}
                    aria-label={`${p.player}, age ${p.age}`}
                    className={`h-2.5 w-2.5 cursor-default rounded-full outline-none ${
                      p.age >= agingThreshold ? "bg-amber-500" : "bg-primary-500"
                    }`}
                  />
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-primary-100 bg-white px-3 py-1.5 text-xs opacity-0 shadow-lg transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100 dark:border-primary-900 dark:bg-[#111a17]">
                    <Link
                      href={`/players/${p.id}`}
                      className="font-medium text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                    >
                      {p.player}
                    </Link>
                    <span className="ml-1.5 text-foreground/50">age {p.age}</span>
                  </div>
                </motion.div>
              ),
            )}
          </div>
          <div className="flex justify-between font-sans text-[10px] text-foreground/35">
            <span>{axisMin}</span>
            <span>age</span>
            <span>{axisMax}</span>
          </div>

          {d.is_top_heavy && (
            <Link
              href={buildRecruitHref({ season, league, position: d.position, ageMax: agingThreshold - 1 })}
              className="inline-flex w-fit items-center gap-1 rounded-full border border-amber-300 px-3 py-1.5 font-sans text-xs font-medium text-amber-700 transition hover:bg-amber-100 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-950"
            >
              Recruit for this gap →
            </Link>
          )}
        </motion.div>
      ))}
    </div>
  );
}
