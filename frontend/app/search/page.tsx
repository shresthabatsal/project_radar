"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { ApiError, getMeta, searchPlayers, type PlayerSearchSort, type SearchPlayersParams } from "@/lib/api";
import type { MetaResponse, PlayerSearchResult } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";
import { SearchFilters } from "@/components/search/SearchFilters";
import { SearchResults } from "@/components/search/SearchResults";
import {
  emptyFilterState, filterStateFromSearchParams, toSearchParams, type FilterState,
} from "@/components/search/filterState";

const PAGE_SIZE = 25;

export default function AdvancedSearchPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center"><RadarSweep size="lg" label="Loading search" /></div>}>
      <AdvancedSearchPageInner />
    </Suspense>
  );
}

function AdvancedSearchPageInner() {
  // Lets another page (the squad profile's "recruit for this gap" actions)
  // deep-link in with filters pre-filled - e.g. /search?position=DF&league=...
  // Read once on mount only: this is a one-time bootstrap of filter state,
  // not a live two-way URL sync, so later filter edits don't rewrite the URL.
  const searchParams = useSearchParams();

  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaError, setMetaError] = useState(false);

  const [filters, setFilters] = useState<FilterState | null>(null);
  const [appliedParams, setAppliedParams] = useState<SearchPlayersParams | null>(null);

  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchVersion, setSearchVersion] = useState(0);

  const abortRef = useRef<AbortController | null>(null);

  // Bootstrap: seasons/leagues come from the backend, not a hardcoded list,
  // and the default season seeds the first search.
  useEffect(() => {
    let cancelled = false;
    getMeta()
      .then((res) => {
        if (cancelled) return;
        setMeta(res);
        const defaultSeason = res.seasons[0] ?? "";
        const initial = searchParams.size > 0
          ? filterStateFromSearchParams(searchParams, defaultSeason)
          : emptyFilterState(defaultSeason);
        setFilters(initial);
        setAppliedParams(toSearchParams(initial, { limit: PAGE_SIZE, offset: 0 }));
      })
      .catch(() => {
        if (!cancelled) setMetaError(true);
      });
    return () => {
      cancelled = true;
    };
    // searchParams is intentionally read only once, on mount (see comment
    // above) - it is not a live dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!appliedParams) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // isCurrent guards every state update below so a request that's been
    // superseded (abortRef now points at a newer controller) can never
    // clobber state a later, still-in-flight search already owns - not
    // just the aborted one's own results/error, but its `finally`'s
    // setLoading(false) too, which would otherwise race the next search's
    // setLoading(true) and flash the loading state off early.
    const isCurrent = () => abortRef.current === controller;

    // State updates deferred into the promise chain (not called at the top
    // of the effect body) rather than synchronously here.
    Promise.resolve()
      .then(() => {
        setLoading(true);
        setError(null);
        return searchPlayers(appliedParams, { signal: controller.signal });
      })
      .then((res) => {
        if (!isCurrent()) return;
        setResults(res.players);
        setTotal(res.total);
        setSearchVersion((v) => v + 1);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!isCurrent()) return;
        setError(err instanceof ApiError ? err.message : "Search failed - try again.");
        setResults([]);
        setTotal(0);
      })
      .finally(() => {
        if (isCurrent()) setLoading(false);
      });

    return () => controller.abort();
  }, [appliedParams]);

  function handleSubmit() {
    if (!filters) return;
    setAppliedParams(toSearchParams(filters, { limit: PAGE_SIZE, offset: 0 }));
  }

  function handleSortChange(sort: PlayerSearchSort) {
    if (!filters) return;
    setFilters({ ...filters, sort });
    setAppliedParams((prev) => (prev ? { ...prev, sort, offset: 0 } : prev));
  }

  function handlePageChange(offset: number) {
    setAppliedParams((prev) => (prev ? { ...prev, offset } : prev));
  }

  if (metaError) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-6 text-center font-sans text-foreground/60">
        Couldn&apos;t reach the backend - make sure the API server is running.
      </div>
    );
  }

  if (!meta || !filters) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <RadarSweep size="lg" label="Loading search" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="flex flex-col gap-2"
      >
        <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground">
          Advanced Search
        </h1>
        <p className="max-w-2xl font-sans text-sm leading-6 text-foreground/60">
          Filter by position, age, nationality, value, wage, and contract status, or dig into
          per-90 performance thresholds under Advanced stats. Every filter combines with AND.
        </p>
      </motion.div>

      <SearchFilters meta={meta} filters={filters} onChange={setFilters} onSubmit={handleSubmit} />

      <SearchResults
        results={results}
        total={total}
        limit={appliedParams?.limit ?? PAGE_SIZE}
        offset={appliedParams?.offset ?? 0}
        loading={loading}
        error={error}
        sort={filters.sort}
        onSortChange={handleSortChange}
        onPageChange={handlePageChange}
        searchKey={String(searchVersion)}
      />
    </div>
  );
}
