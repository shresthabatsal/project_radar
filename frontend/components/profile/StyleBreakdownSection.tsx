"use client";

import { useCallback } from "react";
import { getPlayingStyle, getStyleArchetype } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import type { StyleHighlight } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";

/** ml.style_clustering nearest-archetype label + blurb - a natural
 * companion to the style-category breakdown below, not a standalone tab.
 * Renders nothing at all (not an empty state) when ineligible. */
function StyleArchetypeCard({ id }: { id: string }) {
  const fetcher = useCallback(() => getStyleArchetype(id), [id]);
  const { data, loading } = useAsyncData(fetcher, [fetcher]);

  if (loading) {
    return (
      <div className="flex min-h-[88px] items-center justify-center rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        <RadarSweep label="Finding style archetype" />
      </div>
    );
  }
  if (!data || !data.eligible || !data.label) return null;

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-primary-200 bg-primary-50/60 p-6 dark:border-primary-800 dark:bg-primary-950/40">
      <span className="font-sans text-xs font-semibold uppercase tracking-wide text-primary-600 dark:text-primary-400">
        Style Archetype
      </span>
      <span className="font-display text-xl font-semibold text-foreground">{data.label}</span>
      {data.blurb && <p className="font-sans text-sm leading-6 text-foreground/70">{data.blurb}</p>}
    </div>
  );
}

function HighlightCard({ highlight, tone }: { highlight: StyleHighlight; tone: "strength" | "weakness" }) {
  const toneClass =
    tone === "strength"
      ? "border-primary-200 bg-primary-50/60 dark:border-primary-800 dark:bg-primary-950/40"
      : "border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/20";
  const percentileClass =
    tone === "strength" ? "text-primary-600 dark:text-primary-400" : "text-amber-600 dark:text-amber-400";

  return (
    <div className={`flex flex-col gap-2 rounded-xl border p-4 ${toneClass}`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-sans text-sm font-medium text-foreground">{highlight.category}</span>
        <span className={`font-display text-lg font-semibold ${percentileClass}`}>
          {highlight.percentile.toFixed(0)}
          <span className="text-xs font-normal text-foreground/40">th pctl</span>
        </span>
      </div>
      <p className="font-sans text-sm leading-5 text-foreground/70">{highlight.text}</p>
      {highlight.drivers.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-2">
          {highlight.drivers.map((d) => (
            <span
              key={d.metric}
              className="rounded-full bg-white px-2.5 py-1 font-sans text-xs text-foreground/60 dark:bg-black/20"
            >
              {d.label}: <span className="font-medium text-foreground">{d.value}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function StyleBreakdownSection({ id }: { id: string }) {
  const fetcher = useCallback(() => getPlayingStyle(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load the playing-style breakdown.");

  return (
    <section className="flex flex-col gap-4">
      <StyleArchetypeCard id={id} />

      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">Strengths &amp; Weaknesses</h2>
        <p className="mt-1 font-sans text-sm text-foreground/60">
          The highest and lowest percentile categories, with the metrics driving each one - relative
          to this position&apos;s pool, not an absolute judgment.
        </p>
      </div>

      <div className="min-h-[200px] rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        {loading ? (
          <div className="flex min-h-[160px] items-center justify-center">
            <RadarSweep size="lg" label="Analyzing playing style" />
          </div>
        ) : error ? (
          <p className="text-center font-sans text-sm text-red-500">{error}</p>
        ) : !data || (data.strengths.length === 0 && data.weaknesses.length === 0) ? (
          <p className="text-center font-sans text-sm text-foreground/50">
            Not enough category data in this league for a style breakdown.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="flex flex-col gap-3">
              <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-primary-600 dark:text-primary-400">
                Strengths
              </h3>
              <div className="flex flex-col gap-3">
                {data.strengths.map((s) => (
                  <HighlightCard key={s.category} highlight={s} tone="strength" />
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <h3 className="font-sans text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                Weaknesses
              </h3>
              <div className="flex flex-col gap-3">
                {data.weaknesses.map((w) => (
                  <HighlightCard key={w.category} highlight={w} tone="weakness" />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
