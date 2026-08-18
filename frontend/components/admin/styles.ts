// Deliberately plain, neutral-gray styling - the admin panel is a utility
// surface, not a branded page (see app/admin/page.tsx and Header.tsx, which
// hides the logo/nav entirely on this route). No primary-blue, no
// font-display, no rounded-2xl cards - just enough structure to be usable.

export const panelClass =
  "rounded border border-gray-300 bg-white p-5 dark:border-gray-700 dark:bg-gray-900";

export const inputClass =
  "rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 outline-none focus:border-gray-500 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100";

export const buttonClass =
  "rounded border border-gray-400 bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-800 transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700";

export const labelClass = "text-xs font-medium text-gray-500 dark:text-gray-400";

// font-sans overrides globals.css's blanket h1-h6 { font-family: var(--font-display) }
// rule (a class selector beats a tag selector) - this page is deliberately
// plain, not the branded Space Grotesk headline treatment used elsewhere.
export const headingClass = "font-sans text-base font-semibold text-gray-900 dark:text-gray-100";

export const tableClass = "w-full border-collapse text-sm";

export const thClass =
  "border-b border-gray-300 px-2 py-1.5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400";

export const tdClass =
  "border-b border-gray-200 px-2 py-1.5 text-gray-800 dark:border-gray-800 dark:text-gray-200";

export const errorTextClass = "text-sm text-red-600 dark:text-red-400";
