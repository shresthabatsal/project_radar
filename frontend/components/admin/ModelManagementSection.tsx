"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { adminModelStatus, adminRetrainModel, ApiError, type AdminModelKey } from "@/lib/api";
import type { Json, MetaResponse, ModelStatus } from "@/lib/types";
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

type Rec = Record<string, unknown>;

function asRecord(v: unknown): Rec {
  return (v && typeof v === "object" ? (v as Rec) : {}) as Rec;
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function fmtNum(v: unknown, digits = 2): string {
  const n = num(v);
  return n == null ? "—" : n.toFixed(digits);
}

function fmtPct(v: unknown, digits = 1): string {
  const n = num(v);
  return n == null ? "—" : `${n.toFixed(digits)}%`;
}

function fmtEurBound(v: unknown): string {
  if (v == null) return "∞";
  const n = num(v);
  return n == null ? "—" : `€${(n / 1_000_000).toFixed(0)}M`;
}

function fmtInt(v: unknown): string {
  const n = num(v);
  return n == null ? "—" : n.toLocaleString();
}

// ---- Market Value -----------------------------------------------------

function MarketValueBody({ status }: { status: ModelStatus }) {
  const meta = asRecord(status.meta);
  const cfg = asRecord(status.config);
  const oof = asRecord(meta.oof_evaluation);
  const temporal = asRecord(meta.temporal_holdout_evaluation);
  const oofBrackets = asArray(oof.mdape_pct_by_bracket) as Rec[];
  const temporalBrackets = asArray(temporal.mdape_pct_by_bracket) as Rec[];
  const brackets = asArray(cfg.prior_mv_confidence_brackets);

  function findBracket(list: Rec[], lo: unknown): Rec | undefined {
    return list.find((b) => (b.anchor_mv_min ?? null) === (lo ?? null));
  }

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className={labelClass}>Rows / players</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">
            {fmtInt(meta.n)} / {fmtInt(meta.n_players)}
          </dd>
        </div>
        <div>
          <dt className={labelClass}>Overall MdAPE (GroupKFold)</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">{fmtPct(oof.mdape_pct)}</dd>
        </div>
        <div>
          <dt className={labelClass}>Overall MdAPE (temporal holdout)</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">
            {temporal.mdape_pct != null ? fmtPct(temporal.mdape_pct) : "skipped (too few seasons)"}
          </dd>
        </div>
        <div>
          <dt className={labelClass}>Directional accuracy (temporal)</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">
            {temporal.directional_accuracy_pct != null ? fmtPct(temporal.directional_accuracy_pct) : "—"}
          </dd>
        </div>
      </dl>

      {brackets.length > 1 && (
        <div>
          <h4 className={labelClass}>MdAPE by prior-value bracket</h4>
          <div className="mt-1.5 overflow-x-auto">
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Bracket</th>
                  <th className={thClass}>Tier</th>
                  <th className={thClass}>GroupKFold MdAPE</th>
                  <th className={thClass}>Temporal MdAPE</th>
                </tr>
              </thead>
              <tbody>
                {brackets.slice(0, -1).map((lo, i) => {
                  const hi = brackets[i + 1];
                  const o = findBracket(oofBrackets, lo);
                  const t = findBracket(temporalBrackets, lo);
                  if (!o && !t) return null;
                  return (
                    <tr key={String(lo)}>
                      <td className={tdClass}>
                        {fmtEurBound(lo)}–{fmtEurBound(hi)}
                      </td>
                      <td className={tdClass}>{String(o?.tier ?? t?.tier ?? "—")}</td>
                      <td className={tdClass}>{o ? `${fmtPct(o.mdape_pct)} (n=${fmtInt(o.n)})` : "—"}</td>
                      <td className={tdClass}>{t ? `${fmtPct(t.mdape_pct)} (n=${fmtInt(t.n)})` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h4 className={labelClass}>Confidence tier thresholds (in effect)</h4>
        <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">
          high &ge; {fmtInt(cfg.confidence_tier_high_min_n)} comparable rows, medium &ge;{" "}
          {fmtInt(cfg.confidence_tier_medium_min_n)}, else low.
        </p>
      </div>
    </div>
  );
}

// ---- Sell-High Risk -----------------------------------------------------

function SellHighRiskBody({ status }: { status: ModelStatus }) {
  const meta = asRecord(status.meta);
  const temporal = asRecord(meta.temporal_holdout);
  const gkf = asRecord(meta.groupkfold);
  const baselineLog = asRecord(meta.baseline_logistic_regression);
  const baselineMaj = asRecord(meta.baseline_majority_class);
  const thresholdInfo = asRecord(meta.decline_threshold_info);

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className={labelClass}>Rows / players</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">
            {fmtInt(meta.n)} / {fmtInt(meta.n_players)}
          </dd>
        </div>
        <div>
          <dt className={labelClass}>Positive rate</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">{fmtPct(num(meta.positive_rate) != null ? (meta.positive_rate as number) * 100 : null)}</dd>
        </div>
        <div>
          <dt className={labelClass}>Held-out years</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">{asArray(meta.held_out_years).join(", ") || "—"}</dd>
        </div>
        <div>
          <dt className={labelClass}>Decline quantile / threshold</dt>
          <dd className="text-sm text-gray-900 dark:text-gray-100">
            {fmtNum(thresholdInfo.decline_quantile)} (residual &le; {fmtNum(thresholdInfo.residual_threshold)})
          </dd>
        </div>
      </dl>

      <div className="overflow-x-auto">
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Evaluation</th>
              <th className={thClass}>ROC-AUC</th>
              <th className={thClass}>F1</th>
              <th className={thClass}>Precision</th>
              <th className={thClass}>Recall</th>
              <th className={thClass}>n</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className={tdClass}>Temporal holdout (primary)</td>
              <td className={tdClass}>{fmtNum(temporal.roc_auc, 3)}</td>
              <td className={tdClass}>{fmtNum(temporal.f1, 3)}</td>
              <td className={tdClass}>{fmtNum(temporal.precision, 3)}</td>
              <td className={tdClass}>{fmtNum(temporal.recall, 3)}</td>
              <td className={tdClass}>{fmtInt(temporal.n)}</td>
            </tr>
            <tr>
              <td className={tdClass}>GroupKFold(player)</td>
              <td className={tdClass}>{fmtNum(gkf.roc_auc, 3)}</td>
              <td className={tdClass}>{fmtNum(gkf.f1, 3)}</td>
              <td className={tdClass}>{fmtNum(gkf.precision, 3)}</td>
              <td className={tdClass}>{fmtNum(gkf.recall, 3)}</td>
              <td className={tdClass}>{fmtInt(gkf.n)}</td>
            </tr>
            <tr>
              <td className={tdClass}>Baseline: logistic regression (3-feature)</td>
              <td className={tdClass}>{fmtNum(baselineLog.roc_auc, 3)}</td>
              <td className={tdClass}>{fmtNum(baselineLog.f1, 3)}</td>
              <td className={tdClass}>{fmtNum(baselineLog.precision, 3)}</td>
              <td className={tdClass}>{fmtNum(baselineLog.recall, 3)}</td>
              <td className={tdClass}>{fmtInt(baselineLog.n)}</td>
            </tr>
            <tr>
              <td className={tdClass}>Baseline: majority class</td>
              <td className={tdClass} colSpan={4}>
                accuracy {fmtNum(baselineMaj.accuracy, 3)} - the floor any model must clear
              </td>
              <td className={tdClass}>—</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className={labelClass}>
        The model clears both baselines on the temporal holdout when ROC-AUC above is meaningfully
        higher than either baseline row's.
      </p>
    </div>
  );
}

// ---- Style Clustering -----------------------------------------------------

function StyleClusteringBody({ status }: { status: ModelStatus }) {
  const metaByPos = asRecord(status.meta);
  const cfgByPos = asRecord(status.config);
  const positions = Object.keys(metaByPos).length > 0 ? Object.keys(metaByPos) : Object.keys(cfgByPos);

  return (
    <div className="flex flex-col gap-5">
      {positions.map((pos) => {
        const posMeta = asRecord(metaByPos[pos]);
        const posCfg = asRecord(cfgByPos[pos]);
        const hasError = typeof posMeta.error === "string";
        const clusters = asArray(posMeta.clusters) as Rec[];
        const excluded = asArray(posCfg.excluded_categories) as string[];

        return (
          <div key={pos} className="rounded border border-gray-200 p-3 dark:border-gray-800">
            <h4 className="font-sans text-sm font-semibold text-gray-900 dark:text-gray-100">{pos}</h4>

            <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <dt className={labelClass}>Distance metric</dt>
                <dd className="text-sm text-gray-900 dark:text-gray-100">{String(posCfg.distance_metric ?? "—")}</dd>
              </div>
              <div>
                <dt className={labelClass}>Negative-weight dampening</dt>
                <dd className="text-sm text-gray-900 dark:text-gray-100">
                  {posCfg.negative_weight != null ? fmtNum(posCfg.negative_weight, 2) : "none"}
                </dd>
              </div>
              <div>
                <dt className={labelClass}>K override</dt>
                <dd className="text-sm text-gray-900 dark:text-gray-100">
                  {posCfg.k_override != null ? `K=${posCfg.k_override} (forced)` : "none - silhouette argmax"}
                </dd>
              </div>
              <div>
                <dt className={labelClass}>Excluded categories</dt>
                <dd className="text-sm text-gray-900 dark:text-gray-100">
                  {excluded.length ? excluded.join("; ") : "none"}
                </dd>
              </div>
            </dl>

            {hasError ? (
              <p className={`mt-2 ${errorTextClass}`}>{String(posMeta.error)}</p>
            ) : Object.keys(posMeta).length === 0 ? (
              <p className={`mt-2 ${labelClass}`}>Not trained yet.</p>
            ) : (
              <>
                <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <dt className={labelClass}>K in use</dt>
                    <dd className="text-sm text-gray-900 dark:text-gray-100">
                      {fmtInt(posMeta.k)} ({String(posMeta.k_selection ?? "").startsWith("manual") ? "manual override" : "silhouette argmax"})
                    </dd>
                  </div>
                  <div>
                    <dt className={labelClass}>Silhouette (chosen K)</dt>
                    <dd className="text-sm text-gray-900 dark:text-gray-100">{fmtNum(posMeta.silhouette, 4)}</dd>
                  </div>
                  <div>
                    <dt className={labelClass}>Rows / players</dt>
                    <dd className="text-sm text-gray-900 dark:text-gray-100">
                      {fmtInt(posMeta.n)} / {fmtInt(posMeta.n_players)}
                    </dd>
                  </div>
                </dl>

                {clusters.length > 0 && (
                  <div className="mt-3 overflow-x-auto">
                    <table className={tableClass}>
                      <thead>
                        <tr>
                          <th className={thClass}>Cluster</th>
                          <th className={thClass}>Label</th>
                          <th className={thClass}>Size</th>
                        </tr>
                      </thead>
                      <tbody>
                        {clusters.map((c) => (
                          <tr key={String(c.cluster)}>
                            <td className={tdClass}>{fmtInt(c.cluster)}</td>
                            <td className={tdClass}>{String(c.label ?? "—")}</td>
                            <td className={tdClass}>{fmtInt(c.size)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---- Shared card shell -----------------------------------------------------

type ModelCardProps = {
  status: ModelStatus;
  token: string;
  modelKey: AdminModelKey;
  description: string;
  seasons: string[];
  extraFields?: (
    values: { minMinutes: string; kMin: string; kMax: string },
    setValues: (v: { minMinutes: string; kMin: string; kMax: string }) => void,
  ) => React.ReactNode;
  onUpdated: (meta: Json) => void;
  children: React.ReactNode;
};

function ModelCard({ status, token, modelKey, description, seasons, extraFields, onUpdated, children }: ModelCardProps) {
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
  const [advanced, setAdvanced] = useState({ minMinutes: "", kMin: "", kMax: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleSeason(s: string) {
    setSelectedSeasons((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  async function handleRetrain() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminRetrainModel(token, modelKey, {
        seasons: selectedSeasons.length ? selectedSeasons : undefined,
        min_minutes: advanced.minMinutes.trim() ? Number(advanced.minMinutes) : undefined,
        k_min: advanced.kMin.trim() ? Number(advanced.kMin) : undefined,
        k_max: advanced.kMax.trim() ? Number(advanced.kMax) : undefined,
      });
      if (res.error) {
        setError(res.error);
      }
      // Even on a partial error (e.g. style-clustering: one position group
      // failed but others trained), the response's own per-key meta is the
      // freshest truth - always fold it in, same as a full success.
      onUpdated(res.meta);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Retrain failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-gray-300 p-4 dark:border-gray-700">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-sans text-sm font-semibold text-gray-900 dark:text-gray-100">{status.label}</h3>
        <span className={labelClass}>{status.trained ? "Trained" : "Not trained yet"}</span>
      </div>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>

      <div className="mt-3">{children}</div>

      <div className="mt-4 border-t border-gray-200 pt-3 dark:border-gray-800">
        <span className={labelClass}>Seasons to retrain on</span>
        <div className="mt-1.5 flex max-h-20 flex-wrap gap-x-4 gap-y-1.5 overflow-y-auto">
          {seasons.slice(0, 12).map((s) => (
            <label key={s} className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
              <input type="checkbox" checked={selectedSeasons.includes(s)} onChange={() => toggleSeason(s)} />
              {s}
            </label>
          ))}
        </div>
        <p className={`mt-1 ${labelClass}`}>None selected = this model&apos;s own default (see its retrain script).</p>

        {extraFields && (
          <div className="mt-2 flex flex-wrap gap-3">{extraFields(advanced, setAdvanced)}</div>
        )}

        <button type="button" onClick={handleRetrain} disabled={loading} className={`mt-3 ${buttonClass}`}>
          {loading ? "Retraining…" : "Retrain now"}
        </button>

        <AnimatePresence mode="wait">
          {loading && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="mt-4 flex justify-center py-6"
            >
              <RadarSweep label="Training model" />
            </motion.div>
          )}
        </AnimatePresence>

        {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}
      </div>
    </div>
  );
}

// ---- Top-level section -----------------------------------------------------

type ModelManagementSectionProps = {
  token: string;
  meta: MetaResponse;
};

export function ModelManagementSection({ token, meta }: ModelManagementSectionProps) {
  const [models, setModels] = useState<ModelStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await adminModelStatus(token);
      setModels(res.models);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load model status.");
    }
  }, [token]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  function updateModel(key: string, newMeta: Json) {
    setModels((prev) =>
      prev
        ? prev.map((m) => (m.key === key ? { ...m, trained: Object.keys(newMeta).length > 0, meta: newMeta } : m))
        : prev,
    );
  }

  const byKey = (key: string) => models?.find((m) => m.key === key);

  return (
    <section className={panelClass}>
      <h2 className={headingClass}>Model Management</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Every model this app currently trains, its last training run&apos;s real evaluation metrics
        (read straight from that model&apos;s own meta.json - nothing recomputed here), and a
        per-model retrain control. Retraining reloads the fresh artifact into this running
        server&apos;s memory immediately - no restart needed.
      </p>

      {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}

      {!models && !error ? (
        <div className="mt-6 flex justify-center py-8">
          <RadarSweep label="Loading model status" />
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          {byKey("market_value") && (
            <ModelCard
              status={byKey("market_value") as ModelStatus}
              token={token}
              modelKey="market-value"
              description="Gradient-boosted regressor predicting log(current_mv / prior_mv), reconstructed to a euro figure against a real prior-season value. See MARKET_VALUE_MODEL_PROCESS.md."
              seasons={meta.seasons}
              onUpdated={(m) => updateModel("market_value", m)}
            >
              <MarketValueBody status={byKey("market_value") as ModelStatus} />
            </ModelCard>
          )}

          {byKey("sell_high_risk") && (
            <ModelCard
              status={byKey("sell_high_risk") as ModelStatus}
              token={token}
              modelKey="sell-high-risk"
              description="Gradient-boosted classifier predicting P(significant on-field deterioration next season) for players at/near a real career-peak market value. See SELL_HIGH_RISK_MODEL_PROCESS.md."
              seasons={meta.seasons}
              onUpdated={(m) => updateModel("sell_high_risk", m)}
            >
              <SellHighRiskBody status={byKey("sell_high_risk") as ModelStatus} />
            </ModelCard>
          )}

          {byKey("style_clustering") && (
            <ModelCard
              status={byKey("style_clustering") as ModelStatus}
              token={token}
              modelKey="style-clustering"
              description="One K-means per broad position group (FW/MF/DF - GK is never clustered), assigning each player a style archetype. See STYLE_CLUSTERING_PROCESS.md."
              seasons={meta.seasons}
              extraFields={(values, setValues) => (
                <>
                  <label className="flex flex-col gap-1">
                    <span className={labelClass}>Min minutes (optional)</span>
                    <input
                      type="number"
                      value={values.minMinutes}
                      onChange={(e) => setValues({ ...values, minMinutes: e.target.value })}
                      className={`${inputClass} w-32`}
                      placeholder="default"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className={labelClass}>K min (optional)</span>
                    <input
                      type="number"
                      value={values.kMin}
                      onChange={(e) => setValues({ ...values, kMin: e.target.value })}
                      className={`${inputClass} w-24`}
                      placeholder="default"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className={labelClass}>K max (optional)</span>
                    <input
                      type="number"
                      value={values.kMax}
                      onChange={(e) => setValues({ ...values, kMax: e.target.value })}
                      className={`${inputClass} w-24`}
                      placeholder="default"
                    />
                  </label>
                </>
              )}
              onUpdated={(m) => updateModel("style_clustering", m)}
            >
              <StyleClusteringBody status={byKey("style_clustering") as ModelStatus} />
            </ModelCard>
          )}
        </div>
      )}
    </section>
  );
}
