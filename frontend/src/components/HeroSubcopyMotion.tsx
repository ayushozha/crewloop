"use client";

import { motion, useReducedMotion } from "framer-motion";

type Segment = {
  text: string;
  tone?: "strong" | "accent";
};

const SEGMENTS: Segment[] = [
  { text: "Give CrewLoop one event request. ", tone: "strong" },
  { text: "It imports the source, builds the plan, " },
  { text: "texts or calls", tone: "accent" },
  { text: " the right people, sends emails, tracks payment holds, captures proof, and leaves a clean audit trail." },
];

export function HeroSubcopyMotion() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.p
      className="mx-auto mb-9 max-w-[58ch] text-center text-[clamp(17px,1.55vw,20px)] leading-[1.55] text-ink-2"
      initial={reduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.62, delay: reduceMotion ? 0 : 0.44, ease: [0.22, 1, 0.36, 1] }}
    >
      {SEGMENTS.map((segment, index) => (
        <motion.span
          key={`${index}-${segment.text}`}
          className={
            segment.tone === "strong"
              ? "font-medium text-ink"
              : segment.tone === "accent"
                ? "relative inline-block font-medium text-accent"
                : undefined
          }
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: reduceMotion ? 0 : 0.48,
            delay: reduceMotion ? 0 : 0.52 + index * 0.06,
            ease: [0.22, 1, 0.36, 1],
          }}
        >
          {segment.text}
          {segment.tone === "accent" && (
            <motion.span
              aria-hidden="true"
              className="absolute inset-x-0 bottom-[0.08em] -z-10 h-[0.36em] rounded-full bg-accent-soft"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: reduceMotion ? 0 : 0.52, delay: reduceMotion ? 0 : 0.82, ease: [0.22, 1, 0.36, 1] }}
              style={{ transformOrigin: "left center" }}
            />
          )}
        </motion.span>
      ))}
    </motion.p>
  );
}
