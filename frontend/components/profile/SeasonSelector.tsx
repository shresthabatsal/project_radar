"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { getCareerHistory } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";

/** A plain season picker for the player profile page - each option is a
 * different season's own player id, so picking one navigates to that id.
 * That's a real id change, so every id-driven section naturally re-fetches. */
export function SeasonSelector({ id, currentSeason }: { id: string; currentSeason: string }) {
  const router = useRouter();
  const fetcher = useCallback(() => getCareerHistory(id), [id]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load season list.");

  if (loading || error || !data || data.history.length === 0) {
    return <span className="font-sans text-sm text-foreground/60">Season {currentSeason}</span>;
  }

  // Newest season first in the picker; the id's own encoded season/league/
  // team is what selects the matching <option> below.
  const seasons = [...data.history].reverse();

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const nextId = e.target.value;
    if (nextId && nextId !== id) {
      router.push(`/players/${nextId}`);
    }
  }

  return (
    <label className="flex items-center gap-2 font-sans text-sm text-foreground/60">
      Season
      <select
        value={id}
        onChange={handleChange}
        className="rounded-lg border border-primary-100 bg-white px-3 py-1.5 text-sm text-foreground outline-none ring-primary-400 transition focus:ring-2 dark:border-primary-900 dark:bg-[#111a17]"
      >
        {seasons.map((s) => (
          <option key={s.id} value={s.id}>
            {s.season} · {s.team}
          </option>
        ))}
      </select>
    </label>
  );
}
