"use client";

import { useState } from "react";
import { getStatus } from "@/lib/api";
import { useAsyncData } from "@/lib/hooks";
import { formatLastUpdated } from "@/lib/format";
import { panelClass, headingClass, buttonClass, labelClass, errorTextClass } from "./styles";

export function StatusSection() {
  const [refreshKey, setRefreshKey] = useState(0);
  // getStatus() takes no args, so refreshKey only needs to be an effect
  // dependency (to force a re-fetch on click) - not referenced in the
  // fetcher body itself, hence no useCallback here.
  const { data, loading, error } = useAsyncData(() => getStatus(), [refreshKey], "Couldn't load status.");

  return (
    <section className={panelClass}>
      <div className="flex items-center justify-between">
        <h2 className={headingClass}>Data Status</h2>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={loading}
          className={buttonClass}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}

      {data && (
        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <dt className={labelClass}>Player rows</dt>
            <dd className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {data.player_rows.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className={labelClass}>Supplementary rows</dt>
            <dd className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {data.supplementary_rows.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className={labelClass}>Last updated</dt>
            <dd className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {data.last_updated ? formatLastUpdated(data.last_updated) : "—"}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
