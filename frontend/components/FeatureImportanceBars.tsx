"use client";

import { motion } from "motion/react";
import type { FeatureContribution } from "@/lib/types";

const FEATURE_LABELS: Record<string, string> = {
  power_rating: "League strength",
  log_min: "Minutes played",
  log_games: "Games played",
  minutes: "Minutes played",
  contract_months: "Contract length",
  age: "Age",
  age_sq: "Age (curve)",
  goals_per90: "Goals /90",
  assists_per90: "Assists /90",
  prog_passes_per90: "Progressive passes /90",
  xg_per90: "xG /90",
  npxg_per90: "npxG /90",
  xg_assist_per90: "xA /90",
  sca_per90: "Shot-creating actions /90",
  def_actions_per90: "Tackles + interceptions /90",
  aerials_won_pct: "Aerial duels won %",
  gk_save_pct: "Save %",
  log_prior_mv: "Last season's value",
  has_prior_mv: "Has a prior-season value",
  pos_DF: "Position: Defender",
  pos_MF: "Position: Midfielder",
  pos_FW: "Position: Forward",
  pos_GK: "Position: Goalkeeper",
  wage: "Wage",
};

function humanize(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

type FeatureImportanceBarsProps = {
  contributors: FeatureContribution[];
  className?: string;
};

/** "What drove this number" - a horizontal bar per contributing feature,
 * each bar animating in from zero width rather than appearing full-size. */
export function FeatureImportanceBars({ contributors, className }: FeatureImportanceBarsProps) {
  if (contributors.length === 0) return null;
  const max = Math.max(...contributors.map((c) => c.weight_pct), 1);

  return (
    <div className={`flex flex-col gap-2.5 ${className ?? ""}`}>
      {contributors.map((c, i) => (
        <div key={c.feature} className="flex items-center gap-3">
          <span className="w-36 shrink-0 truncate font-sans text-xs text-foreground/60">
            {humanize(c.feature)}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-primary-50 dark:bg-primary-950">
            <motion.div
              className="h-full rounded-full bg-primary-500"
              initial={{ width: 0 }}
              animate={{ width: `${(c.weight_pct / max) * 100}%` }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: "easeOut" }}
            />
          </div>
          <span className="w-12 shrink-0 text-right font-sans text-xs text-foreground/50">
            {c.weight_pct.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}
