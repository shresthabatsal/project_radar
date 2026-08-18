"use client";

const ROTATE_SECONDS = 6;

// Fixed (not randomized) angle/radius pairs for up to 6 blips -
// deterministic so server and client render the same markup. Purely
// decorative, not tied to real player data.
const BLIP_SLOTS: { angle: number; radius: number }[] = [
  { angle: 18, radius: 42 },
  { angle: 82, radius: 76 },
  { angle: 152, radius: 56 },
  { angle: 205, radius: 90 },
  { angle: 268, radius: 64 },
  { angle: 322, radius: 34 },
];

/**
 * Radar's signature hero motif: concentric rings/grid + a continuously
 * rotating sweep, with scattered blip markers - a quiet background
 * presence behind the search bar, not a competing focal point.
 */
export function RadarHeroVisual() {
  return (
    <div className="relative aspect-square w-[clamp(440px,64vw,780px)]">
      {/* Concentric rings + crosshair/diagonal grid - soft brand tints so
          the grid reads as a screen, not a faded watermark. */}
      <div className="absolute inset-0 rounded-full border border-primary-300/70 dark:border-primary-700/60" />
      <div className="absolute inset-[16%] rounded-full border border-primary-300/55 dark:border-primary-700/45" />
      <div className="absolute inset-[34%] rounded-full border border-primary-300/45 dark:border-primary-700/35" />
      <div className="absolute inset-[54%] rounded-full border border-primary-300/35 dark:border-primary-700/28" />
      <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-primary-300/40 dark:bg-primary-700/30" />
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-primary-300/40 dark:bg-primary-700/30" />
      <div className="absolute left-1/2 top-1/2 h-full w-px -translate-x-1/2 -translate-y-1/2 rotate-45 bg-primary-300/25 dark:bg-primary-700/20" />
      <div className="absolute left-1/2 top-1/2 h-full w-px -translate-x-1/2 -translate-y-1/2 -rotate-45 bg-primary-300/25 dark:bg-primary-700/20" />

      {/* The rotating sweep - dimmer alpha values (globals.css's
          .radar-hero-sweep) so it reads as ambient motion, not a bright
          competing shape. Keeps rotating continuously; nothing depends on its position. */}
      <div
        className="radar-hero-sweep absolute inset-0 rounded-full"
        style={{
          maskImage: "radial-gradient(circle, transparent 6%, black 60%, black 96%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(circle, transparent 6%, black 60%, black 96%, transparent 100%)",
          animation: `radar-hero-spin ${ROTATE_SECONDS}s linear infinite`,
        }}
      />

      <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-500/55 shadow-[0_0_8px_2px_rgba(0,146,88,0.3)]" />

      {/* Blips - plain, statically-visible markers from first paint (no
          per-blip reveal timing, no labels, no player identity). */}
      {BLIP_SLOTS.map(({ angle, radius }, i) => {
        const rad = (angle * Math.PI) / 180;
        const left = 50 + radius * 0.5 * Math.sin(rad);
        const top = 50 - radius * 0.5 * Math.cos(rad);
        return (
          <div
            key={i}
            className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-500/40 shadow-[0_0_5px_1px_rgba(0,146,88,0.25)]"
            style={{ left: `${left}%`, top: `${top}%` }}
          />
        );
      })}
    </div>
  );
}
