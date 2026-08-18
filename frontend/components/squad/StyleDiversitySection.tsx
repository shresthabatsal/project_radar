"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { StyleDiversityEntry } from "@/lib/types";
import { buildRecruitHref } from "./recruitLink";

const POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeeper",
  DF: "Defender",
  MF: "Midfielder",
  FW: "Forward",
};

type StyleDiversitySectionProps = {
  data: StyleDiversityEntry[];
  season: string;
  league: string;
};

/** Per position, how the squad's rostered players break down across
 * that position group's trained style archetypes - concrete counts, not
 * an abstract spread number. is_style_similar (amber) means every assignable player landed in the same archetype. */
export function StyleDiversitySection({ data, season, league }: StyleDiversitySectionProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {data.map((d, i) => {
        const flagged = d.is_style_similar === true;
        const maxCount = Math.max(1, ...d.archetypes.map((a) => a.count));
        return (
          <motion.div
            key={d.position}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.08, ease: "easeOut" }}
            className={`flex flex-col gap-3 rounded-xl border p-4 ${
              flagged
                ? "border-amber-300 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-950/20"
                : "border-primary-100 dark:border-primary-900"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-baseline gap-2">
                <span className="font-display text-base font-semibold text-foreground">
                  {POSITION_LABELS[d.position] ?? d.position}
                </span>
                <span className="font-sans text-xs text-foreground/40">{d.position}</span>
              </div>
              <span className="font-sans text-xs text-foreground/40">{d.count} rostered</span>
            </div>

            {d.archetypes.length === 0 ? (
              <p className="font-sans text-xs text-foreground/40">
                {d.position === "GK"
                  ? "Not applicable - goalkeepers aren't covered by style-archetype clustering."
                  : "No trained archetypes for this position yet."}
              </p>
            ) : (
              <>
                <div className="flex flex-col gap-1.5">
                  {d.archetypes.map((a) => (
                    <div key={a.cluster} className="flex items-center gap-2">
                      <span className="w-6 shrink-0 text-right font-sans text-xs font-semibold text-foreground/70">
                        {a.count}
                      </span>
                      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-primary-50 dark:bg-primary-950">
                        <motion.div
                          className={`h-full rounded-full ${
                            flagged && a.count > 0 ? "bg-amber-400" : "bg-primary-500"
                          }`}
                          initial={{ width: 0 }}
                          animate={{ width: `${(a.count / maxCount) * 100}%` }}
                          transition={{ duration: 0.6, delay: i * 0.08 + 0.1, ease: "easeOut" }}
                        />
                      </div>
                      <span className="w-40 shrink-0 truncate font-sans text-xs text-foreground/60" title={a.label}>
                        {a.label}
                      </span>
                    </div>
                  ))}
                </div>
                {flagged && (
                  <span className="w-fit rounded-full bg-amber-100 px-2 py-0.5 font-sans text-[11px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                    Style-similar - every option is the same archetype
                  </span>
                )}
              </>
            )}

            {flagged && (
              <Link
                href={buildRecruitHref({ season, league, position: d.position })}
                className="inline-flex w-fit items-center gap-1 rounded-full border border-amber-300 px-3 py-1.5 font-sans text-xs font-medium text-amber-700 transition hover:bg-amber-100 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-950"
              >
                Recruit for this gap →
              </Link>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
