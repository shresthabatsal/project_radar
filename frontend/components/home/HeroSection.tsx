"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "motion/react";
import { PlayerSearchBar } from "@/components/PlayerSearchBar";
import { RadarHeroVisual } from "@/components/home/RadarHeroVisual";

type HeroSectionProps = {
  season: string | null;
};

export function HeroSection({ season }: HeroSectionProps) {
  return (
    // min-h instead of a fixed height: fills one screen below the header
    // on load but grows rather than clipping. No overflow-hidden here -
    // the search dropdown is a sibling that must extend past this section's box.
    <section className="relative isolate flex min-h-[calc(100dvh-4rem)] flex-col items-center justify-center px-6 py-16">
      {/* Signature radar sweep - a quiet background presence behind the
          search column, not a competing focal point. Clipped to this
          section's bounds by its own wrapper, scoped separately so it can't clip the search dropdown below. */}
      <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden" aria-hidden="true">
        <RadarHeroVisual />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="mx-auto flex max-w-2xl flex-col items-center gap-6 text-center"
      >
        <Image
          src="/brand/radar_main_primary.png"
          alt="Radar"
          width={220}
          height={50}
          priority
          className="h-11 w-auto dark:hidden"
        />
        <Image
          src="/brand/radar_main_white.png"
          alt="Radar"
          width={220}
          height={50}
          priority
          className="hidden h-11 w-auto dark:block"
        />

        <p className="max-w-lg font-sans text-lg leading-7 text-foreground/70">
          Statistical scouting decision-support: composite performance, similarity search,
          hidden gems, market value, and moneyball scoring across 14 leagues.
        </p>

        <div className="mt-2 w-full max-w-xl">
          <PlayerSearchBar season={season} placeholder="Search for a player, e.g. Kevin De Bruyne" />
        </div>

        <Link
          href="/search"
          className="group inline-flex items-center gap-1.5 rounded-full border border-primary-200 px-4 py-2 font-sans text-sm font-medium text-primary-700 transition hover:border-primary-300 hover:bg-primary-50 dark:border-primary-800 dark:text-primary-300 dark:hover:bg-primary-950"
        >
          Advanced Search
          <svg
            className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>
      </motion.div>
    </section>
  );
}
