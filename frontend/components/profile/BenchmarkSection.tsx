"use client";

import { useCallback, useMemo } from "react";
import Link from "next/link";
import { getPositionBenchmark } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import type { CategoryScore } from "@/lib/types";
import type { RadarOverlay } from "@/components/RadarChart";
import { RadarChart } from "@/components/RadarChart";
import { RadarSweep } from "@/components/RadarSweep";

export function BenchmarkSection({ id, radar }: { id: string; radar: CategoryScore[] }) {
  const fetcher = useCallback(() => getPositionBenchmark(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load the league benchmark.");

  const overlays: RadarOverlay[] = useMemo(() => {
    if (!data) return [];
    const list: RadarOverlay[] = [
      {
        key: "league-average",
        label: "League Average",
        scores: Object.fromEntries(radar.map((c) => [c.category, data.league_average])),
        colorClassName: "stroke-foreground/40",
        dashArray: "5 5",
      },
    ];
    if (data.category_leaders.length > 0) {
      // Each point is that category's OWN league leader, independently -
      // not one player's full radar. A pure poacher can lead Finishing
      // without also leading Defensive Work; this overlay is a composite
      // across however many different real players that takes.
      list.push({
        key: "category-best",
        label: "Best per Category",
        scores: Object.fromEntries(data.category_leaders.map((c) => [c.category, c.score])),
        pointTitles: Object.fromEntries(
          data.category_leaders.map((c) => [c.category, `${c.category}: ${c.score.toFixed(1)} - ${c.player}`]),
        ),
        colorClassName: "stroke-amber-500",
        dashArray: "1 4",
      });
    }
    return list;
  }, [data, radar]);

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-foreground">Radar vs. the League</h2>
          <p className="mt-1 font-sans text-sm text-foreground/60">
            Your style-category radar layered against the flat league average and, category by
            category, whoever leads THAT category in this pool - so the &quot;Best per Category&quot;
            shape is a composite of potentially many different players, not any one player&apos;s own
            radar. Hover a point on it to see who leads that category.
          </p>
        </div>

        <div className="flex min-h-[440px] items-center justify-center rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
          {loading ? (
            <RadarSweep size="lg" label="Loading benchmark" />
          ) : error ? (
            <p className="text-center font-sans text-sm text-red-500">{error}</p>
          ) : (
            <RadarChart categories={radar} overlays={overlays} size={420} />
          )}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-foreground">Vs. the League&apos;s Best</h2>
          <p className="mt-1 font-sans text-sm text-foreground/60">
            {data
              ? `Headline per-90 metrics against the top holder in this ${data.season} ${data.position} pool (${data.sample_size.toLocaleString()} players).`
              : "Headline per-90 metrics against this pool's leader."}
          </p>
        </div>

        <div className="min-h-[160px] rounded-2xl border border-primary-100 bg-white dark:border-primary-900 dark:bg-[#111a17]">
          {loading ? (
            <div className="flex min-h-[160px] items-center justify-center py-12">
              <RadarSweep label="Loading leaders" />
            </div>
          ) : error ? (
            <div className="flex min-h-[160px] items-center justify-center px-6 text-center font-sans text-sm text-red-500">
              {error}
            </div>
          ) : !data || data.metric_leaders.length === 0 ? (
            <div className="flex min-h-[160px] items-center justify-center px-6 text-center font-sans text-sm text-foreground/50">
              No headline metrics available for this position.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] border-collapse font-sans text-sm">
                <thead>
                  <tr className="border-b border-primary-100 text-left text-xs text-foreground/50 dark:border-primary-900">
                    <th className="px-4 py-3 font-medium">Metric</th>
                    <th className="px-4 py-3 font-medium text-right">You</th>
                    <th className="px-4 py-3 font-medium text-right">League Best</th>
                  </tr>
                </thead>
                <tbody>
                  {data.metric_leaders.map((m) => (
                    <tr key={m.metric} className="border-b border-primary-50 dark:border-primary-950">
                      <td className="px-4 py-3 text-foreground/70">{m.metric}</td>
                      <td className="px-4 py-3 text-right font-medium text-foreground">
                        {m.player_value != null ? m.player_value.toFixed(2) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {m.best_player_id ? (
                          <Link
                            href={`/players/${m.best_player_id}`}
                            className="text-xs text-foreground/50 hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                          >
                            {m.best_player}
                          </Link>
                        ) : (
                          <span className="text-xs text-foreground/50">{m.best_player}</span>
                        )}
                        <span className="ml-2 font-semibold text-amber-600 dark:text-amber-400">{m.best_value.toFixed(2)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
