export function GemBadge({ className }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-primary-50 px-2 py-0.5 font-sans text-[11px] font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300 ${className ?? ""}`}
    >
      <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2L2 9l10 13L22 9 12 2z" />
      </svg>
      Gem
    </span>
  );
}
