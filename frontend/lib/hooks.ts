"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Shared fetch-on-dependency-change pattern for Radar's section components
 * (similarity, market value, moneyball, gems, player profile): loading/
 * error/data state, with a superseded fetch's response guarded out via a
 * generation counter so it can never clobber a newer request's state. All
 * state updates are deferred into the promise chain (never called
 * synchronously in the effect body), per the react-hooks/set-state-in-effect
 * rule that also shaped PlayerSearchBar and the advanced-search page. */
export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  errorMessage = "Something went wrong - try again.",
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });
  const generation = useRef(0);

  useEffect(() => {
    const myGeneration = ++generation.current;

    Promise.resolve()
      .then(() => {
        setState((s) => ({ ...s, loading: true, error: null }));
        return fetcher();
      })
      .then((data) => {
        if (generation.current !== myGeneration) return;
        setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (generation.current !== myGeneration) return;
        setState({ data: null, loading: false, error: err instanceof ApiError ? err.message : errorMessage });
      });
    // deps is caller-controlled, matching useEffect's own contract.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
