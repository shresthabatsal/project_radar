"use client";

import { useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { getMeta, getPlayerFilters, getSquadProfile } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { Combobox } from "@/components/Combobox";
import { PositionDepthChart } from "./PositionDepthChart";
import { AgeCurveChart } from "./AgeCurveChart";
import { ContractCliffTimeline } from "./ContractCliffTimeline";
import { StyleDiversitySection } from "./StyleDiversitySection";
import { WageOutputScatter } from "./WageOutputScatter";
import { HighRiskPlayersSection } from "./HighRiskPlayersSection";

const inputClass =
  "rounded-lg border border-primary-100 bg-white px-3 py-2 font-sans text-sm text-foreground outline-none ring-primary-400 transition focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-primary-900 dark:bg-[#111a17]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-sans text-xs font-medium text-foreground/60">{label}</span>
      {children}
    </label>
  );
}

function SectionCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="flex flex-col gap-4 rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]"
    >
      <div>
        <h2 className="font-display text-xl font-semibold text-foreground">{title}</h2>
        <p className="font-sans text-sm text-foreground/50">{subtitle}</p>
      </div>
      {children}
    </motion.section>
  );
}

/** Team/season/league selector + the five-section squad diagnostic. Shared
 * by /teams (no team chosen yet) and /teams/[team] (team fixed by the
 * route) - both just render this with a different initialTeam. */
export function TeamProfileClient({ initialTeam }: { initialTeam?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [season, setSeason] = useState(searchParams.get("season") ?? "");
  const [league, setLeague] = useState(searchParams.get("league") ?? "");
  const [team, setTeam] = useState(initialTeam ?? "");

  const metaFetcher = useCallback(() => getMeta(), []);
  const { data: meta } = useAsyncData(metaFetcher, [metaFetcher], "Couldn't load season/league list.");

  // Falls back to the backend's first available season once meta loads,
  // without needing an effect to sync it into state - the <select> below is
  // driven by this derived value, and its own onChange still overrides it.
  const effectiveSeason = season || meta?.seasons[0] || "";

  const filterOptionsFetcher = useCallback(
    () => getPlayerFilters({ season: effectiveSeason || undefined, league: league || undefined }),
    [effectiveSeason, league],
  );
  const { data: filterOptions, loading: teamsLoading } = useAsyncData(
    filterOptionsFetcher,
    [filterOptionsFetcher],
    "Couldn't load team list.",
  );

  const profileFetcher = useCallback(() => {
    if (!effectiveSeason || !league || !team) return Promise.resolve(null);
    return getSquadProfile(team, { season: effectiveSeason, league });
  }, [effectiveSeason, league, team]);
  const { data: profile, loading: profileLoading, error: profileError } = useAsyncData(
    profileFetcher,
    [profileFetcher],
    "Couldn't load this squad's profile.",
  );

  function selectTeam(next: string) {
    setTeam(next);
    if (next && effectiveSeason && league) {
      router.push(`/teams/${encodeURIComponent(next)}?season=${encodeURIComponent(effectiveSeason)}&league=${encodeURIComponent(league)}`);
    }
  }

  function selectLeague(next: string) {
    // A team from the old league can't carry over - cleared unconditionally,
    // same rule advanced search's League field already follows.
    setLeague(next);
    setTeam("");
  }

  const gapCounts = profile
    ? {
        thin: profile.position_depth.filter((p) => p.is_thin).length,
        aging: profile.age_curve.filter((a) => a.is_top_heavy).length,
        cliffs: profile.contract_cliff.length,
        similar: profile.style_diversity.filter((s) => s.is_style_similar).length,
        highRisk: profile.high_risk_players.length,
      }
    : null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="flex flex-col gap-2"
      >
        <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Squad Profile
        </h1>
        <p className="max-w-2xl font-sans text-sm leading-6 text-foreground/60">
          A read-only diagnostic of one team&apos;s roster - depth, age, contract exposure, style
          variety, and wage-to-output. This surfaces gaps; it doesn&apos;t rank replacements - use
          &quot;Recruit for this gap&quot; on any flagged issue to search for candidates.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17] sm:grid-cols-3">
        <Field label="Season">
          <select value={effectiveSeason} onChange={(e) => setSeason(e.target.value)} className={inputClass}>
            <option value="">Select season</option>
            {meta?.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="League">
          <select value={league} onChange={(e) => selectLeague(e.target.value)} className={inputClass}>
            <option value="">Select league</option>
            {meta?.leagues.map((l) => (
              <option key={l.key} value={l.key}>
                {l.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Team">
          <Combobox
            value={team}
            onChange={selectTeam}
            options={filterOptions?.teams ?? []}
            loading={teamsLoading}
            disabled={!league}
            placeholder={league ? "e.g. Liverpool" : "Pick a league first"}
            emptyOptionLabel="Choose a team"
          />
        </Field>
      </div>

      {!effectiveSeason || !league || !team ? (
        <div className="flex min-h-[30vh] items-center justify-center text-center font-sans text-sm text-foreground/50">
          Pick a season, league, and team above to load its squad profile.
        </div>
      ) : profileLoading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <RadarSweep size="lg" label="Building squad profile" />
        </div>
      ) : profileError || !profile ? (
        <div className="flex min-h-[30vh] items-center justify-center text-center font-sans text-sm text-red-500">
          {profileError ?? "No data."}
        </div>
      ) : (
        <>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05, ease: "easeOut" }}
            className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]"
          >
            <div>
              <h2 className="font-display text-2xl font-semibold text-foreground">{profile.team}</h2>
              <p className="font-sans text-sm text-foreground/50">
                {profile.league.replace(/-/g, " ")} · {profile.season} · {profile.roster_size} rostered
              </p>
            </div>
            {gapCounts && (
              <div className="flex flex-wrap gap-2">
                {gapCounts.thin > 0 && <GapPill label={`${gapCounts.thin} thin position${gapCounts.thin > 1 ? "s" : ""}`} />}
                {gapCounts.aging > 0 && <GapPill label={`${gapCounts.aging} aging position${gapCounts.aging > 1 ? "s" : ""}`} />}
                {gapCounts.cliffs > 0 && <GapPill label={`${gapCounts.cliffs} contract cliff${gapCounts.cliffs > 1 ? "s" : ""}`} />}
                {gapCounts.similar > 0 && <GapPill label={`${gapCounts.similar} low-diversity position${gapCounts.similar > 1 ? "s" : ""}`} />}
                {gapCounts.highRisk > 0 && <GapPill label={`${gapCounts.highRisk} high-risk player${gapCounts.highRisk > 1 ? "s" : ""}`} />}
                {gapCounts.thin + gapCounts.aging + gapCounts.cliffs + gapCounts.similar + gapCounts.highRisk === 0 && (
                  <span className="rounded-full bg-primary-50 px-3 py-1 font-sans text-xs font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                    No flagged gaps
                  </span>
                )}
              </div>
            )}
          </motion.div>

          <SectionCard title="Position Depth" subtitle="Rostered count and composite-index range per position.">
            <PositionDepthChart data={profile.position_depth} season={profile.season} league={profile.league} minDepth={profile.min_depth} />
          </SectionCard>

          <SectionCard title="Age Curve" subtitle="Age distribution per position, relative to the squad's own range.">
            <AgeCurveChart data={profile.age_curve} season={profile.season} league={profile.league} agingThreshold={profile.aging_threshold} />
          </SectionCard>

          <SectionCard title="Contract Cliff" subtitle="Upcoming expiries, highest-impact players first.">
            <ContractCliffTimeline data={profile.contract_cliff} season={profile.season} league={profile.league} />
          </SectionCard>

          <SectionCard title="Style Diversity" subtitle="How stylistically similar each position's players are to each other.">
            <StyleDiversitySection data={profile.style_diversity} season={profile.season} league={profile.league} />
          </SectionCard>

          <SectionCard title="Wage vs. Output" subtitle="Composite index against wage - under/over-paid players at a glance.">
            <WageOutputScatter data={profile.wage_output} />
          </SectionCard>

          <SectionCard
            title="High Risk Players"
            subtitle="Contract, mileage/decline, sell-high, and financial flags - each independently computed, never a sell recommendation."
          >
            <HighRiskPlayersSection data={profile.high_risk_players} />
          </SectionCard>
        </>
      )}
    </div>
  );
}

function GapPill({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-amber-100 px-3 py-1 font-sans text-xs font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
      {label}
    </span>
  );
}
