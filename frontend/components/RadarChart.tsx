"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { CategoryScore } from "@/lib/types";

const MAX_VALUE = 100;
const GRID_FRACTIONS = [0.25, 0.5, 0.75, 1];

/** An additional named polygon layered on the same axes as the player's own
 * (e.g. league average, league best) - deliberately NOT distinguished by
 * color alone: each overlay also gets its own dash pattern and no fill, so
 * it reads as a reference line rather than another player's data. `labelHref`
 * is optional - only overlays that name a real player (e.g. "league best")
 * link their legend label to that player's profile; a flat reference like
 * "league average" has no player to link to. `pointTitles` is optional
 * per-category hover text for each vertex - e.g. a "best per category"
 * overlay is a composite across potentially many different real players, so
 * unlike `labelHref` there's no single player to name in the legend; hovering
 * each point instead shows who leads THAT specific category. */
export type RadarOverlay = {
  key: string;
  label: string;
  labelHref?: string;
  scores: Record<string, number>;
  pointTitles?: Record<string, string>;
  colorClassName: string;
  dashArray?: string;
};

type RadarChartProps = {
  categories: CategoryScore[];
  size?: number;
  className?: string;
  overlays?: RadarOverlay[];
  primaryLabel?: string;
};

/** Player style-category radar - the shape draws in from the center on
 * mount (a thematic nod to the product name), rather than appearing
 * instantly. Categories with no measurable data are already omitted
 * upstream (see PlayerProfileResponse.radar), so every axis here is real. */
export function RadarChart({ categories, size = 400, className, overlays = [], primaryLabel = "You" }: RadarChartProps) {
  const data = categories.filter(
    (c): c is { category: string; score: number } => c.score != null,
  );
  const n = data.length;

  if (n < 3) {
    return (
      <div className="flex items-center justify-center py-12 text-center font-sans text-sm text-foreground/50">
        Not enough category data in this league for a radar chart.
      </div>
    );
  }

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 72;
  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2;

  const angleFor = (i: number) => startAngle + i * angleStep;
  const pointFor = (i: number, fraction: number): [number, number] => {
    const angle = angleFor(i);
    const r = radius * fraction;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  };

  const dataPoints = data.map((d, i) => pointFor(i, Math.max(0, Math.min(1, d.score / MAX_VALUE))));
  const dataPolygon = dataPoints.map((p) => p.join(",")).join(" ");

  const overlayPolygons = overlays.map((ov) => {
    const vertices = data.map((d, i) => {
      const [x, y] = pointFor(i, Math.max(0, Math.min(1, (ov.scores[d.category] ?? 0) / MAX_VALUE)));
      return { x, y, category: d.category };
    });
    return {
      ...ov,
      points: vertices.map((v) => `${v.x},${v.y}`).join(" "),
      vertices,
    };
  });

  return (
    <div className={`flex flex-col items-center gap-4 ${className ?? ""}`}>
      <div className="relative mx-auto" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="absolute inset-0 overflow-visible">
          {GRID_FRACTIONS.map((f) => (
            <polygon
              key={f}
              points={data.map((_, i) => pointFor(i, f).join(",")).join(" ")}
              className="fill-none stroke-primary-100 dark:stroke-primary-900"
              strokeWidth={1}
            />
          ))}

          {data.map((_, i) => {
            const [x, y] = pointFor(i, 1);
            return (
              <line
                key={i}
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                className="stroke-primary-100 dark:stroke-primary-900"
                strokeWidth={1}
              />
            );
          })}

          {overlayPolygons.map((ov) => (
            <polygon
              key={ov.key}
              points={ov.points}
              className={`fill-none ${ov.colorClassName}`}
              strokeWidth={2}
              strokeDasharray={ov.dashArray}
              strokeLinejoin="round"
            />
          ))}

          {overlayPolygons.map((ov) =>
            ov.pointTitles
              ? ov.vertices.map((v) => (
                  <circle
                    key={`${ov.key}-${v.category}`}
                    cx={v.x}
                    cy={v.y}
                    r={3.5}
                    strokeWidth={2}
                    className={`fill-white dark:fill-[#111a17] ${ov.colorClassName}`}
                  >
                    {ov.pointTitles?.[v.category] && <title>{ov.pointTitles[v.category]}</title>}
                  </circle>
                ))
              : null,
          )}

          <motion.g
            style={{ transformOrigin: `${cx}px ${cy}px` }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          >
            <polygon
              points={dataPolygon}
              className="fill-primary-500/25 stroke-primary-500"
              strokeWidth={2}
              strokeLinejoin="round"
            />
            {dataPoints.map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={3} className="fill-primary-600 dark:fill-primary-400" />
            ))}
          </motion.g>
        </svg>

        {data.map((d, i) => {
          const angle = angleFor(i);
          const labelR = radius + 38;
          const x = cx + labelR * Math.cos(angle);
          const y = cy + labelR * Math.sin(angle);
          const cos = Math.cos(angle);
          const align = cos > 0.3 ? "left" : cos < -0.3 ? "right" : "center";
          return (
            <div
              key={d.category}
              className="absolute w-24 -translate-x-1/2 -translate-y-1/2 font-sans text-[10px] leading-tight text-foreground/60"
              style={{ left: `${(x / size) * 100}%`, top: `${(y / size) * 100}%`, textAlign: align }}
            >
              {d.category}
              <div className="font-semibold text-primary-600 dark:text-primary-400">{d.score.toFixed(0)}</div>
            </div>
          );
        })}
      </div>

      {overlays.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-sans text-xs text-foreground/60">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-primary-500" />
            {primaryLabel}
          </span>
          {overlays.map((ov) => (
            <span key={ov.key} className="flex items-center gap-1.5">
              <svg width="14" height="8" className="shrink-0" aria-hidden="true">
                <line
                  x1={0}
                  y1={4}
                  x2={14}
                  y2={4}
                  strokeWidth={2}
                  className={ov.colorClassName}
                  strokeDasharray={ov.dashArray}
                />
              </svg>
              {ov.labelHref ? (
                <Link href={ov.labelHref} className="hover:text-primary-600 hover:underline dark:hover:text-primary-400">
                  {ov.label}
                </Link>
              ) : (
                ov.label
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
