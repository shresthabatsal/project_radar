import type { PlayerProfileBasic } from "@/lib/types";

function formatDate(raw: string): string {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// Mirrors backend/config.py's CONTRACT_MONTHS_TIER_* bands, so the
// urgency badge shown here matches what's actually driving the Moneyball score.
function urgencyBand(months: number | null): { label: string; className: string } {
  if (months == null) {
    return { label: "Contract status unknown", className: "bg-foreground/5 text-foreground/50" };
  }
  if (months <= 0) {
    return {
      label: "Expired / free agent",
      className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    };
  }
  if (months <= 6) {
    return {
      label: `Expires in ${months} mo — high urgency`,
      className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    };
  }
  if (months <= 12) {
    return {
      label: `Expires in ${months} mo`,
      className: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
    };
  }
  if (months <= 18) {
    return {
      label: `Expires in ${months} mo`,
      className: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    };
  }
  if (months <= 24) {
    return {
      label: `Expires in ${months} mo`,
      className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
    };
  }
  return {
    label: `Expires in ${months} mo`,
    className: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  };
}

/** Wage & contract chips for the profile header. Renders nothing at all
 * when the player has no verified wage or contract record, rather than a row of blank/"N/A" chips. */
export function WageContractInfo({ bio }: { bio: PlayerProfileBasic }) {
  const hasWage = Boolean(bio.weekly_wage_label || bio.annual_wage_label);
  const hasContract = Boolean(bio.contract_expiry);
  const hasClause = Boolean(bio.release_clause_label);

  if (!hasWage && !hasContract && !hasClause) return null;

  const band = hasContract ? urgencyBand(bio.contract_months_remaining) : null;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      {bio.weekly_wage_label && (
        <span className="rounded-full border border-primary-100 bg-white px-3 py-1 font-sans text-xs font-medium text-foreground/70 dark:border-primary-900 dark:bg-[#111a17]">
          {bio.weekly_wage_label}/week
        </span>
      )}
      {bio.annual_wage_label && (
        <span className="rounded-full border border-primary-100 bg-white px-3 py-1 font-sans text-xs font-medium text-foreground/70 dark:border-primary-900 dark:bg-[#111a17]">
          {bio.annual_wage_label}/year
        </span>
      )}
      {hasContract && band && (
        <span className={`rounded-full px-3 py-1 font-sans text-xs font-medium ${band.className}`}>
          {band.label} ({formatDate(bio.contract_expiry as string)})
        </span>
      )}
      {bio.release_clause_label && (
        <span className="rounded-full border border-primary-100 bg-white px-3 py-1 font-sans text-xs font-medium text-foreground/70 dark:border-primary-900 dark:bg-[#111a17]">
          Release clause {bio.release_clause_label}
        </span>
      )}
    </div>
  );
}
