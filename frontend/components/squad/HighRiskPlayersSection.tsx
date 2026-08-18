"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { PlayerRiskAssessment } from "@/lib/types";
import { riskReasonStyle } from "@/lib/riskReasons";

type HighRiskPlayersSectionProps = {
  data: PlayerRiskAssessment[];
};

/** backend/scoring/risk.py's four independent risk reasons, for whichever
 * rostered players triggered at least one - styled as a timeline like the
 * Contract Cliff section above it (same dot-and-line rhythm, same
 * highest-impact-first ordering the backend already applies), but every
 * triggered reason gets its own colored chip since a player can trigger
 * several at once and they need to read as separate flags, not one merged
 * "at risk" verdict. Diagnostic only, same tone as every other squad-
 * profile flag (thin position, aging position, contract cliff) - this
 * surfaces reasons, it never recommends selling anyone. */
export function HighRiskPlayersSection({ data }: HighRiskPlayersSectionProps) {
  if (data.length === 0) {
    return <p className="font-sans text-sm text-foreground/50">No players currently flag any risk reason.</p>;
  }

  return (
    <div className="flex flex-col">
      {data.map((p, i) => (
        <motion.div
          key={`${p.player}-${i}`}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: i * 0.06, ease: "easeOut" }}
          className="relative flex gap-4"
        >
          <div className="flex flex-col items-center">
            <span className="z-10 mt-1.5 h-3 w-3 shrink-0 rounded-full bg-red-500" />
            {i < data.length - 1 && <span className="w-px flex-1 bg-primary-100 dark:bg-primary-900" />}
          </div>

          <div className="flex flex-1 flex-col gap-1.5 pb-6">
            <div className="flex flex-wrap items-center gap-2">
              {p.id ? (
                <Link
                  href={`/players/${p.id}`}
                  className="font-display text-base font-semibold text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                >
                  {p.player}
                </Link>
              ) : (
                <span className="font-display text-base font-semibold text-foreground">{p.player}</span>
              )}
              <span className="rounded-full bg-primary-50 px-2 py-0.5 font-sans text-[11px] font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                {p.position}
              </span>
              {p.reasons.map((r) => (
                <span
                  key={r.reason}
                  title={r.detail ?? r.label}
                  className={`rounded-full px-2 py-0.5 font-sans text-[11px] font-medium ${riskReasonStyle(r.reason).chipClass}`}
                >
                  {riskReasonStyle(r.reason).short}
                </span>
              ))}
            </div>
            <div className="flex flex-col gap-1">
              {p.reasons.map((r) => (
                <p key={r.reason} className="font-sans text-xs text-foreground/60">
                  {r.detail}
                </p>
              ))}
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
