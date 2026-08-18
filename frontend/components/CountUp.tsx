"use client";

import { useEffect, useState } from "react";
import { animate } from "motion/react";

type CountUpProps = {
  value: number;
  duration?: number;
  decimals?: number;
  /** Overrides the default toFixed(decimals) formatting - e.g. for currency. */
  format?: (n: number) => string;
  className?: string;
};

/** Radar's shared "headline number" treatment: briefly counts up from 0 to
 * its final value on mount/change, rather than appearing instantly. Used
 * consistently for composite index, market value, and moneyball score. */
export function CountUp({ value, duration = 1, decimals = 1, format, className }: CountUpProps) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const controls = animate(0, value, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [value, duration]);

  const text = format ? format(display) : display.toFixed(decimals);
  return <span className={className}>{text}</span>;
}
