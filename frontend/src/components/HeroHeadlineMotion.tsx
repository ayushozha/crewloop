"use client";

import { motion, useReducedMotion } from "framer-motion";

const LINES = [
  ["CrewLoop", "is", "the"],
  ["action", "OS", "for", "small"],
  ["business."],
] as const;

export function HeroHeadlineMotion() {
  const reduceMotion = useReducedMotion();
  const initial = reduceMotion ? "visible" : "hidden";

  return (
    <motion.h1
      aria-label="CrewLoop is the action OS for small business."
      className="font-display relative mx-auto mb-6 max-w-[18ch] overflow-visible text-center text-[46px] leading-[0.98] tracking-normal text-ink sm:text-[64px] md:text-[84px] lg:text-[98px]"
      initial={initial}
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: 0.055,
            delayChildren: 0.08,
          },
        },
      }}
    >
      <span aria-hidden="true" className="relative z-10 block">
        {LINES.map((line, lineIndex) => (
          <span key={line.join("-")} className="block sm:whitespace-nowrap">
            {line.map((word, wordIndex) => {
              const isAccent = word === "action" || word === "OS";
              const wordClass = [
                "inline-block",
                word === "action" ? "text-accent" : "",
                isAccent ? "relative" : "",
              ].filter(Boolean).join(" ");
              return (
                <motion.span
                  key={`${lineIndex}-${word}`}
                  className={wordClass}
                  variants={{
                    hidden: {
                      opacity: 0,
                      y: 24,
                      filter: "blur(8px)",
                    },
                    visible: {
                      opacity: 1,
                      y: 0,
                      filter: "blur(0px)",
                      transition: {
                        duration: 0.72,
                        ease: [0.22, 1, 0.36, 1],
                      },
                    },
                  }}
                >
                  {word}
                  {isAccent && (
                    <motion.span
                      aria-hidden="true"
                      className="absolute inset-x-0 bottom-[0.08em] -z-10 h-[0.22em] rounded-full bg-accent-soft"
                      initial={{ scaleX: 0, opacity: 0 }}
                      animate={{ scaleX: 1, opacity: 0.85 }}
                      transition={{
                        duration: reduceMotion ? 0 : 0.7,
                        delay: reduceMotion ? 0 : 0.7,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      style={{ transformOrigin: "left center" }}
                    />
                  )}
                  {wordIndex < line.length - 1 ? "\u00a0" : null}
                </motion.span>
              );
            })}
          </span>
        ))}
      </span>
      <motion.span
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[78%] w-[86%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(62,124,78,0.12),transparent)]"
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduceMotion ? 0 : 1, ease: [0.22, 1, 0.36, 1] }}
      />
    </motion.h1>
  );
}
