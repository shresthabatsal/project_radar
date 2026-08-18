"use client";

import { motion } from "motion/react";
import type { MetaResponse } from "@/lib/types";
import { formatLastUpdated, seasonRangeLabel } from "@/lib/format";
import { RadarSweep } from "@/components/RadarSweep";

type DataCoverageSectionProps = {
  meta: MetaResponse | null;
  loading: boolean;
};

export function DataCoverageSection({ meta, loading }: DataCoverageSectionProps) {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-4xl">
        <div className="text-center">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-foreground">
            What&apos;s in the data
          </h2>
          <p className="mx-auto mt-4 max-w-xl font-sans text-base leading-7 text-foreground/70">
            Every score on Radar is computed from real match performance combined with market
            value, wage, and contract data, drawn from multiple independent sources.
          </p>
        </div>

        {loading && (
          <div className="mt-14 flex justify-center">
            <RadarSweep size="md" label="Loading coverage" />
          </div>
        )}

        {!loading && meta && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="mt-14 grid grid-cols-1 gap-8 rounded-2xl border border-primary-100 bg-white p-8 dark:border-primary-900 dark:bg-[#111a17] sm:grid-cols-2 lg:grid-cols-4"
          >
            <div>
              <p className="font-display text-2xl font-semibold text-primary-600 dark:text-primary-400">
                {meta.leagues.length}
              </p>
              <p className="mt-1 font-sans text-sm text-foreground/60">Leagues covered</p>
              <p className="mt-3 font-sans text-xs leading-5 text-foreground/50">
                {meta.leagues.map((l) => l.label).join(", ")}
              </p>
            </div>

            <div>
              <p className="font-display text-2xl font-semibold text-primary-600 dark:text-primary-400">
                {meta.seasons.length}
              </p>
              <p className="mt-1 font-sans text-sm text-foreground/60">Seasons of data</p>
              <p className="mt-3 font-sans text-xs leading-5 text-foreground/50">
                {seasonRangeLabel(meta.seasons)}
              </p>
            </div>

            <div>
              <p className="font-display text-2xl font-semibold text-primary-600 dark:text-primary-400">
                Performance + Value
              </p>
              <p className="mt-1 font-sans text-sm text-foreground/60">Data combined per player</p>
              <p className="mt-3 font-sans text-xs leading-5 text-foreground/50">
                Standard match stats alongside market value, wages, contract status, and
                on-pitch differential (WOWY) data.
              </p>
            </div>

            <div>
              <p className="font-display text-2xl font-semibold text-primary-600 dark:text-primary-400">
                Multi-Source
              </p>
              <p className="mt-1 font-sans text-sm text-foreground/60">3 data providers</p>
              <p className="mt-3 font-sans text-xs leading-5 text-foreground/50">
                Primary match stats are supplemented with independent Understat and FotMob data
                for a fuller picture of each player.
              </p>
            </div>
          </motion.div>
        )}

        {!loading && meta?.last_updated && (
          <p className="mt-6 text-center font-sans text-xs text-foreground/40">
            Data last refreshed {formatLastUpdated(meta.last_updated)}
          </p>
        )}
      </div>
    </section>
  );
}
