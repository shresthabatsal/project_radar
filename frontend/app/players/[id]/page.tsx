"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "motion/react";
import { getPlayerProfile } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { RadarSweep } from "@/components/RadarSweep";
import { RadarChart } from "@/components/RadarChart";
import { CountUp } from "@/components/CountUp";
import { BenchmarkSection } from "@/components/profile/BenchmarkSection";
import { StyleBreakdownSection } from "@/components/profile/StyleBreakdownSection";
import { RawDataSection } from "@/components/profile/RawDataSection";
import { CareerHistorySection } from "@/components/profile/CareerHistorySection";
import { SimilaritySection } from "@/components/profile/SimilaritySection";
import { MarketValueSection } from "@/components/profile/MarketValueSection";
import { RiskFactorsCallout } from "@/components/profile/RiskFactorsCallout";
import { MoneyballSection } from "@/components/profile/MoneyballSection";
import { ImpactScoreSection } from "@/components/profile/ImpactScoreSection";
import { WageContractInfo } from "@/components/profile/WageContractInfo";
import { SeasonSelector } from "@/components/profile/SeasonSelector";

const TABS = [
  { key: "raw", label: "Profile" },
  { key: "benchmark", label: "Benchmark" },
  { key: "style", label: "Playing Style" },
  { key: "career", label: "Career" },
  { key: "similar", label: "Similar Players" },
  { key: "market", label: "Market Value" },
  { key: "moneyball", label: "Moneyball" },
  { key: "impact", label: "Impact Score" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function PlayerProfilePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [tab, setTab] = useState<TabKey>("raw");

  const fetcher = useCallback(() => getPlayerProfile(id), [id]);
  const { data: profile, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load this player.");

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <RadarSweep size="lg" label="Loading profile" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center px-6 text-center font-sans text-foreground/60">
        {error ?? "Player not found."}
      </div>
    );
  }

  const bio = profile.profile;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              {bio.player}
            </h1>
            <p className="mt-1 font-sans text-sm text-foreground/60">
              {bio.team} &middot; {bio.league.replace(/-/g, " ")} &middot; {bio.season}
            </p>
          </div>
          <SeasonSelector id={id} currentSeason={bio.season} />
        </div>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 font-sans text-sm text-foreground/70">
          <span className="font-medium text-primary-600 dark:text-primary-400">{bio.position}</span>
          {bio.age != null && <span>{Math.round(bio.age)} yo</span>}
          {bio.minutes != null && <span>{Math.round(bio.minutes).toLocaleString()} minutes</span>}
          {bio.goals != null && <span>{bio.goals} goals</span>}
          {bio.assists != null && <span>{bio.assists} assists</span>}
          {bio.xg != null && <span>{bio.xg.toFixed(1)} xG</span>}
        </div>
        <WageContractInfo bio={bio} />
      </motion.div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-5">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: "easeOut" }}
          className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-primary-100 bg-white p-8 text-center dark:border-primary-900 dark:bg-[#111a17] lg:col-span-2"
        >
          <span className="font-sans text-sm text-foreground/50">Composite Index</span>
          {profile.composite_index != null ? (
            <CountUp
              value={profile.composite_index}
              decimals={1}
              className="font-display text-6xl font-semibold text-primary-600 dark:text-primary-400"
            />
          ) : (
            <span className="font-display text-4xl text-foreground/30">—</span>
          )}
          {profile.composite_description && (
            <span className="rounded-full bg-primary-50 px-3 py-1 font-sans text-sm font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300">
              {profile.composite_description}
            </span>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15, ease: "easeOut" }}
          className="flex items-center justify-center rounded-2xl border border-primary-100 bg-white p-4 dark:border-primary-900 dark:bg-[#111a17] lg:col-span-3"
        >
          <RadarChart categories={profile.radar} />
        </motion.div>
      </div>

      <RiskFactorsCallout risk={profile.risk} />

      <div className="flex flex-col gap-8">
        <nav className="flex flex-wrap gap-2 border-b border-primary-100 pb-4 dark:border-primary-900">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              aria-current={tab === t.key ? "page" : undefined}
              className={`rounded-full px-4 py-2 font-sans text-sm font-medium transition ${
                tab === t.key
                  ? "bg-primary-500 text-white"
                  : "text-foreground/60 hover:bg-primary-50 dark:hover:bg-primary-950"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {tab === "benchmark" && <BenchmarkSection id={id} radar={profile.radar} />}
        {tab === "style" && <StyleBreakdownSection id={id} />}
        {tab === "raw" && <RawDataSection id={id} />}
        {tab === "career" && <CareerHistorySection id={id} currentSeason={bio.season} />}
        {tab === "similar" && <SimilaritySection id={id} />}
        {tab === "market" && <MarketValueSection id={id} />}
        {tab === "moneyball" && <MoneyballSection id={id} />}
        {tab === "impact" && <ImpactScoreSection id={id} />}
      </div>
    </div>
  );
}
