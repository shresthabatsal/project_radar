"use client";

import { motion } from "motion/react";

const SIZES = {
  sm: 24,
  md: 48,
  lg: 96,
  xl: 420,
} as const;

type RadarSweepProps = {
  size?: keyof typeof SIZES;
  label?: string;
  className?: string;
  /** Purely visual (e.g. a hero background flourish) - hidden from screen
   * readers and skips the "status"/label semantics used everywhere else
   * this renders as an actual loading indicator. */
  decorative?: boolean;
};

/**
 * Radar's signature loading/scanning indicator: a rotating conic-gradient
 * sweep over concentric rings, used consistently anywhere the app is
 * fetching or computing (search, similarity, model predictions).
 */
export function RadarSweep({ size = "md", label, className, decorative = false }: RadarSweepProps) {
  const px = SIZES[size];

  return (
    <div
      role={decorative ? undefined : "status"}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : (label ?? "Loading")}
      className={`inline-flex flex-col items-center gap-3 ${className ?? ""}`}
    >
      <div
        className="relative rounded-full border border-primary-200 dark:border-primary-800"
        style={{ width: px, height: px }}
      >
        <div className="absolute inset-[16%] rounded-full border border-primary-200/70 dark:border-primary-800/70" />
        <div className="absolute inset-[38%] rounded-full border border-primary-200/50 dark:border-primary-800/50" />
        <div className="absolute inset-0 top-1/2 left-1/2 h-px w-1/2 -translate-y-1/2 bg-primary-200/60 dark:bg-primary-800/60" />
        <div className="absolute inset-1/2 top-0 left-1/2 h-1/2 w-px -translate-x-1/2 bg-primary-200/60 dark:bg-primary-800/60" />

        <motion.div
          className="absolute inset-0 rounded-full"
          style={{
            // Tailwind's JS-config-driven utilities (bg-primary-500, etc.)
            // compile to literal color values, not --color-* CSS variables
            // (those only get emitted for colors declared via an @theme
            // block) - so the brand hex is inlined directly here too.
            background:
              "conic-gradient(from 0deg, transparent 0deg, transparent 270deg, #009258 350deg, #47b187 360deg)",
            maskImage: "radial-gradient(circle, transparent 0%, black 100%)",
            WebkitMaskImage: "radial-gradient(circle, transparent 0%, black 100%)",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
        />

        <div className="absolute inset-0 flex items-center justify-center">
          <span className="h-1.5 w-1.5 rounded-full bg-primary-500" />
        </div>
      </div>

      {!decorative && label && (
        <span className="text-xs font-medium tracking-wide text-primary-600 dark:text-primary-400">
          {label}
        </span>
      )}
      {!decorative && <span className="sr-only">{label ?? "Loading"}</span>}
    </div>
  );
}
