"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { adminBacktest, ApiError } from "@/lib/api";
import type { BacktestResponse, MetaResponse } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";
import {
  panelClass,
  headingClass,
  buttonClass,
  inputClass,
  labelClass,
  tableClass,
  thClass,
  tdClass,
  errorTextClass,
} from "./styles";

const POSITIONS = ["GK", "DF", "MF", "FW"] as const;

function formatCell(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}

function PooledTable({ pooled }: { pooled: Record<string, unknown> }) {
  const bucketNames = Object.keys(pooled);
  if (bucketNames.length === 0) return null;
  const columns: string[] = [];
  for (const name of bucketNames) {
    const bucket = pooled[name];
    if (bucket && typeof bucket === "object") {
      for (const k of Object.keys(bucket)) if (!columns.includes(k)) columns.push(k);
    }
  }
  return (
    <div className="overflow-x-auto">
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Bucket</th>
            {columns.map((c) => (
              <th key={c} className={thClass}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bucketNames.map((name) => {
            const bucket = (pooled[name] ?? {}) as Record<string, unknown>;
            return (
              <tr key={name}>
                <td className={tdClass}>{name}</td>
                {columns.map((c) => (
                  <td key={c} className={tdClass}>
                    {formatCell(bucket[c])}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RunsTable({ runs }: { runs: Record<string, unknown>[] }) {
  function bucketSummary(result: Record<string, unknown>, name: string): string {
    const bucket = (result[name] ?? {}) as Record<string, unknown>;
    if (bucket.n == null) return "—";
    const pct = bucket.pct_stayed_good;
    return `n=${bucket.n}${pct != null ? `, ${pct}% stayed good` : ""}`;
  }

  return (
    <div className="overflow-x-auto">
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Season</th>
            <th className={thClass}>Outcome</th>
            <th className={thClass}>Position</th>
            <th className={thClass}>Flagged</th>
            <th className={thClass}>Riser</th>
            <th className={thClass}>Flagged (non-riser)</th>
            <th className={thClass}>Baseline</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run, i) => {
            const result = (run.result ?? {}) as Record<string, unknown>;
            return (
              <tr key={i}>
                <td className={tdClass}>{formatCell(run.season)}</td>
                <td className={tdClass}>{formatCell(run.outcome_season)}</td>
                <td className={tdClass}>{formatCell(run.position)}</td>
                <td className={tdClass}>{formatCell(result.n_flagged_total)}</td>
                <td className={tdClass}>{bucketSummary(result, "riser")}</td>
                <td className={tdClass}>{bucketSummary(result, "flagged_non_riser")}</td>
                <td className={tdClass}>{bucketSummary(result, "baseline")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type BacktestSectionProps = {
  token: string;
  meta: MetaResponse;
};

export function BacktestSection({ token, meta }: BacktestSectionProps) {
  // meta.seasons[0] is the latest season - it has no "following season" to
  // backtest an outcome against yet, so it always errors. Default to the
  // one before it (still recent, but has a real outcome season) instead.
  const defaultSeason = meta.seasons[1] ?? meta.seasons[0];
  const [seasons, setSeasons] = useState<string[]>(defaultSeason ? [defaultSeason] : []);
  const [positions, setPositions] = useState<string[]>([]);
  const [horizon, setHorizon] = useState(1);
  const [league, setLeague] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await adminBacktest(token, {
        season: seasons.length ? seasons : undefined,
        position: positions.length ? positions : undefined,
        horizon,
        league: league || undefined,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={panelClass}>
      <h2 className={headingClass}>Backtest Hidden-Gem Detector</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        For each flagged season, checks how flagged players actually performed the following
        season vs. the baseline pool. Leaving everything unchecked tests every available
        season × position - slow.
      </p>

      <div className="mt-4 flex flex-col gap-4">
        <div>
          <span className={labelClass}>Seasons</span>
          <div className="mt-1.5 flex max-h-24 flex-wrap gap-x-4 gap-y-1.5 overflow-y-auto">
            {meta.seasons.map((s) => (
              <label key={s} className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={seasons.includes(s)}
                  onChange={() => toggle(seasons, setSeasons, s)}
                />
                {s}
              </label>
            ))}
          </div>
        </div>

        <div>
          <span className={labelClass}>Positions</span>
          <div className="mt-1.5 flex flex-wrap gap-4">
            {POSITIONS.map((p) => (
              <label key={p} className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={positions.includes(p)}
                  onChange={() => toggle(positions, setPositions, p)}
                />
                {p}
              </label>
            ))}
          </div>
          <p className={`mt-1 ${labelClass}`}>None checked = all four.</p>
        </div>

        <div className="flex flex-wrap gap-4">
          <label className="flex flex-col gap-1.5">
            <span className={labelClass}>Horizon (seasons ahead)</span>
            <input
              type="number"
              min={1}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value) || 1)}
              className={`${inputClass} w-28`}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className={labelClass}>League</span>
            <select value={league} onChange={(e) => setLeague(e.target.value)} className={inputClass}>
              <option value="">All leagues</option>
              {meta.leagues.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <button type="button" onClick={handleRun} disabled={loading} className={`mt-4 ${buttonClass}`}>
        {loading ? "Running…" : "Run backtest"}
      </button>

      <AnimatePresence mode="wait">
        {loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-6 flex justify-center py-8"
          >
            <RadarSweep label="Running backtest" />
          </motion.div>
        )}
      </AnimatePresence>

      {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}

      {result && !loading && (
        <div className="mt-5 flex flex-col gap-5">
          {result.error ? (
            <p className={errorTextClass}>{result.error}</p>
          ) : (
            <>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {result.n_runs} run{result.n_runs === 1 ? "" : "s"}
                {result.n_skipped ? `, ${result.n_skipped} skipped` : ""} across{" "}
                {result.seasons_tested.join(", ")} &middot; {result.positions_tested.join(", ")} &middot;
                horizon {result.horizon}
                {result.league ? ` · ${result.league}` : ""}
              </p>

              {Object.keys(result.pooled).length > 0 && (
                <div>
                  <h3 className={labelClass}>Pooled outcomes</h3>
                  <div className="mt-1.5">
                    <PooledTable pooled={result.pooled} />
                  </div>
                </div>
              )}

              {result.runs.length > 0 && (
                <div>
                  <h3 className={labelClass}>Per-run results</h3>
                  <div className="mt-1.5">
                    <RunsTable runs={result.runs as Record<string, unknown>[]} />
                  </div>
                </div>
              )}

              {result.skipped.length > 0 && (
                <div>
                  <h3 className={labelClass}>Skipped</h3>
                  <pre className="mt-1.5 max-h-40 overflow-auto rounded border border-gray-200 bg-gray-50 p-2 text-xs text-gray-600 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400">
                    {JSON.stringify(result.skipped, null, 2)}
                  </pre>
                </div>
              )}

              <details>
                <summary className="cursor-pointer text-sm text-gray-500 dark:text-gray-400">
                  Raw response
                </summary>
                <pre className="mt-1.5 max-h-80 overflow-auto rounded border border-gray-200 bg-gray-50 p-2 text-xs text-gray-600 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>
      )}
    </section>
  );
}
