// backend/scoring/risk.py's four reasons, each with its own color so
// multiple triggered reasons on one player stay individually legible
// side by side - same "visually distinct, never merged" principle
// GemBadge follows. Shared by the squad profile's High Risk Players
// section and the individual player profile's risk callout so the two
// never drift into different colors for the same reason.
export const RISK_REASON_STYLE: Record<string, { short: string; chipClass: string; cardClass: string }> = {
  contract: {
    short: "Contract",
    chipClass: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    cardClass: "border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/20",
  },
  mileage_decline: {
    short: "Mileage",
    chipClass: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
    cardClass: "border-orange-200 bg-orange-50/60 dark:border-orange-900 dark:bg-orange-950/20",
  },
  sell_high: {
    short: "Sell-high",
    chipClass: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    cardClass: "border-red-200 bg-red-50/60 dark:border-red-900 dark:bg-red-950/20",
  },
  financial: {
    short: "Financial",
    chipClass: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
    cardClass: "border-sky-200 bg-sky-50/60 dark:border-sky-900 dark:bg-sky-950/20",
  },
};

export function riskReasonStyle(reason: string) {
  return (
    RISK_REASON_STYLE[reason] ?? {
      short: reason,
      chipClass: "bg-foreground/10 text-foreground/60",
      cardClass: "border-primary-100 bg-primary-50/60 dark:border-primary-900 dark:bg-primary-950/20",
    }
  );
}
