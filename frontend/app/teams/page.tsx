"use client";

import { Suspense } from "react";
import { RadarSweep } from "@/components/RadarSweep";
import { TeamProfileClient } from "@/components/squad/TeamProfileClient";

export default function TeamsIndexPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[70vh] items-center justify-center">
          <RadarSweep size="lg" label="Loading squad profile" />
        </div>
      }
    >
      <TeamProfileClient />
    </Suspense>
  );
}
