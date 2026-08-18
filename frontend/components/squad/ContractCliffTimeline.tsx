"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { ContractCliffEntry } from "@/lib/types";
import { buildRecruitHref } from "./recruitLink";

function formatDate(raw: string | null): string {
  if (!raw) return "—";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

type ContractCliffTimelineProps = {
  data: ContractCliffEntry[];
  season: string;
  league: string;
};

/** Upcoming contract expiries, in the exact order the backend ranked them -
 * highest-impact (composite index, then minutes) first, not just whichever
 * expiry date happens to be soonest. Rendered as a timeline; each entry's
 * urgency comes straight from the backend's own short/long window flags. */
export function ContractCliffTimeline({ data, season, league }: ContractCliffTimelineProps) {
  if (data.length === 0) {
    return <p className="font-sans text-sm text-foreground/50">No contracts expiring within the tracked window.</p>;
  }

  return (
    <div className="flex flex-col">
      {data.map((c, i) => (
        <motion.div
          key={`${c.player}-${i}`}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: i * 0.06, ease: "easeOut" }}
          className="relative flex gap-4"
        >
          <div className="flex flex-col items-center">
            <span
              className={`z-10 mt-1.5 h-3 w-3 shrink-0 rounded-full ${
                c.within_short_window ? "bg-amber-500" : "bg-primary-400"
              }`}
            />
            {i < data.length - 1 && <span className="w-px flex-1 bg-primary-100 dark:bg-primary-900" />}
          </div>

          <div className="flex flex-1 flex-col gap-1.5 pb-6">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/players/${c.id}`}
                className="font-display text-base font-semibold text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
              >
                {c.player}
              </Link>
              <span className="rounded-full bg-primary-50 px-2 py-0.5 font-sans text-[11px] font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                {c.position}
              </span>
              {c.within_short_window && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-sans text-[11px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  Expires soon
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 font-sans text-xs text-foreground/60">
              <span>
                {formatDate(c.contract_expiry)} ({c.contract_months_remaining} mo)
              </span>
              {c.composite_index != null && <span>Composite {c.composite_index.toFixed(1)}</span>}
              {c.minutes != null && <span>{Math.round(c.minutes).toLocaleString()} minutes</span>}
              {c.age != null && <span>{c.age.toFixed(0)} yo</span>}
            </div>
            <Link
              href={buildRecruitHref({ season, league, position: c.position })}
              className="mt-1 inline-flex w-fit items-center gap-1 rounded-full border border-amber-300 px-3 py-1 font-sans text-xs font-medium text-amber-700 transition hover:bg-amber-100 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-950"
            >
              Recruit for this gap →
            </Link>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
