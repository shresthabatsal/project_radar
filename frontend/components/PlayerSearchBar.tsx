"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ApiError, listPlayers } from "@/lib/api";
import type { PlayerSummary } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 300;

type PlayerSearchBarProps = {
  /** Season to search within - the hero passes the dataset's most recent
   * season once GET /meta resolves. Search is disabled until it's set. */
  season: string | null;
  placeholder?: string;
  className?: string;
};

export function PlayerSearchBar({ season, placeholder, className }: PlayerSearchBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlayerSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    // Below the minimum length there's nothing to fetch - handleChange
    // already clears results/error synchronously for that case (an effect
    // shouldn't fire setState purely as a reaction to its own inputs).
    if (!season || trimmed.length < MIN_QUERY_LENGTH) return;

    // Every state update lives inside this callback, not the effect body
    // itself, so it only ever fires once the debounce actually elapses -
    // no spinner flicker on every keystroke while the user is still typing.
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      listPlayers({ season, name: trimmed, limit: 8 }, { signal: controller.signal })
        .then((res) => {
          setResults(res.players);
          setOpen(true);
          setActiveIndex(-1);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError(err instanceof ApiError ? err.message : "Search failed - try again.");
          setResults([]);
        })
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query, season]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setQuery(value);
    if (value.trim().length < MIN_QUERY_LENGTH) {
      abortRef.current?.abort();
      setResults([]);
      setLoading(false);
      setError(null);
      setOpen(false);
    }
  }

  function selectPlayer(player: PlayerSummary) {
    setOpen(false);
    setQuery("");
    setResults([]);
    router.push(`/players/${player.id}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const chosen = activeIndex >= 0 ? results[activeIndex] : results[0];
      if (chosen) selectPlayer(chosen);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown = open && query.trim().length >= MIN_QUERY_LENGTH;

  return (
    <div ref={containerRef} className={`relative w-full ${className ?? ""}`}>
      <div className="relative">
        <svg
          className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
        </svg>

        <input
          type="text"
          value={query}
          disabled={!season}
          onChange={handleChange}
          onFocus={() => query.trim().length >= MIN_QUERY_LENGTH && setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={season ? (placeholder ?? "Search for a player...") : "Loading players..."}
          role="combobox"
          aria-expanded={showDropdown}
          aria-autocomplete="list"
          aria-controls="player-search-results"
          className="w-full rounded-full border border-primary-200 bg-white/95 py-4 pl-12 pr-14 font-sans text-base text-foreground shadow-lg shadow-primary-950/5 outline-none ring-primary-400 transition placeholder:text-foreground/40 focus:ring-2 disabled:cursor-not-allowed disabled:opacity-70 dark:border-primary-900 dark:bg-[#111a17]/95"
        />

        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {loading ? (
            <RadarSweep size="sm" label="Searching" />
          ) : (
            <button
              type="button"
              aria-label="Search"
              onClick={() => results[0] && selectPlayer(results[0])}
              disabled={!season || results.length === 0}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-500 text-white transition hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {showDropdown && (
          <motion.ul
            id="player-search-results"
            role="listbox"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-primary-100 bg-white shadow-xl dark:border-primary-900 dark:bg-[#111a17]"
          >
            {error && <li className="px-5 py-4 text-sm text-red-500">{error}</li>}

            {!error && !loading && results.length === 0 && (
              <li className="px-5 py-4 text-sm text-foreground/50">
                No players found for &ldquo;{query.trim()}&rdquo;.
              </li>
            )}

            {results.map((p, i) => (
              <li key={p.id} role="option" aria-selected={i === activeIndex}>
                <button
                  type="button"
                  onMouseEnter={() => setActiveIndex(i)}
                  onClick={() => selectPlayer(p)}
                  className={`flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition ${
                    i === activeIndex ? "bg-primary-50 dark:bg-primary-950" : ""
                  }`}
                >
                  <span className="flex flex-col">
                    <span className="font-sans font-medium text-foreground">{p.player}</span>
                    <span className="text-xs text-foreground/50">
                      {p.team} &middot; {p.league.replace(/-/g, " ")} &middot; {p.position}
                    </span>
                  </span>
                  {p.minutes != null && (
                    <span className="shrink-0 text-xs text-foreground/40">{Math.round(p.minutes)}&apos;</span>
                  )}
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
