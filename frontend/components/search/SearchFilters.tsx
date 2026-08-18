"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { getPlayerFilters } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import type { MetaResponse } from "@/lib/types";
import { Combobox } from "@/components/Combobox";
import type { FilterState } from "./filterState";

const POSITIONS = ["GK", "DF", "MF", "FW"] as const;

type SearchFiltersProps = {
  meta: MetaResponse;
  filters: FilterState;
  onChange: (next: FilterState) => void;
  onSubmit: () => void;
};

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-sans text-xs font-medium text-foreground/60">{label}</span>
      {children}
      {hint && <span className="font-sans text-[11px] text-foreground/40">{hint}</span>}
    </label>
  );
}

const inputClass =
  "rounded-lg border border-primary-100 bg-white px-3 py-2 font-sans text-sm text-foreground outline-none ring-primary-400 transition focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-primary-900 dark:bg-[#111a17]";

function RangePair({
  label,
  unit,
  min,
  max,
  onMinChange,
  onMaxChange,
}: {
  label: string;
  unit?: string;
  min: string;
  max: string;
  onMinChange: (v: string) => void;
  onMaxChange: (v: string) => void;
}) {
  return (
    <Field label={unit ? `${label} (${unit})` : label}>
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

export function SearchFilters({ meta, filters, onChange, onSubmit }: SearchFiltersProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  function set<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  // Real team/nationality values present in the current season (further
  // scoped to league, if chosen). Always in sync with whatever snapshot
  // is loaded, not a hardcoded list.
  const filterOptionsFetcher = useCallback(
    () => getPlayerFilters({ season: filters.season || undefined, league: filters.league || undefined }),
    [filters.season, filters.league],
  );
  const { data: filterOptions, loading: filterOptionsLoading } = useAsyncData(
    filterOptionsFetcher,
    [filterOptionsFetcher],
    "Couldn't load team/nationality options.",
  );

  // ml.style_clustering archetypes for the chosen position only - labels
  // aren't comparable across position groups. Empty for GK or before a
  // position is chosen. Deduped by label, since the filter matches by label text.
  const archetypeOptions = filters.position
    ? Array.from(
        new Map(
          (filterOptions?.archetypes ?? [])
            .filter((a) => a.position === filters.position)
            .map((a) => [a.label, a] as const),
        ).values(),
      )
    : [];

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="flex flex-col gap-6 rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Season">
          <select
            value={filters.season}
            onChange={(e) => set("season", e.target.value)}
            className={inputClass}
          >
            {meta.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Position">
          <select
            value={filters.position}
            onChange={(e) => {
              // An archetype belonging to the OLD position (or "any") can't
              // carry over to the new one - cleared unconditionally, same
              // rule League→Team already follows below.
              const position = e.target.value;
              onChange({ ...filters, position, archetype: "" });
            }}
            className={inputClass}
          >
            <option value="">Any position</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Archetype"
          hint={
            !filters.position
              ? "Pick a position first"
              : filters.position === "GK"
                ? "Goalkeepers have no style archetypes"
                : "ml.style_clustering"
          }
        >
          <select
            value={filters.archetype}
            onChange={(e) => set("archetype", e.target.value)}
            disabled={!filters.position || archetypeOptions.length === 0}
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

        <Field label="League">
          <select
            value={filters.league}
            onChange={(e) => {
              // A team from the OLD league can't carry over - cleared
              // unconditionally so `team` never points at a value the current scope's dropdown wouldn't list.
              const league = e.target.value;
              onChange({ ...filters, league, team: "" });
            }}
            className={inputClass}
          >
            <option value="">All leagues</option>
            {meta.leagues.map((l) => (
              <option key={l.key} value={l.key}>
                {l.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Team" hint={filters.league ? "Type to search" : "Pick a league first"}>
          <Combobox
            value={filters.team}
            onChange={(v) => set("team", v)}
            options={filterOptions?.teams ?? []}
            loading={filterOptionsLoading}
            disabled={!filters.league}
            placeholder={filters.league ? "e.g. Real Madrid" : "Pick a league first"}
            emptyOptionLabel="Any team"
          />
        </Field>

        <RangePair
          label="Age"
          min={filters.ageMin}
          max={filters.ageMax}
          onMinChange={(v) => set("ageMin", v)}
          onMaxChange={(v) => set("ageMax", v)}
        />

        <Field label="Nationality" hint="Type to search">
          <Combobox
            value={filters.nationality}
            onChange={(v) => set("nationality", v)}
            options={filterOptions?.nationalities ?? []}
            loading={filterOptionsLoading}
            placeholder="e.g. ESP"
            emptyOptionLabel="Any nationality"
          />
        </Field>

        <Field label="Minimum minutes played">
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={filters.minMinutes}
            onChange={(e) => set("minMinutes", e.target.value)}
            placeholder="e.g. 900"
            className={inputClass}
          />
        </Field>

        <Field label="Contract expiring within">
          <div className="flex items-center gap-2">
            <input
              type="number"
              inputMode="numeric"
              min={0}
              value={filters.contractExpiringMonths}
              onChange={(e) => set("contractExpiringMonths", e.target.value)}
              placeholder="e.g. 12"
              className={inputClass}
            />
            <span className="whitespace-nowrap font-sans text-xs text-foreground/50">months</span>
          </div>
        </Field>

        <RangePair
          label="Market value"
          unit="€M"
          min={filters.marketValueMinM}
          max={filters.marketValueMaxM}
          onMinChange={(v) => set("marketValueMinM", v)}
          onMaxChange={(v) => set("marketValueMaxM", v)}
        />

        <RangePair
          label="Annual wage"
          unit="€M"
          min={filters.wageMinM}
          max={filters.wageMaxM}
          onMinChange={(v) => set("wageMinM", v)}
          onMaxChange={(v) => set("wageMaxM", v)}
        />

        <Field label="Release clause">
          <select
            value={filters.hasReleaseClause}
            onChange={(e) => set("hasReleaseClause", e.target.value as FilterState["hasReleaseClause"])}
            className={inputClass}
          >
            <option value="any">Any</option>
            <option value="yes">Has a release clause</option>
            <option value="no">No release clause</option>
          </select>
        </Field>
      </div>

      <div className="border-t border-primary-100 pt-4 dark:border-primary-900">
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex items-center gap-2 font-sans text-sm font-medium text-primary-700 dark:text-primary-300"
          aria-expanded={advancedOpen}
        >
          <motion.svg
            animate={{ rotate: advancedOpen ? 90 : 0 }}
            transition={{ duration: 0.2 }}
            className="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </motion.svg>
          Advanced stats
        </button>

        <AnimatePresence initial={false}>
          {advancedOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="grid grid-cols-1 gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Min goals /90">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minGoalsPer90}
                    onChange={(e) => set("minGoalsPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min assists /90">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minAssistsPer90}
                    onChange={(e) => set("minAssistsPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min xG /90">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minXgPer90}
                    onChange={(e) => set("minXgPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min npxG /90">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minNpxgPer90}
                    onChange={(e) => set("minNpxgPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min progressive passes" hint="Season total">
                  <input
                    type="number"
                    value={filters.minProgressivePasses}
                    onChange={(e) => set("minProgressivePasses", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min tackles" hint="Season total">
                  <input
                    type="number"
                    value={filters.minTackles}
                    onChange={(e) => set("minTackles", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min SCA /90" hint="Shot-creating actions">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minScaPer90}
                    onChange={(e) => set("minScaPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Min GCA /90" hint="Goal-creating actions">
                  <input
                    type="number"
                    step="0.01"
                    value={filters.minGcaPer90}
                    onChange={(e) => set("minGcaPer90", e.target.value)}
                    className={inputClass}
                  />
                </Field>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          className="rounded-full bg-primary-500 px-6 py-2.5 font-sans text-sm font-semibold text-white transition hover:bg-primary-600"
        >
          Search
        </button>
      </div>
    </form>
  );
}
