"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import { RadarSweep } from "@/components/RadarSweep";
import { TeamProfileClient } from "@/components/squad/TeamProfileClient";

export default function TeamProfilePage() {
  const params = useParams<{ team: string }>();
  // Next.js hands dynamic segments back still URL-encoded (e.g. "Manchester%20City",
  // not "Manchester City") - decode once here so downstream code (and the
  // encodeURIComponent() call in lib/api.ts's getSquadProfile) doesn't
  // double-encode it into a 404. Single-word team names never surfaced this
  // since encoding is a no-op on them.
  const team = decodeURIComponent(params.team);

  return (
    <Suspense
      fallback={
        <div className="flex min-h-[70vh] items-center justify-center">
          <RadarSweep size="lg" label="Loading squad profile" />
        </div>
      }
    >
      <TeamProfileClient initialTeam={team} />
    </Suspense>
  );
}
