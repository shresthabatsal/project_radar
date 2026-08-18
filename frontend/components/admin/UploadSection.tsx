"use client";

import { useState } from "react";
import { ApiError, uploadSnapshot } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";
import { panelClass, headingClass, buttonClass, labelClass, errorTextClass } from "./styles";

export function UploadSection() {
  const [playersFile, setPlayersFile] = useState<File | null>(null);
  const [supplementaryFile, setSupplementaryFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!playersFile && !supplementaryFile) {
      setError("Choose at least one CSV file.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadSnapshot({
        players: playersFile ?? undefined,
        supplementary: supplementaryFile ?? undefined,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className={panelClass}>
      <h2 className={headingClass}>Upload Data Snapshot</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Replaces the players table, the supplementary table, or both - upload either file on its
        own. Takes effect immediately, in place.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end">
        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Players CSV</span>
          <input
            type="file"
            accept=".csv,.csv.gz"
            onChange={(e) => setPlayersFile(e.target.files?.[0] ?? null)}
            className="text-sm text-gray-700 dark:text-gray-300"
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>Supplementary CSV</span>
          <input
            type="file"
            accept=".csv,.csv.gz"
            onChange={(e) => setSupplementaryFile(e.target.files?.[0] ?? null)}
            className="text-sm text-gray-700 dark:text-gray-300"
          />
        </label>

        <button type="submit" disabled={submitting} className={buttonClass}>
          {submitting ? "Uploading…" : "Upload"}
        </button>
      </form>

      {error && <p className={`mt-3 ${errorTextClass}`}>{error}</p>}

      {result && (
        <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">
          {result.ok ? (
            <>
              Uploaded.
              {result.player_rows != null && ` ${result.player_rows.toLocaleString()} player rows.`}
              {result.supplementary_rows != null &&
                ` ${result.supplementary_rows.toLocaleString()} supplementary rows.`}
              {" "}Refresh Data Status above to see the new counts.
            </>
          ) : (
            result.error ?? "No file provided."
          )}
        </p>
      )}
    </section>
  );
}
