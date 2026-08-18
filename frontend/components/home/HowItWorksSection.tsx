"use client";

import { motion, type Variants } from "motion/react";

const STEPS = [
  {
    title: "Composite Performance Index",
    body: "Position-relative output, playing-style percentiles, and league strength blended into one number, so players in different leagues land on the same scale.",
  },
  {
    title: "Similarity Search",
    body: "Finds players with the closest statistical profile to one you're scouting, ranked by match score. Four selectable distance methods, mahalanobis by default.",
  },
  {
    title: "Hidden Gem Flags",
    body: "Underpriced-for-output players are flagged automatically and tagged wherever they appear across the app - not a separate list you have to go check.",
  },
  {
    title: "Market Value",
    body: "A trained model estimates what a player is worth from performance and situational data, surfaced as a valuation gap against their real observed value.",
  },
  {
    title: "Moneyball Scoring",
    body: "Blends performance, value-for-wage efficiency, and contract-opportunity leverage into one score for prioritizing targets, not ranking them for you.",
  },
  {
    title: "Squad Profiling",
    body: "Starts from a team's roster instead of a named player - depth, age curve, contract cliffs, and style variety, each flagged where it's thin.",
  },
  {
    title: "On-Pitch Impact",
    body: "How a team performs with a player on versus off the pitch - a separate signal from their individual output stats, not a substitute for them.",
  },
  {
    title: "Style & Role Clustering",
    body: "Groups players into playing-style archetypes within their position, so you can search by role instead of just by raw stats.",
  },
  {
    title: "High-Risk Flags",
    body: "Contract, mileage, financial, and sell-high risk are tracked separately and surfaced together, so a squad's exposure is never hiding behind one score.",
  },
] as const;

const container: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12 },
  },
};

const item: Variants = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" },
  },
};

export function HowItWorksSection() {
  return (
    <section className="border-t border-primary-100 bg-primary-50/40 px-6 py-24 dark:border-primary-900 dark:bg-primary-950/20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-foreground">
            How it works
          </h2>
          <p className="mt-4 font-sans text-base leading-7 text-foreground/70">
            Player-level and squad-level layers of statistical evidence to build a shortlist
            from - decision support, not an automated recommendation engine. Nothing here
            replaces judgment; it just makes the judgment faster to reach.
          </p>
        </div>

        <motion.ol
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={container}
          className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
        >
          {STEPS.map((step, i) => (
            <motion.li
              key={step.title}
              variants={item}
              className="flex flex-col gap-3 rounded-2xl border border-primary-100 bg-white p-6 shadow-sm dark:border-primary-900 dark:bg-[#111a17]"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-500 font-display text-sm font-semibold text-white">
                {i + 1}
              </span>
              <h3 className="font-display text-base font-semibold text-foreground">{step.title}</h3>
              <p className="font-sans text-sm leading-6 text-foreground/65">{step.body}</p>
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}
