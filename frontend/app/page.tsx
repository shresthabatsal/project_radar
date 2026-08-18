"use client";

import { useEffect, useState } from "react";
import { getMeta } from "@/lib/api";
import type { MetaResponse } from "@/lib/types";
import { HeroSection } from "@/components/home/HeroSection";
import { HowItWorksSection } from "@/components/home/HowItWorksSection";
import { DataCoverageSection } from "@/components/home/DataCoverageSection";

export default function Home() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getMeta()
      .then((res) => {
        if (!cancelled) setMeta(res);
      })
      .catch(() => {
        // Data-description section and the hero search bar both degrade
        // gracefully (loading/disabled state) if the backend is unreachable.
      })
      .finally(() => {
        if (!cancelled) setMetaLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const latestSeason = meta?.seasons[0] ?? null;

  return (
    <div className="flex flex-col">
      <HeroSection season={latestSeason} />
      <HowItWorksSection />
      <DataCoverageSection meta={meta} loading={metaLoading} />
    </div>
  );
}
