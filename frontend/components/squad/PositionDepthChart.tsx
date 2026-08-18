"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { PositionDepthEntry } from "@/lib/types";
import { buildRecruitHref } from "./recruitLink";

const POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeeper",
  DF: "Defender",
  MF: "Midfielder",
  FW: "Forward",
};

type PositionDepthChartProps = {
  data: PositionDepthEntry[];
  season: string;
  league: string;
  minDepth: number;
};

/** Count + composite-index range per position. Healthy depth reads in the
 * brand primary color; a "thin" position (fewer rostered players than
 * minDepth) gets an amber-bordered card and a distinct fill color on its
 * range bar - never bare red/green, just a clearly different treatment. */
export function PositionDepthChart({ data, season, league, minDepth }: PositionDepthChartProps) {
  return (
    <div className="flex flex-col gap-3">
      {data.map((d, i) => (
        <motion.div
          key={d.position}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: i * 0.08, ease: "easeOut" }}
          className={`flex flex-col gap-3 rounded-xl border p-4 ${
            d.is_thin
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
              {d.is_thin && (
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 font-sans text-[11px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  Thin - fewer than {minDepth} rostered
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-display text-2xl font-semibold text-foreground">{d.count}</span>
              <span className="font-sans text-xs text-foreground/40">rostered</span>
            </div>
          </div>

          <div className="relative h-2.5 overflow-hidden rounded-full bg-primary-50 dark:bg-primary-950">
            <motion.div
              className={`h-full rounded-full ${d.is_thin ? "bg-amber-400" : "bg-primary-500"}`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(0, Math.min(100, d.avg_composite ?? 0))}%` }}
              transition={{ duration: 0.6, delay: i * 0.08 + 0.1, ease: "easeOut" }}
            />
            {d.best_composite != null && (
              <div
                className="absolute top-0 h-full w-0.5 bg-foreground/60"
                style={{ left: `${Math.max(0, Math.min(100, d.best_composite))}%` }}
                title={`Best: ${d.best_player} (${d.best_composite.toFixed(1)})`}
              />
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 font-sans text-xs text-foreground/50">
            <span>Avg composite {d.avg_composite != null ? d.avg_composite.toFixed(1) : "—"}</span>
            <span>
              {d.best_composite != null ? (
                <>
                  Best {d.best_composite.toFixed(1)} ·{" "}
                  {d.best_player_id ? (
                    <Link
                      href={`/players/${d.best_player_id}`}
                      className="hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                    >
                      {d.best_player}
                    </Link>
                  ) : (
                    d.best_player
                  )}
                </>
              ) : (
                "—"
              )}
            </span>
          </div>

          {d.is_thin && (
            <Link
              href={buildRecruitHref({ season, league, position: d.position })}
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
