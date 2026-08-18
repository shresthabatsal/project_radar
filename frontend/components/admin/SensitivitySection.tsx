"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { adminSensitivity, ApiError } from "@/lib/api";
import type { MetaResponse, SensitivityResponse, SensitivityScenario } from "@/lib/types";
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

function ScenarioTable({ title, scenarios }: { title: string; scenarios: SensitivityScenario[] }) {
  if (scenarios.length === 0) return null;
  return (
    <div>
      <h3 className={labelClass}>{title}</h3>
      <div className="mt-1.5 overflow-x-auto">
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Scenario</th>
              <th className={thClass}>Weights</th>
              <th className={thClass}>Spearman</th>
              <th className={thClass}>Top-N overlap</th>
              <th className={thClass}>Mean |Δ rank|</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.scenario}>
                <td className={tdClass}>{s.scenario}</td>
                <td className={`${tdClass} font-mono text-xs`}>
                  {Object.entries(s.weights)
                    .map(([k, v]) => `${k}=${v.toFixed(2)}`)
                    .join(", ")}
                </td>
                <td className={tdClass}>{s.spearman?.toFixed(4) ?? "—"}</td>
                <td className={tdClass}>{s.top_n_overlap_pct != null ? `${s.top_n_overlap_pct}%` : "—"}</td>
                <td className={tdClass}>{s.mean_abs_rank_change ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type SensitivitySectionProps = {
  token: string;
  meta: MetaResponse;
};

export function SensitivitySection({ token, meta }: SensitivitySectionProps) {
  const [season, setSeason] = useState(meta.seasons[0] ?? "");
  const [position, setPosition] = useState<(typeof POSITIONS)[number]>("MF");
  const [league, setLeague] = useState("");
  const [pct, setPct] = useState(0.2);
  const [topN, setTopN] = useState(10);
  const [minMinutes, setMinMinutes] = useState(450);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SensitivityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await adminSensitivity(token, {
        season,
        position,
        league: league || undefined,
        pct,
        top_n: topN,
        min_minutes: minMinutes,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sensitivity run failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={panelClass}>
      <h2 className={headingClass}>Weight Sensitivity</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Perturbs each composite/moneyball weight by ±{Math.round(pct * 100)}% and reports rank
        stability (Spearman correlation vs. the nominal ranking) for one season/position/league
        pool.
      </p>

      <div className="mt-4 flex flex-wrap gap-4">
        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Season</span>
          <select value={season} onChange={(e) => setSeason(e.target.value)} className={inputClass}>
            {meta.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Position</span>
          <select
            value={position}
            onChange={(e) => setPosition(e.target.value as (typeof POSITIONS)[number])}
            className={inputClass}
          >
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
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

        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Perturbation</span>
          <input
            type="number"
            step="0.05"
            min={0.05}
            max={0.5}
            value={pct}
            onChange={(e) => setPct(Number(e.target.value) || 0.2)}
            className={`${inputClass} w-24`}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Top N</span>
          <input
            type="number"
            min={1}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value) || 10)}
            className={`${inputClass} w-20`}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Min minutes</span>
          <input
            type="number"
            min={0}
            value={minMinutes}
            onChange={(e) => setMinMinutes(Number(e.target.value) || 0)}
            className={`${inputClass} w-24`}
          />
        </label>
      </div>

      <button type="button" onClick={handleRun} disabled={loading || !season} className={`mt-4 ${buttonClass}`}>
        {loading ? "Running…" : "Run sensitivity"}
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
            <RadarSweep label="Computing sensitivity" />
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
                Pool size {result.pool_size} &middot; min minutes {result.min_minutes} &middot; top{" "}
                {result.top_n}
              </p>
              <ScenarioTable title="Composite index" scenarios={result.composite_sensitivity} />
              <ScenarioTable title="Moneyball score" scenarios={result.moneyball_sensitivity} />
            </>
          )}
        </div>
      )}
    </section>
  );
}
