import type { PlayerRiskAssessment } from "@/lib/types";
import { riskReasonStyle } from "@/lib/riskReasons";

/** backend/scoring/risk.py's four independent risk reasons for THIS
 * player, whoever's squad they're on - same colored-card treatment as the
 * Playing Style tab's Strengths/Weaknesses cards (components/profile/
 * StyleBreakdownSection.tsx's HighlightCard), just keyed by risk reason
 * instead of strength/weakness tone. Useful outside squad context too: a
 * rival's player showing sell-high signals is a recruitment opportunity,
 * not just a retention concern for their own club - which is why this
 * renders for ANY player profile, not only rostered squad views.
 *
 * Renders nothing (not an empty card) when the player triggers no reason -
 * absence of risk isn't itself something worth a headline on every single
 * profile page. Diagnostic only: reasons, never a "sell this player" or
 * "sign this player" verdict. */
export function RiskFactorsCallout({ risk }: { risk: PlayerRiskAssessment | null }) {
  if (!risk || !risk.any_triggered) return null;
  const triggered = risk.reasons.filter((r) => r.triggered);

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-primary-100 bg-white p-6 dark:border-primary-900 dark:bg-[#111a17]">
      <div>
        <h2 className="font-display text-lg font-semibold text-foreground">Risk Factors</h2>
        <p className="mt-1 font-sans text-xs text-foreground/50">
          Independently-computed flags, not a recommendation - see each reason&apos;s own detail.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {triggered.map((r) => {
          const style = riskReasonStyle(r.reason);
          return (
            <div key={r.reason} className={`flex flex-col gap-1 rounded-xl border p-3 ${style.cardClass}`}>
              <span className={`inline-flex w-fit items-center rounded-full px-2 py-0.5 font-sans text-[11px] font-medium ${style.chipClass}`}>
                {r.label}
              </span>
              <p className="font-sans text-sm leading-5 text-foreground/70">{r.detail}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
