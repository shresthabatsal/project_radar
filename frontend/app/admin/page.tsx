"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { adminConfig, ApiError, getMeta } from "@/lib/api";
import type { MetaResponse } from "@/lib/types";
import { StatusSection } from "@/components/admin/StatusSection";
import { UploadSection } from "@/components/admin/UploadSection";
import { ModelManagementSection } from "@/components/admin/ModelManagementSection";
import { BacktestSection } from "@/components/admin/BacktestSection";
import { SensitivitySection } from "@/components/admin/SensitivitySection";
import { ConfigSection } from "@/components/admin/ConfigSection";
import { buttonClass, inputClass, errorTextClass } from "@/components/admin/styles";

const TOKEN_STORAGE_KEY = "radar_admin_token";

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaError, setMetaError] = useState(false);

  // Not real auth (per spec) - just carry the token across reloads within
  // this tab so the prompt doesn't reappear on every refresh. Deferred into
  // a microtask (not read synchronously in the effect body) both to satisfy
  // react-hooks/set-state-in-effect and to avoid a hydration mismatch - the
  // server always renders the locked state, sessionStorage only exists
  // client-side.
  useEffect(() => {
    Promise.resolve().then(() => {
      const stored = sessionStorage.getItem(TOKEN_STORAGE_KEY);
      if (stored) setToken(stored);
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    getMeta()
      .then((res) => {
        if (!cancelled) setMeta(res);
      })
      .catch(() => {
        if (!cancelled) setMetaError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleUnlock(e: React.FormEvent) {
    e.preventDefault();
    setChecking(true);
    setAuthError(null);
    try {
      // adminConfig doubles as the token check - any 401 surfaces as an ApiError.
      await adminConfig(tokenInput);
      sessionStorage.setItem(TOKEN_STORAGE_KEY, tokenInput);
      setToken(tokenInput);
    } catch (err) {
      setAuthError(err instanceof ApiError && err.status === 401 ? "Invalid token." : "Couldn't reach the backend.");
    } finally {
      setChecking(false);
    }
  }

  function handleLock() {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setTokenInput("");
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans dark:bg-gray-950">
      <div className="border-b border-gray-300 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <span className="font-mono text-sm font-semibold text-gray-900 dark:text-gray-100">
            Radar Admin
          </span>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/" className="text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100">
              ← Back to site
            </Link>
            {token && (
              <button type="button" onClick={handleLock} className="text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100">
                Lock
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-10">
        {!token ? (
          <form
            onSubmit={handleUnlock}
            className="mx-auto flex max-w-sm flex-col gap-3 rounded border border-gray-300 bg-white p-6 dark:border-gray-700 dark:bg-gray-900"
          >
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Admin token</span>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="X-Admin-Token"
                autoFocus
                className={inputClass}
              />
            </label>
            <button type="submit" disabled={checking || !tokenInput} className={buttonClass}>
              {checking ? "Checking…" : "Unlock"}
            </button>
            {authError && <p className={errorTextClass}>{authError}</p>}
            <p className="text-xs text-gray-400">
              Client-side check only - set via the ADMIN_TOKEN env var on the backend (defaults to
              &ldquo;dev-admin-token&rdquo; locally).
            </p>
          </form>
        ) : metaError ? (
          <p className={errorTextClass}>Couldn&apos;t reach the backend - make sure the API server is running.</p>
        ) : !meta ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
        ) : (
          <div className="flex flex-col gap-6">
            <StatusSection />
            <UploadSection />
            <ModelManagementSection token={token} meta={meta} />
            <BacktestSection token={token} meta={meta} />
            <SensitivitySection token={token} meta={meta} />
            <ConfigSection token={token} />
          </div>
        )}
      </div>
    </div>
  );
}
