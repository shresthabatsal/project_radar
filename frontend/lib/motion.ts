import type { Variants } from "motion/react";

// Radar's shared animation language (established Phases 7-9): a radar-sweep
// spinner for anything loading/computing (see components/RadarSweep.tsx),
// staggered list/row entrances, and count-up animations for headline
// numbers. Every list on the site (search results, similar players, gems)
// reuses these exact variants rather than inventing a one-off per page.

export const listContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

export const listItem: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};
