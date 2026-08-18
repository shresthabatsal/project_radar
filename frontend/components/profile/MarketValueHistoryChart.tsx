"use client";

import { motion } from "motion/react";
import type { MarketValueTrajectoryPoint } from "@/lib/types";

function formatEurMillions(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${(n / 1_000).toFixed(0)}K`;
  return `€${n.toFixed(0)}`;
}

const WIDTH = 560;
const HEIGHT = 180;
const PAD_LEFT = 8;
const PAD_RIGHT = 8;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;

type PlotPoint = {
  key: string;
  season: string;
  value: number;
  isEstimated: boolean;
};

type MarketValueHistoryChartProps = {
  trajectory: MarketValueTrajectoryPoint[];
};

/** This player's REAL market value by season, as a small line/area chart -
 * only actual/recorded values (solid dot = verified on file, hollow dot =
 * the heuristic estimate used for a season with no real value on file).
 * Deliberately never plots a projected/future point - the model's own
 * valuation is a separate, present-tense estimate (see MarketValueSection's
 * "Model Valuation" card), not another point on this player's real value
 * history. */
export function MarketValueHistoryChart({ trajectory }: MarketValueHistoryChartProps) {
  const real = trajectory.filter((p) => p.display_mv != null);
  if (real.length === 0) {
    return <p className="font-sans text-sm text-foreground/50">No value history on file.</p>;
  }

  const points: PlotPoint[] = real.map((p) => ({
    key: p.season,
    season: p.season,
    value: p.display_mv as number,
    isEstimated: p.is_estimated,
  }));

  const values = points.map((p) => p.value);
  const minV = Math.min(...values, 0);
  const maxV = Math.max(...values, 1);
  const span = Math.max(1, maxV - minV);
  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const xFor = (i: number) => (points.length <= 1 ? PAD_LEFT + plotW / 2 : PAD_LEFT + (i / (points.length - 1)) * plotW);
  const yFor = (v: number) => PAD_TOP + (1 - (v - minV) / span) * plotH;

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${xFor(i).toFixed(1)},${yFor(p.value).toFixed(1)}`).join(" ");
  const areaPath =
    points.length > 0
      ? `${linePath} L${xFor(points.length - 1).toFixed(1)},${(HEIGHT - PAD_BOTTOM).toFixed(1)} ` +
        `L${xFor(0).toFixed(1)},${(HEIGHT - PAD_BOTTOM).toFixed(1)} Z`
      : "";

  return (
    <div>
      <div className="relative mx-auto w-full max-w-xl">
        <svg
          width={WIDTH}
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="mx-auto block w-full"
          role="img"
          aria-label="This player's real market value by season"
        >
          {areaPath && <path d={areaPath} className="fill-primary-500/10" />}
          {linePath && (
            <motion.path
              d={linePath}
              fill="none"
              className="stroke-primary-500"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          )}

          {points.map((p, i) => (
            <circle
              key={p.key}
              cx={xFor(i)}
              cy={yFor(p.value)}
              r={3.5}
              strokeWidth={1.5}
              className={
                p.isEstimated
                  ? "fill-white stroke-primary-500 dark:fill-[#111a17]"
                  : "fill-primary-500 stroke-white dark:stroke-[#111a17]"
              }
            />
          ))}

          {points.map((p, i) =>
            i % Math.ceil(points.length / 6) === 0 || i === points.length - 1 ? (
              <text
                key={`label-${p.key}`}
                x={xFor(i)}
                y={HEIGHT - 8}
                textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
                className="fill-foreground/40 font-sans text-[9px]"
              >
                {p.season.slice(2, 9)}
              </text>
            ) : null,
          )}
        </svg>

        {/* Hover zones + tooltips - a sibling of the SVG, not a descendant,
         * so a tooltip near the top edge is never clipped by an ancestor. */}
        <div className="pointer-events-none absolute inset-0">
          {points.map((p, i) => {
            const leftPct = (xFor(i) / WIDTH) * 100;
            const topPct = (yFor(p.value) / HEIGHT) * 100;
            return (
              <div
                key={`hover-${p.key}`}
                tabIndex={0}
                aria-label={`${p.season}, ${formatEurMillions(p.value)}, ${p.isEstimated ? "estimated" : "verified"}`}
                className="group pointer-events-auto absolute z-0 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-default outline-none focus:z-20 hover:z-20"
                style={{ left: `${leftPct}%`, top: `${topPct}%` }}
              >
                <div
                  className={`pointer-events-none absolute z-20 whitespace-nowrap rounded-lg border border-primary-100 bg-white px-2.5 py-1.5 text-xs opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 dark:border-primary-900 dark:bg-[#111a17] ${
                    topPct < 25 ? "top-full mt-2" : "bottom-full mb-2"
                  } left-1/2 -translate-x-1/2`}
                >
                  <div className="font-medium text-foreground">{p.season}</div>
                  <div className="mt-0.5 text-foreground/50">
                    {formatEurMillions(p.value)} · {p.isEstimated ? "estimated" : "verified"}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 font-sans text-[11px] text-foreground/50">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-primary-500" />
          Verified
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full border border-primary-500 bg-white dark:bg-[#111a17]" />
          Estimated
        </span>
      </div>
    </div>
  );
}
