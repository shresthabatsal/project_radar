"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import {
  getMeta,
  getSimilarityMethods,
  getSimilarPlayers,
  type ContractStatus,
  type SimilarityMethod,
  type SimilarPlayersSort,
} from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import type { MetaResponse, SimilarPlayerMatch } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";
import { GemBadge } from "@/components/GemBadge";
import { RawCompareModal } from "@/components/profile/RawCompareModal";
import { listContainer, listItem } from "@/lib/motion";

const PAGE_SIZE = 10;

// Fallback labels so the method <select> isn't empty for the one render
// before GET /similarity-methods resolves - that endpoint is the source of truth for reasoning copy.
const METHOD_FALLBACK_LABELS: Record<SimilarityMethod, string> = {
  mahalanobis: "Mahalanobis (default)",
  cosine: "Cosine",
  euclidean: "Euclidean",
  manhattan: "Manhattan",
};
const METHOD_ORDER: SimilarityMethod[] = ["mahalanobis", "cosine", "euclidean", "manhattan"];

const inputClass =
  "rounded-lg border border-primary-100 bg-white px-3 py-2 font-sans text-sm text-foreground outline-none ring-primary-400 transition focus:ring-2 dark:border-primary-900 dark:bg-[#111a17]";

// Maps onto GET /players/{id}/similar's `window` param (1-5 seasons,
// minutes-weighted blend). "Last 3-5 seasons" maps to the top of that
// range (5), same as the engine's own cap.
type SeasonWindow = 1 | 2 | 5;

interface FilterState {
  window: SeasonWindow;
  league: string;
  team: string;
  ageMin: string;
  ageMax: string;
  minutesMin: string;
  minutesMax: string;
  contractStatus: "" | ContractStatus;
  // ml.style_clustering archetype label - an exact match against one of
  // this query's own archetype_options (already scoped to the target's position group, server-side).
  archetype: string;
}

const EMPTY_FILTERS: FilterState = {
  window: 1,
  league: "",
  team: "",
  ageMin: "",
  ageMax: "",
  minutesMin: "",
  minutesMax: "",
  contractStatus: "",
  archetype: "",
};

function num(s: string): number | undefined {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-sans text-xs font-medium text-foreground/60">{label}</span>
      {children}
    </label>
  );
}

function RangeField({
  label,
  min,
  max,
  onMinChange,
  onMaxChange,
}: {
  label: string;
  min: string;
  max: string;
  onMinChange: (v: string) => void;
  onMaxChange: (v: string) => void;
}) {
  return (
    <Field label={label}>
      <div className="flex items-center gap-2">
        <input
          type="number"
          inputMode="decimal"
          placeholder="Min"
          value={min}
          onChange={(e) => onMinChange(e.target.value)}
          className={`${inputClass} w-full`}
        />
        <span className="text-foreground/30">–</span>
        <input
          type="number"
          inputMode="decimal"
          placeholder="Max"
          value={max}
          onChange={(e) => onMaxChange(e.target.value)}
          className={`${inputClass} w-full`}
        />
      </div>
    </Field>
  );
}

export function SimilaritySection({ id }: { id: string }) {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [draftFilters, setDraftFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SimilarPlayersSort>("match_score");
  const [method, setMethod] = useState<SimilarityMethod>("mahalanobis");
  const [page, setPage] = useState(1);
  const [compareCandidate, setCompareCandidate] = useState<SimilarPlayerMatch | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMeta()
      .then((res) => {
        if (!cancelled) setMeta(res);
      })
      .catch(() => {
        // League filter just falls back to "All leagues" only - not fatal.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Static, season/player-independent - the method picker's reasoning
  // copy, sourced from the backend so it can't drift. Fetched once; a
  // failure just falls back to METHOD_FALLBACK_LABELS, not fatal.
  const methodsFetcher = useCallback(() => getSimilarityMethods(), []);
  const { data: methodsData } = useAsyncData(methodsFetcher, [methodsFetcher]);

  const fetcher = useCallback(
    () =>
      getSimilarPlayers(id, {
        page,
        page_size: PAGE_SIZE,
        sort,
        method,
        window: appliedFilters.window,
        league: appliedFilters.league || undefined,
        team: appliedFilters.team || undefined,
        age_min: num(appliedFilters.ageMin),
        age_max: num(appliedFilters.ageMax),
        minutes_min: num(appliedFilters.minutesMin),
        minutes_max: num(appliedFilters.minutesMax),
        contract_status: appliedFilters.contractStatus || undefined,
        archetype: appliedFilters.archetype || undefined,
      }),
    [id, page, sort, method, appliedFilters],
  );
  const { data: result, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load similar players.");
  const data = result?.similar ?? null;
  const total = result?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // ml.style_clustering archetypes for the target's own position group -
  // already scoped server-side, no extra fetch needed. Deduped by label,
  // since the filter matches by label text.
  const archetypeOptions = Array.from(
    new Map((result?.archetype_options ?? []).map((a) => [a.label, a] as const)).values(),
  );

  function applyFilters() {
    setAppliedFilters(draftFilters);
    setPage(1);
  }

  function clearFilters() {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  }

  function handleSortChange(next: SimilarPlayersSort) {
    setSort(next);
    setPage(1);
  }

  function handleMethodChange(next: SimilarityMethod) {
    setMethod(next);
    setPage(1);
  }

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">Similar Players</h2>
        <p className="mt-1 font-sans text-sm text-foreground/60">
          Closest statistical matches over the position&apos;s full raw per-90 metric set - a
          shortlist starting point, not a verdict.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          applyFilters();
        }}
        className="flex flex-col gap-5 rounded-2xl border border-primary-100 bg-white p-5 dark:border-primary-900 dark:bg-[#111a17]"
      >
        {/* Distance method - wired to apply instantly on change like
            Sort, not gated behind Apply Filters: switching method changes
            what "closest" means. A radio group so every option's reasoning is visible at once. */}
        <fieldset className="flex flex-col gap-3">
          <legend className="font-sans text-xs font-medium text-foreground/60">Similarity method</legend>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {METHOD_ORDER.map((key) => {
              const info = methodsData?.methods.find((m) => m.key === key);
              const isDefault = key === (methodsData?.default ?? "mahalanobis");
              const isActive = method === key;
              return (
                <label
                  key={key}
                  className={`flex cursor-pointer flex-col gap-1 rounded-xl border p-3 transition ${
                    isActive
                      ? "border-primary-400 bg-primary-50 dark:border-primary-600 dark:bg-primary-950"
                      : "border-primary-100 hover:bg-primary-50/60 dark:border-primary-900 dark:hover:bg-primary-950/40"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="similarity-method"
                      value={key}
                      checked={isActive}
                      onChange={() => handleMethodChange(key)}
                      className="h-4 w-4 accent-primary-500"
                    />
                    <span className="font-sans text-sm font-semibold text-foreground">
                      {info?.label ?? METHOD_FALLBACK_LABELS[key]}
                    </span>
                    {isDefault && (
                      <span className="rounded-full bg-primary-500 px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-wide text-white">
                        Recommended default
                      </span>
                    )}
                  </span>
                  {info && (
                    <span className="pl-6 font-sans text-xs leading-5 text-foreground/60">
                      {info.description}{" "}
                      <span className="text-foreground/45">Best for: {info.best_for}</span>
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Season Window">
            <select
              value={draftFilters.window}
              onChange={(e) =>
                setDraftFilters({ ...draftFilters, window: Number(e.target.value) as SeasonWindow })
              }
              className={inputClass}
            >
              <option value={1}>Current season</option>
              <option value={2}>Last 2 seasons (avg)</option>
              <option value={5}>Last 3-5 seasons (avg)</option>
            </select>
          </Field>

          <Field label="League">
            <select
              value={draftFilters.league}
              onChange={(e) => setDraftFilters({ ...draftFilters, league: e.target.value })}
              className={inputClass}
            >
              <option value="">All leagues</option>
              {(meta?.leagues ?? []).map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Team">
            <input
              type="text"
              value={draftFilters.team}
              onChange={(e) => setDraftFilters({ ...draftFilters, team: e.target.value })}
              placeholder="e.g. Real Madrid"
              className={inputClass}
            />
          </Field>

          <RangeField
            label="Age"
            min={draftFilters.ageMin}
            max={draftFilters.ageMax}
            onMinChange={(v) => setDraftFilters({ ...draftFilters, ageMin: v })}
            onMaxChange={(v) => setDraftFilters({ ...draftFilters, ageMax: v })}
          />

          <RangeField
            label="Minutes"
            min={draftFilters.minutesMin}
            max={draftFilters.minutesMax}
            onMinChange={(v) => setDraftFilters({ ...draftFilters, minutesMin: v })}
            onMaxChange={(v) => setDraftFilters({ ...draftFilters, minutesMax: v })}
          />

          <Field label="Contract status">
            <select
              value={draftFilters.contractStatus}
              onChange={(e) =>
                setDraftFilters({ ...draftFilters, contractStatus: e.target.value as FilterState["contractStatus"] })
              }
              className={inputClass}
            >
              <option value="">Any</option>
              <option value="free">Free agent</option>
              <option value="expiring">Contract expiring</option>
              <option value="clause">Has release clause</option>
            </select>
          </Field>

          <Field label="Archetype">
            <select
              value={draftFilters.archetype}
              onChange={(e) => setDraftFilters({ ...draftFilters, archetype: e.target.value })}
              disabled={archetypeOptions.length === 0}
              className={inputClass}
            >
              <option value="">Any archetype</option>
              {archetypeOptions.map((a) => (
                <option key={a.cluster} value={a.label}>
                  {a.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-full border border-primary-200 px-5 py-2 font-sans text-sm font-medium text-foreground/70 transition hover:bg-primary-50 dark:border-primary-800 dark:hover:bg-primary-950"
          >
            Clear
          </button>
          <button
            type="submit"
            className="rounded-full bg-primary-500 px-5 py-2 font-sans text-sm font-semibold text-white transition hover:bg-primary-600"
          >
            Apply Filters
          </button>
        </div>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-sans text-sm text-foreground/60">
          {loading ? "Searching…" : `${total.toLocaleString()} comparable player${total === 1 ? "" : "s"} found`}
        </p>
        <label className="flex items-center gap-2 font-sans text-sm text-foreground/60">
          Sort by
          <select
            value={sort}
            onChange={(e) => handleSortChange(e.target.value as SimilarPlayersSort)}
            className="rounded-lg border border-primary-100 bg-white px-3 py-1.5 text-sm text-foreground outline-none ring-primary-400 focus:ring-2 dark:border-primary-900 dark:bg-[#111a17]"
          >
            <option value="match_score">Match score</option>
            <option value="composite">Composite index</option>
            <option value="age">Age</option>
            <option value="market_value">Market value</option>
          </select>
        </label>
      </div>

      <div className="min-h-[240px] rounded-2xl border border-primary-100 bg-white dark:border-primary-900 dark:bg-[#111a17]">
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex min-h-[240px] items-center justify-center py-16"
            >
              <RadarSweep size="lg" label="Finding similar players" />
            </motion.div>
          ) : error ? (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-red-500"
            >
              {error}
            </motion.div>
          ) : !data || data.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex min-h-[240px] items-center justify-center px-6 text-center font-sans text-sm text-foreground/50"
            >
              No comparable players match these filters. Try widening the range or clearing a few.
            </motion.div>
          ) : (
            <motion.div key={`similar-page-${page}-${sort}`} className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse font-sans text-sm">
                <thead>
                  <tr className="border-b border-primary-100 text-left text-xs text-foreground/50 dark:border-primary-900">
                    <th className="px-4 py-3 font-medium">Player</th>
                    <th className="px-4 py-3 font-medium">Team</th>
                    <th className="px-4 py-3 font-medium">League</th>
                    <th className="px-4 py-3 font-medium">Age</th>
                    <th className="px-4 py-3 font-medium">Match</th>
                    <th className="px-4 py-3 font-medium">Composite Index</th>
                  </tr>
                </thead>
                <motion.tbody initial="hidden" animate="visible" variants={listContainer}>
                  {data.map((sp) => (
                    <motion.tr
                      key={sp.id}
                      variants={listItem}
                      onClick={() => setCompareCandidate(sp)}
                      title="View raw metric comparison"
                      className="cursor-pointer border-b border-primary-50 transition hover:bg-primary-50/60 dark:border-primary-950 dark:hover:bg-primary-950/40"
                    >
                      <td className="px-4 py-3 font-medium">
                        <span className="flex items-center gap-1.5">
                          <Link
                            href={`/players/${sp.id}`}
                            onClick={(e) => e.stopPropagation()}
                            title={`Go to ${sp.player}'s profile`}
                            className="text-foreground hover:text-primary-600 hover:underline dark:hover:text-primary-400"
                          >
                            {sp.player}
                          </Link>
                          {sp.is_gem && <GemBadge />}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-foreground/70">{sp.team}</td>
                      <td className="px-4 py-3 text-foreground/70">{sp.league.replace(/-/g, " ")}</td>
                      <td className="px-4 py-3 text-foreground/70">{sp.age != null ? Math.round(sp.age) : "—"}</td>
                      <td className="px-4 py-3 font-medium text-primary-600 dark:text-primary-400">
                        {sp.match_score.toFixed(0)}
                      </td>
                      <td className="px-4 py-3 text-foreground/70">
                        {sp.composite != null ? sp.composite.toFixed(1) : "—"}
                      </td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {!loading && total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-4 font-sans text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-full border border-primary-200 px-4 py-1.5 text-foreground/70 transition hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-primary-800 dark:hover:bg-primary-950"
          >
            Previous
          </button>
          <span className="text-foreground/50">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            className="rounded-full border border-primary-200 px-4 py-1.5 text-foreground/70 transition hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-primary-800 dark:hover:bg-primary-950"
          >
            Next
          </button>
        </div>
      )}

      <RawCompareModal
        open={compareCandidate != null}
        onClose={() => setCompareCandidate(null)}
        targetId={id}
        targetName={result?.target?.player ?? "Target player"}
        candidate={compareCandidate}
        metricGroups={result?.metric_groups ?? []}
      />
    </section>
  );
}
