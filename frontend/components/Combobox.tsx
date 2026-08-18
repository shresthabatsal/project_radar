"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

type ComboboxProps = {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  emptyOptionLabel?: string;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
};

const inputClass =
  "rounded-lg border border-primary-100 bg-white px-3 py-2 font-sans text-sm text-foreground outline-none ring-primary-400 transition focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-primary-900 dark:bg-[#111a17]";

/** A searchable dropdown over a fixed, already-fetched list of real values -
 * type to narrow, then click/Enter to select. The committed value is always
 * either "" or one of `options`: typing alone never commits arbitrary text,
 * and an unmatched draft reverts to the last valid selection on blur/close,
 * so this can never silently filter on a value that matches nothing. */
export function Combobox({
  value,
  onChange,
  options,
  placeholder,
  emptyOptionLabel = "Any",
  disabled,
  loading,
  className,
}: ComboboxProps) {
  const listId = useId();
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep the draft text in sync when the committed value changes from
  // outside this component (e.g. clearing all filters, or a league change
  // resetting team) - adjusted during render, not an effect, per
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes.
  const [syncedValue, setSyncedValue] = useState(value);
  if (value !== syncedValue) {
    setSyncedValue(value);
    setQuery(value);
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filtered =
    query.trim() === ""
      ? options
      : options.filter((o) => o.toLowerCase().includes(query.trim().toLowerCase()));

  function select(option: string) {
    onChange(option);
    setQuery(option);
    setOpen(false);
    setActiveIndex(-1);
  }

  function clear() {
    onChange("");
    setQuery("");
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % Math.max(filtered.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? filtered.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const chosen = activeIndex >= 0 ? filtered[activeIndex] : filtered[0];
      if (chosen) select(chosen);
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery(value);
    }
  }

  return (
    <div ref={containerRef} className={`relative ${className ?? ""}`}>
      <div className="relative">
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          aria-controls={listId}
          disabled={disabled}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          // Reverts any unmatched typed text back to the last real
          // selection. Option buttons below use onMouseDown+preventDefault
          // so clicking one never fires this blur first - otherwise the
          // revert would race the click and the option would never register.
          onBlur={() => setQuery(value)}
          placeholder={placeholder}
          className={`${inputClass} w-full pr-8`}
        />
        {value && !disabled && (
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={clear}
            aria-label="Clear selection"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-foreground/40 transition hover:text-foreground"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <AnimatePresence>
        {open && !disabled && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-primary-100 bg-white shadow-lg dark:border-primary-900 dark:bg-[#111a17]"
          >
            {loading ? (
              <li className="px-3 py-2 font-sans text-xs text-foreground/50">Loading…</li>
            ) : (
              <>
                <li role="option" aria-selected={value === ""}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={clear}
                    className="w-full px-3 py-2 text-left font-sans text-sm text-foreground/50 transition hover:bg-primary-50 dark:hover:bg-primary-950"
                  >
                    {emptyOptionLabel}
                  </button>
                </li>
                {filtered.length === 0 ? (
                  <li className="px-3 py-2 font-sans text-xs text-foreground/50">No matches.</li>
                ) : (
                  filtered.map((o, i) => (
                    <li key={o} role="option" aria-selected={o === value}>
                      <button
                        type="button"
                        onMouseEnter={() => setActiveIndex(i)}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => select(o)}
                        className={`w-full px-3 py-2 text-left font-sans text-sm transition ${
                          i === activeIndex ? "bg-primary-50 dark:bg-primary-950" : ""
                        } ${o === value ? "font-medium text-primary-700 dark:text-primary-300" : "text-foreground"}`}
                      >
                        {o}
                      </button>
                    </li>
                  ))
                )}
              </>
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
