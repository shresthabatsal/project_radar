"use client";

import { useCallback } from "react";
import { adminConfig } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import type { ConfigEntry, ConfigGroup } from "@/lib/types";
import { RadarSweep } from "@/components/RadarSweep";
import { panelClass, headingClass, labelClass, errorTextClass } from "./styles";

// A short explanation reads fine inline; config.py's longer design-
// rationale comments (some run to 3-4 paragraphs - e.g.
// STYLE_CLUSTER_NEGATIVE_WEIGHT's) would otherwise dominate the page, so
// anything past this length collapses behind a <details> instead.
const LONG_EXPLANATION_CHARS = 220;

function formatValue(v: unknown): { text: string; multiline: boolean } {
  if (v === null || v === undefined) return { text: "—", multiline: false };
  if (typeof v === "object") return { text: JSON.stringify(v, null, 2), multiline: true };
  return { text: String(v), multiline: false };
}

function ExplanationText({ text }: { text: string }) {
  if (text.length <= LONG_EXPLANATION_CHARS) {
    return <p className="mt-1 text-xs leading-relaxed text-gray-600 dark:text-gray-400">{text}</p>;
  }
  const preview = text.slice(0, 90).trimEnd();
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300">
        {preview}&hellip; <span className="underline">show full explanation</span>
      </summary>
      <p className="mt-1.5 text-xs leading-relaxed text-gray-600 dark:text-gray-400">{text}</p>
    </details>
  );
}

function ConfigEntryRow({ entry }: { entry: ConfigEntry }) {
  const { text, multiline } = formatValue(entry.value);
  return (
    <div className="border-b border-gray-100 py-2.5 last:border-b-0 dark:border-gray-900">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <code className="font-mono text-xs font-medium text-gray-900 dark:text-gray-100">{entry.name}</code>
        {entry.section && (
          <span className="font-mono text-[10px] uppercase tracking-wide text-gray-400 dark:text-gray-600">
            {entry.section}
          </span>
        )}
      </div>
      {multiline ? (
        <pre className="mt-1 overflow-x-auto rounded border border-gray-200 bg-gray-50 p-2 font-mono text-xs text-gray-800 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-200">
          {text}
        </pre>
      ) : (
        <code className="mt-1 block font-mono text-xs text-primary-700 dark:text-primary-400">{text}</code>
      )}
      {entry.explanation && <ExplanationText text={entry.explanation} />}
    </div>
  );
}

function ConfigGroupPanel({ group, defaultOpen }: { group: ConfigGroup; defaultOpen: boolean }) {
  return (
    <details
      className="rounded border border-gray-300 dark:border-gray-700"
      open={defaultOpen}
    >
      <summary className="cursor-pointer select-none px-3 py-2 font-sans text-sm font-semibold text-gray-900 dark:text-gray-100">
        {group.group}{" "}
        <span className="font-normal text-gray-500 dark:text-gray-400">
          ({group.entries.length} constant{group.entries.length === 1 ? "" : "s"})
        </span>
      </summary>
      <div className="border-t border-gray-200 px-3 py-1 dark:border-gray-800">
        {group.entries.length === 0 ? (
          <p className="py-2 text-xs text-gray-400 dark:text-gray-600">
            No tunable constants in backend/config.py for this area yet.
          </p>
        ) : (
          group.entries.map((entry) => <ConfigEntryRow key={entry.name} entry={entry} />)
        )}
      </div>
    </details>
  );
}

export function ConfigSection({ token }: { token: string }) {
  const fetcher = useCallback(() => adminConfig(token), [token]);
  const { data, loading, error } = useAsyncData(fetcher, [fetcher], "Couldn't load config.");

  return (
    <section className={panelClass}>
      <h2 className={headingClass}>Configuration (backend/config.py)</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Read-only. Every tunable constant currently loaded by the backend, grouped by feature
        area, with its current value and (where config.py&apos;s own comments give it one) its
        explanation - parsed straight from the file on every load, so this can never drift from
        what it actually says.
      </p>
      <p className={`mt-2 ${labelClass}`}>
        No editing here by design - several of these (hyperparameters, feature choices, K
        overrides) only take effect on the next retrain, and editing them without retraining
        would silently desync this view from what a currently-loaded model actually used. Use the
        Model Management section above to retrain, or edit backend/config.py directly and
        retrain from there.
      </p>

      {loading && (
        <div className="mt-6 flex justify-center py-8">
          <RadarSweep label="Loading config" />
        </div>
      )}

      {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}

      {data && (
        <div className="mt-4 flex flex-col gap-2">
          {data.groups.map((group, i) => (
            <ConfigGroupPanel key={group.group} group={group} defaultOpen={i === 0} />
          ))}
        </div>
      )}
    </section>
  );
}
