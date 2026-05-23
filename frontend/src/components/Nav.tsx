"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowIcon, Brand } from "./Brand";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 backdrop-blur-md transition-colors ${
        scrolled ? "border-b border-line" : "border-b border-transparent"
      }`}
      style={{ background: "color-mix(in oklab, var(--color-bg) 84%, transparent)" }}
    >
      <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-5 md:px-8">
        <Link href="/" aria-label="CrewLoop home">
          <Brand />
        </Link>
        <nav className="hidden gap-7 md:flex" aria-label="Primary">
          <a href="#how" className="text-sm text-ink-2 hover:text-ink">
            How it works
          </a>
          <a href="#who" className="text-sm text-ink-2 hover:text-ink">
            Who it&apos;s for
          </a>
          <a href="#rule" className="text-sm text-ink-2 hover:text-ink">
            Guardrails
          </a>
          <Link href="/dashboard" className="text-sm text-ink-2 hover:text-ink">
            Dashboard
          </Link>
        </nav>
        <a
          href="/home"
          className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-white transition hover:-translate-y-px hover:bg-black"
        >
          Open demo
          <ArrowIcon />
        </a>
      </div>
    </header>
  );
}
