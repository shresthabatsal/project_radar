"use client";

import { useCallback } from "react";
import { getMarketValue } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { CountUp } from "@/components/CountUp";
import { FeatureImportanceBars } from "@/components/FeatureImportanceBars";
import { MarketValueHistoryChart } from "@/components/profile/MarketValueHistoryChart";

function formatEurMillions(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${(n / 1_000).toFixed(0)}K`;
  return `€${n.toFixed(0)}`;
}

const METHOD_BADGE: Record<string, string> = {
  verified: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  gbm: "bg-primary-100 text-primary-700 dark:bg-primary-950 dark:text-primary-300",
  // Distinct from plain "heuristic" (no model trained at all) - this is a
  // model that IS trained but has no valid prior-season value to anchor on
  // for this specific player-season, so it isn't the model's own estimate.
  heuristic_fallback: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  heuristic: "bg-foreground/10 text-foreground/60",
};

const GAP_COLOR = (pct: number) =>
  pct > 0 ? "text-green-600 dark:text-green-400" : pct < 0 ? "text-red-600 dark:text-red-400" : "text-foreground/50";

const CONFIDENCE_BADGE: Record<string, string> = {
  high: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

function CardShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold text-foreground">{title}</h2>
      <div className="rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
        {children}
      </div>
    </section>
  );
}

/** A single valuation model: "Market Value" (a verified real value when on
 * file, else the trained GBM's own prediction with its feature-importance
 * breakdown, else a heuristic fallback), the model's own estimate compared
 * against the observed value when both exist ("what does the model think
 * this player is worth, vs. what the market says" - a recruitment signal,
 * not a correction to either number), and this player's real value history
 * as a chart with nothing projected on it. No separate trend-forecast card -
 * this endpoint answers exactly one question now. */
export function MarketValueSection({ id }: { id: string }) {
  const fetcher = useCallback(() => getMarketValue(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load market value.");

  if (loading) {
    return (
      <CardShell title="Market Value">
        <div className="flex min-h-[160px] items-center justify-center">
          <RadarSweep label="Predicting market value" />
        </div>
      </CardShell>
    );
  }

  if (error || !data) {
    return (
      <CardShell title="Market Value">
        <div className="flex min-h-[160px] items-center justify-center text-center font-sans text-sm text-red-500">
          {error ?? "No data."}
        </div>
      </CardShell>
    );
  }

  const hasGap = data.valuation_diff_pct != null && data.valuation_diff_eur != null;

  return (
    <CardShell title="Market Value">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="font-sans text-xs text-foreground/50">Current value</span>
          <p className="font-display text-4xl font-semibold text-foreground">
            {data.current_value_label ?? "—"}
          </p>
        </div>
        {data.method_label && (
          <span
            className={`rounded-full px-3 py-1 font-sans text-xs font-medium ${
              METHOD_BADGE[data.method ?? ""] ?? "bg-foreground/10 text-foreground/60"
            }`}
          >
            {data.method_label}
          </span>
        )}
      </div>

      {data.ml_model_trained ? (
        <div className="mt-6 grid grid-cols-1 gap-6 border-t border-primary-100 pt-6 dark:border-primary-900 lg:grid-cols-2">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-sans text-xs font-medium uppercase tracking-wide text-foreground/50">
                Model Valuation
              </span>
              {data.ml_prediction_confidence && (
                <span
                  className={`rounded-full px-2 py-0.5 font-sans text-[11px] font-medium ${
                    CONFIDENCE_BADGE[data.ml_prediction_confidence] ?? "bg-foreground/10 text-foreground/60"
                  }`}
                >
                  {CONFIDENCE_LABEL[data.ml_prediction_confidence] ?? data.ml_prediction_confidence} confidence
                </span>
              )}
            </div>
            {data.ml_prediction != null ? (
              <CountUp
                value={data.ml_prediction}
                format={formatEurMillions}
                className="mt-1 block font-display text-3xl font-semibold text-primary-600 dark:text-primary-400"
              />
            ) : (
              <p className="mt-1 font-display text-lg text-foreground/40">Not enough data</p>
            )}
            <p className="mt-1 font-sans text-xs text-foreground/40">
              What the model thinks this player is worth, from performance and bio features alone -
              independent of the observed market value.
            </p>
            {data.ml_prediction_confidence_note && (
              <p className="mt-2 font-sans text-xs text-foreground/50">
                {data.ml_prediction_confidence_note}
              </p>
            )}
          </div>
          <div>
            <span className="mb-2 block font-sans text-xs font-medium uppercase tracking-wide text-foreground/50">
              What drives this valuation
            </span>
            {data.top_contributors.length > 0 ? (
              <FeatureImportanceBars contributors={data.top_contributors} />
            ) : (
              <p className="font-sans text-sm text-foreground/40">No contributor breakdown available.</p>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-4 font-sans text-xs text-foreground/40">
          No trained model artifact yet - showing the heuristic estimate only.
        </p>
      )}

      {hasGap && (
        <div className="mt-6 border-t border-primary-100 pt-6 dark:border-primary-900">
          <span className="font-sans text-xs font-medium uppercase tracking-wide text-foreground/50">
            Valuation Gap
          </span>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 font-sans text-sm sm:grid-cols-4">
            <div>
              <div className="text-xs text-foreground/50">Actual market value</div>
              <div className="font-medium text-foreground">{data.current_value_label}</div>
            </div>
            <div>
              <div className="text-xs text-foreground/50">Model valuation</div>
              <div className="font-medium text-foreground">{data.ml_prediction_label}</div>
            </div>
            <div>
              <div className="text-xs text-foreground/50">Difference</div>
              <div className={`font-medium ${GAP_COLOR(data.valuation_diff_pct as number)}`}>
                {data.valuation_diff_label}
              </div>
            </div>
            <div>
              <div className="text-xs text-foreground/50">Gap</div>
              <div className={`font-medium ${GAP_COLOR(data.valuation_diff_pct as number)}`}>
                {(data.valuation_diff_pct as number) > 0 ? "+" : ""}
                {(data.valuation_diff_pct as number).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {data.trajectory.length > 0 && (
        <div className="mt-6 border-t border-primary-100 pt-6 dark:border-primary-900">
          <span className="mb-2 block font-sans text-xs font-medium uppercase tracking-wide text-foreground/50">
            Value History
          </span>
          <MarketValueHistoryChart trajectory={data.trajectory} />
        </div>
      )}
    </CardShell>
  );
}
