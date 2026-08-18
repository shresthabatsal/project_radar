"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import type { SimilarMetricGroup, SimilarPlayerMatch } from "@/lib/types";

type RawCompareModalProps = {
  open: boolean;
  onClose: () => void;
  targetId: string;
  targetName: string;
  candidate: SimilarPlayerMatch | null;
  metricGroups: SimilarMetricGroup[];
};

/**
 * A factual, raw-metrics-only side-by-side - no composite index,
 * category scores, gem status, market value, or moneyball score. The
 * Difference column is a plain subtraction, not an evaluative judgment.
 */
export function RawCompareModal({ open, onClose, targetId, targetName, candidate, metricGroups }: RawCompareModalProps) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && candidate && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-8"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={`Raw metric comparison: ${targetName} vs ${candidate.player}`}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-primary-100 bg-white shadow-xl dark:border-primary-900 dark:bg-[#111a17]"
          >
            <div className="flex items-start justify-between gap-4 border-b border-primary-100 px-6 py-5 dark:border-primary-900">
              <div>
                <h3 className="font-display text-lg font-semibold text-foreground">Raw Metric Comparison</h3>
                <p className="mt-1 font-sans text-xs text-foreground/50">Per-90 statistics, unranked - no scores or verdicts.</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 font-sans text-sm">
                  <Link
                    href={`/players/${targetId}`}
                    className="font-medium text-primary-600 underline-offset-2 hover:underline dark:text-primary-400"
                  >
                    {targetName}
                  </Link>
                  <span className="text-foreground/40">vs</span>
                  <Link
                    href={`/players/${candidate.id}`}
                    className="font-medium text-primary-600 underline-offset-2 hover:underline dark:text-primary-400"
                  >
                    {candidate.player}
                  </Link>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close comparison"
                className="shrink-0 rounded-full p-1.5 text-foreground/50 transition hover:bg-primary-50 hover:text-foreground dark:hover:bg-primary-950"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="overflow-y-auto px-6 py-5">
              {metricGroups.length === 0 ? (
                <p className="font-sans text-sm text-foreground/50">No metric data available for this position.</p>
              ) : (
                <div className="flex flex-col gap-6">
                  {metricGroups.map((group) => (
                    <div key={group.category}>
                      <h4 className="font-sans text-xs font-semibold uppercase tracking-wide text-foreground/40">
                        {group.category}
                      </h4>
                      <table className="mt-2 w-full border-collapse font-sans text-sm">
                        <thead>
                          <tr className="text-left text-xs text-foreground/50">
                            <th className="w-2/5 py-1.5 font-medium">Metric</th>
                            <th className="py-1.5 text-right font-medium">{targetName}</th>
                            <th className="py-1.5 text-right font-medium">Difference</th>
                            <th className="py-1.5 text-right font-medium">{candidate.player}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.metrics.map((m) => {
                            const row = candidate.metrics[m.key];
                            return (
                              <tr key={m.key} className="border-t border-primary-50 dark:border-primary-950">
                                <td className="py-1.5 text-foreground/70">{m.label}</td>
                                <td className="py-1.5 text-right text-foreground">{row?.target ?? "N/A"}</td>
                                <td className="py-1.5 text-right text-foreground/70">{row?.diff ?? "N/A"}</td>
                                <td className="py-1.5 text-right text-foreground">{row?.value ?? "N/A"}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
