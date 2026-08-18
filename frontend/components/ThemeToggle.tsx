"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "radar-theme";

/** Reads the class already applied by the blocking init script in
 * app/layout.tsx (which runs before hydration) so this never has to guess -
 * avoids a hydration-mismatch flash where the button's initial icon doesn't
 * match the theme the page actually rendered in. */
function currentTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Manual light/dark toggle, present in the header on every page. Defaults
 * to light for a first-time visitor regardless of OS preference (see the
 * init script in app/layout.tsx) and persists the choice to localStorage so
 * it survives navigation and future visits within the same browser. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Sync from the DOM after mount. Deliberately an effect, not a lazy
  // useState initializer: the server always renders "light" (no `document`
  // to read), so if the client's first render read the real DOM state
  // directly it would compute "dark" whenever that's the stored theme -
  // producing a genuine hydration mismatch (different icon/aria-label) since
  // it's synchronizing with a browser-only external system (the class the
  // beforeInteractive script already applied), the sanctioned use of an
  // effect per the set-state-in-effect rule's own guidance.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(currentTheme());
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage unavailable (private browsing, disabled storage) - the
      // toggle still works for the current page, it just won't persist.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      aria-pressed={theme === "dark"}
      className="flex h-8 w-8 items-center justify-center rounded-full text-foreground/60 transition hover:bg-primary-50 hover:text-primary-600 dark:hover:bg-primary-950 dark:hover:text-primary-400"
    >
      {theme === "dark" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4.5 w-4.5">
          <circle cx="12" cy="12" r="4" />
          <path
            strokeLinecap="round"
            d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4.5 w-4.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
        </svg>
      )}
    </button>
  );
}
