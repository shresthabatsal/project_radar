"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { WageOutputPoint } from "@/lib/types";

function formatWage(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${(n / 1_000).toFixed(0)}K`;
  return `€${n.toFixed(0)}`;
}

const WIDTH = 640;
const HEIGHT = 340;
const PAD_LEFT = 46;
const PAD_RIGHT = 16;
const PAD_TOP = 20;
const PAD_BOTTOM = 36;

// Below this % from the chart's top edge, the tooltip flips to render below
// the point instead of above - otherwise it pops off the top of the chart.
// Below/above these % from the left edge, the tooltip anchors to that side
// of the point instead of centering on it - otherwise it overflows left/right.
const TOP_FLIP_PCT = 20;
const LEFT_ANCHOR_PCT = 15;
const RIGHT_ANCHOR_PCT = 85;

function tooltipPositionClass(topPct: number, leftPct: number): string {
  const vertical = topPct < TOP_FLIP_PCT ? "top-full mt-2" : "bottom-full mb-2";
  const horizontal =
    leftPct < LEFT_ANCHOR_PCT ? "left-0" : leftPct > RIGHT_ANCHOR_PCT ? "right-0" : "left-1/2 -translate-x-1/2";
  return `${vertical} ${horizontal}`;
}

function dotColorClass(eff: number | null): string {
  if (eff == null) return "fill-foreground/30";
  if (eff >= 65) return "fill-primary-500";
  if (eff <= 35) return "fill-amber-500";
  return "fill-foreground/40";
}

/** Composite index (y) vs. weekly wage (x), one dot per squad player - under/
 * over-paid players relative to output are visible across the whole squad at
 * once. Dot color follows value_efficiency (backend/scoring/moneyball.py's
 * formula): clearly above/below "fair" reads primary/amber, everything in
 * between stays neutral gray, rather than a full traffic-light gradient.
 * Points are passive - hovering (or focusing, for keyboard users) reveals an
 * HTML tooltip, and only the player's name inside that tooltip navigates to
 * their profile (same pattern as AgeCurveChart). The tooltip layer is a
 * sibling of the horizontally-scrollable SVG wrapper, not a descendant of
 * it - `overflow-x-auto` without an explicit overflow-y implicitly computes
 * overflow-y as `auto` too (CSS spec), which was silently clipping tooltips
 * that popped above points near the chart's top edge. Points near an edge
 * also flip/anchor the tooltip toward the chart's interior instead of
 * always centering above, so it never renders off the visible area. */
export function WageOutputScatter({ data }: { data: WageOutputPoint[] }) {
  const points = data.filter(
    (p): p is WageOutputPoint & { weekly_wage_eur: number; composite_index: number } =>
      p.weekly_wage_eur != null && p.composite_index != null,
  );

  if (points.length === 0) {
    return <p className="font-sans text-sm text-foreground/50">No wage data on file for this squad.</p>;
  }

  const maxWage = Math.max(...points.map((p) => p.weekly_wage_eur), 1);
  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const xFor = (wage: number) => PAD_LEFT + (wage / maxWage) * plotW;
  const yFor = (composite: number) => PAD_TOP + (1 - Math.max(0, Math.min(100, composite)) / 100) * plotH;

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxWage);
  const yTicks = [0, 25, 50, 75, 100];

  return (
    <div>
      <div className="relative mx-auto w-full max-w-2xl">
        <div className="overflow-x-auto">
          <svg
            width={WIDTH}
            height={HEIGHT}
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="mx-auto block w-full max-w-2xl"
            role="img"
            aria-label="Composite index versus weekly wage, one point per squad player"
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line
                  x1={PAD_LEFT}
                  x2={WIDTH - PAD_RIGHT}
                  y1={yFor(t)}
                  y2={yFor(t)}
                  className="stroke-primary-100 dark:stroke-primary-900"
                  strokeWidth={1}
                />
                <text
                  x={PAD_LEFT - 8}
                  y={yFor(t)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="fill-foreground/40 font-sans text-[10px]"
                >
                  {t}
                </text>
              </g>
            ))}
            {xTicks.map((t, i) => (
              <text
                key={i}
                x={xFor(t)}
                y={HEIGHT - PAD_BOTTOM + 16}
                textAnchor="middle"
                className="fill-foreground/40 font-sans text-[10px]"
              >
                {formatWage(t)}
              </text>
            ))}
            <text x={PAD_LEFT} y={HEIGHT - 6} className="fill-foreground/40 font-sans text-[10px]">
              Weekly wage
            </text>
            <text x={4} y={14} className="fill-foreground/40 font-sans text-[10px]">
              Composite
            </text>

            {points.map((p, i) => (
              <motion.circle
                key={`${p.player}-${i}`}
                cx={xFor(p.weekly_wage_eur)}
                cy={yFor(p.composite_index)}
                r={5}
                className={`${dotColorClass(p.value_efficiency)} stroke-white dark:stroke-[#111a17]`}
                strokeWidth={1}
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 0.9, scale: 1 }}
                transition={{ duration: 0.4, delay: i * 0.03, ease: "easeOut" }}
              />
            ))}
          </svg>
        </div>

        {/* Hover zones + tooltips, layered over the SVG via the same
         * xFor/yFor pixel math expressed as a % of the chart's own box - a
         * sibling of the overflow-x-auto wrapper above, not nested inside
         * it, so a tooltip escaping the chart's box is never clipped. */}
        <div className="pointer-events-none absolute inset-0">
          {points.map((p, i) => {
            const leftPct = (xFor(p.weekly_wage_eur) / WIDTH) * 100;
            const topPct = (yFor(p.composite_index) / HEIGHT) * 100;
            return (
              <div
                key={`hover-${p.player}-${i}`}
                tabIndex={0}
                aria-label={`${p.player}, ${p.position}, composite ${p.composite_index.toFixed(1)}, ${formatWage(p.weekly_wage_eur)} per week`}
                className="group pointer-events-auto absolute z-0 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-default outline-none focus:z-20 hover:z-20"
                style={{ left: `${leftPct}%`, top: `${topPct}%` }}
              >
                <div
                  className={`pointer-events-none absolute z-20 whitespace-nowrap rounded-lg border border-primary-100 bg-white px-3 py-1.5 text-xs opacity-0 shadow-lg transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100 dark:border-primary-900 dark:bg-[#111a17] ${tooltipPositionClass(topPct, leftPct)}`}
                >
                  <Link
                    href={`/players/${p.id}`}
                    className="font-medium text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                  >
                    {p.player}
                  </Link>
                  <div className="mt-0.5 text-foreground/50">
                    {p.position} · composite {p.composite_index.toFixed(1)} · {formatWage(p.weekly_wage_eur)}/wk
                    {p.wage_is_estimated ? " (est.)" : ""}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 font-sans text-xs text-foreground/60">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-primary-500" />
          Strong value
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-foreground/40" />
          Fair
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
          Overpaid vs. output
        </span>
      </div>
    </div>
  );
}
