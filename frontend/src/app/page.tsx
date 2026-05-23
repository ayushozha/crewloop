import Link from "next/link";

import { ArrowIcon, BrandMark } from "@/components/Brand";
import { HeroHeadlineMotion } from "@/components/HeroHeadlineMotion";
import { HeroSubcopyMotion } from "@/components/HeroSubcopyMotion";
import { Nav } from "@/components/Nav";

const LOOP_STEPS = [
  {
    n: "01 · Intake",
    title: "Turn the request into work.",
    body: "Chat or SMS becomes structured: what is needed, where, by when, budget, urgency, and the one missing detail if clarification is required.",
  },
  {
    n: "02 · Source",
    title: "Check the outside source.",
    body: "Browser Use reads staffing pages, vendor portals, or event briefs, then saves screenshot and source evidence before the agent acts.",
  },
  {
    n: "03 · Match",
    title: "Choose the right operator.",
    body: "Rank contractors by skill, availability, distance, reliability, rate, and memory. For vendors, use the same loop to pick the approved source.",
  },
  {
    n: "04 · Reach out",
    title: "Use the right channel.",
    body: "Text first, call when the shift is urgent, email vendors for invoices or confirmations, and log every response.",
  },
  {
    n: "05 · Commit",
    title: "Lock the plan once someone says yes.",
    body: "Create the schedule, reserve the item, attach the invoice, and send confirmations so the owner can see exactly what changed.",
  },
  {
    n: "06 · Money",
    title: "Hold or release payment with rules.",
    body: "Sponge and Stripe state tracks caps, proof required, owner approval, receipts, and blocked releases.",
  },
  {
    n: "07 · Proof",
    title: "Collect evidence before closing.",
    body: "SMS check-in, photo, source screenshot, timesheet, or manager approval becomes part of the audit trail.",
  },
  {
    n: "08 · Learn",
    title: "Make the next operation easier.",
    body: "Response speed, reliability, vendor notes, and source evidence become memory for the next request.",
  },
] as const;

const INDUSTRIES = [
  "Event operators",
  "Catering",
  "Venue teams",
  "Cleaning crews",
  "Moving crews",
  "Mobile services",
  "Photographers & production",
  "Hospitality teams",
  "Security staffing",
  "Field service operators",
] as const;

export default function HomePage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <HowItWorks />
        <WhoItsFor />
        <PaymentRule />
        <ClosingCta />
      </main>
      <Footer />
    </>
  );
}

/* -------------------------------- Hero ---------------------------------- */

function Hero() {
  return (
    <section className="px-5 md:px-8 pt-9 md:pt-16 pb-7">
      <div className="mx-auto max-w-[1180px]">
        <div className="mb-7 flex items-center justify-center gap-2.5">
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-accent dot-pulse" aria-hidden />
          <span className="eyebrow">Small business action OS · 2-minute dispatch demo</span>
        </div>

        <HeroHeadlineMotion />
        <HeroSubcopyMotion />

        <div className="flex flex-wrap items-center justify-center gap-3">
          <a
            href="/home"
            className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-white transition hover:-translate-y-px hover:bg-black"
          >
            Open demo flow
            <ArrowIcon />
          </a>
          <a
            href="#how"
            className="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2.5 text-sm font-medium text-ink transition hover:-translate-y-px hover:border-ink"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
              <circle cx="6" cy="6" r="5.2" stroke="currentColor" strokeWidth="1.3" />
              <path d="M5 4l3 2-3 2V4Z" fill="currentColor" />
            </svg>
            See the loop
          </a>
        </div>

        <HeroScene />
      </div>
    </section>
  );
}

function HeroScene() {
  return (
    <div
      className="relative mt-12 md:mt-[72px] overflow-hidden rounded-3xl border border-line p-3.5 pb-9 md:px-6 md:pt-12 md:pb-14"
      style={{
        background:
          "radial-gradient(800px 200px at 50% 0%, #EEEAE0 0%, transparent 60%), var(--color-panel)",
      }}
    >
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-[1fr_1.05fr_1fr] items-stretch max-w-[440px] md:max-w-none mx-auto">
        <SmsCard />
        <MatchCard />
        <TimelineCard />
      </div>
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[14px] border border-line bg-white p-[18px] shadow-[0_1px_0_rgba(22,20,16,0.02),0_10px_24px_-16px_rgba(22,20,16,0.18)] ${className}`}
    >
      {children}
    </div>
  );
}

function SmsCard() {
  return (
    <Card className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between border-b border-line-2 pb-2.5 text-xs text-muted">
        <span className="flex items-center gap-2">
          <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-[#E5E0D2] text-[10px] font-semibold text-[#5B5648]">
            BE
          </span>
          Bay Events Co.
        </span>
        <span className="font-mono text-[10.5px] tracking-wider">5:42 PM</span>
      </div>

      <div className="max-w-[88%] self-start rounded-2xl rounded-bl-md bg-[#F0EDE3] px-3.5 py-2.5 text-[14px] leading-snug text-ink">
        Need a bartender tonight 6–10 PM in SoMa. Source page has the shift details. Pay $120.
        <span className="ml-1.5 inline-flex items-center gap-1 rounded-full bg-urgent-soft px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-urgent">
          ● Urgent
        </span>
      </div>
      <div className="max-w-[88%] self-end rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-[14px] leading-snug text-panel">
        On it. Importing source evidence and ranking 4 bartenders within 3 miles.
      </div>
      <div className="max-w-[88%] self-end rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-[14px] leading-snug text-panel">
        Emma looks best — 98% reliability, available, $30/hr. Texting now, calling in 90s if no reply.
      </div>
      <div className="inline-flex gap-1 self-start rounded-2xl rounded-bl-md bg-[#F0EDE3] px-3 py-2.5" aria-label="Typing">
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" />
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" style={{ animationDelay: "0.15s" }} />
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" style={{ animationDelay: "0.3s" }} />
      </div>
    </Card>
  );
}

interface MatchRow {
  initial: string;
  name: string;
  meta: string;
  pill: string;
  variant: "featured" | "default";
  pillVariant: "green" | "dim";
  avAccent?: boolean;
}

const MATCH_ROWS: MatchRow[] = [
  { initial: "E", name: "Emma Carter", meta: "2.1 mi · 98% reliable · $30/hr", pill: "Texting", variant: "featured", pillVariant: "green", avAccent: true },
  { initial: "M", name: "Madison Reed", meta: "3.4 mi · 61% reliable · $28/hr", pill: "Backup", variant: "default", pillVariant: "dim" },
  { initial: "A", name: "Ashley Brooks", meta: "Guest service · partial match", pill: "Partial", variant: "default", pillVariant: "dim" },
  { initial: "L", name: "Luis Romero", meta: "Moving crew · skill mismatch", pill: "Skipped", variant: "default", pillVariant: "dim" },
];

function MatchCard() {
  return (
    <Card>
      <div className="mb-3.5 flex items-center justify-between">
        <h4 className="m-0 flex items-center gap-2 text-[13px] font-medium text-ink">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
            <circle cx="7" cy="7" r="5.2" stroke="currentColor" strokeWidth="1.4" />
            <path d="M5 7l1.4 1.4L9.2 5.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Matched 4 contractors
        </h4>
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted">Re-ranked · 2s</span>
      </div>

      {MATCH_ROWS.map((row, i) => (
        <div
          key={row.name}
          className={`${
            row.variant === "featured"
              ? "grid grid-cols-[28px_1fr_auto] gap-3 items-center -mx-2 rounded-[10px] border border-[rgba(62,124,78,0.22)] bg-accent-soft p-3"
              : "grid grid-cols-[28px_1fr_auto] gap-3 items-center py-3 px-1 border-b border-line-2"
          } ${i === MATCH_ROWS.length - 1 && row.variant !== "featured" ? "border-b-0" : ""}`}
        >
          <div
            className={`grid h-7 w-7 place-items-center rounded-full text-[11px] font-semibold ${
              row.avAccent ? "bg-[#D7E5D8] text-[#2C5638]" : "bg-[#E5E0D2] text-[#5B5648]"
            }`}
          >
            {row.initial}
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-[14px] font-medium text-ink">{row.name}</span>
            <span className="font-mono text-[11.5px] tracking-tight text-muted">{row.meta}</span>
          </div>
          <span
            className={`whitespace-nowrap rounded-full px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider ${
              row.pillVariant === "green" ? "bg-accent text-panel" : "bg-[#F0EDE3] text-muted"
            }`}
          >
            {row.pill}
          </span>
        </div>
      ))}
    </Card>
  );
}

interface TimelineRow {
  state: "done" | "live" | "pending";
  text: React.ReactNode;
  time: string;
}

const TIMELINE_ROWS: TimelineRow[] = [
  { state: "done", text: <><b className="font-medium text-ink">Source imported</b> · Bay Events shift page</>, time: "5:42" },
  { state: "done", text: <><b className="font-medium text-ink">Request parsed</b> · bartender, SoMa, $120</>, time: "5:42" },
  { state: "done", text: <><b className="font-medium text-ink">Emma texted</b> · top match</>, time: "5:43" },
  { state: "done", text: <><b className="font-medium text-ink">Call placed</b> · urgent escalation</>, time: "5:44" },
  { state: "live", text: <><b className="font-medium text-ink">Confirming shift</b> with Emma…</>, time: "5:45" },
  { state: "pending", text: <span className="text-muted">Payment hold · $120</span>, time: "—" },
];

function TimelineCard() {
  return (
    <Card>
      <div className="mb-3.5 flex items-center justify-between">
        <h4 className="m-0 flex items-center gap-2 text-[13px] font-medium text-ink">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
            <circle cx="7" cy="7" r="5.2" stroke="currentColor" strokeWidth="1.4" />
            <path d="M7 4v3.2l2 1.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          Dispatch timeline
        </h4>
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted">Live</span>
      </div>

      <div className="flex flex-col">
        {TIMELINE_ROWS.map((row, i) => (
          <div
            key={i}
            className="relative grid grid-cols-[22px_1fr_auto] items-center gap-2.5 py-2.5"
          >
            {i < TIMELINE_ROWS.length - 1 && (
              <span className="absolute left-[10px] top-[18px] bottom-[-10px] w-[1.5px] bg-line" />
            )}
            <TimelineDot state={row.state} />
            <span className="text-[13.5px] text-ink-2">{row.text}</span>
            <span className="font-mono text-[11px] text-muted">{row.time}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function TimelineDot({ state }: { state: TimelineRow["state"] }) {
  if (state === "done") {
    return (
      <span className="relative z-10 grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-accent bg-accent">
        <span
          className="block h-1 w-[7px]"
          style={{
            borderLeft: "1.5px solid #fff",
            borderBottom: "1.5px solid #fff",
            transform: "rotate(-45deg) translate(0px,-1px)",
          }}
        />
      </span>
    );
  }
  if (state === "live") {
    return (
      <span className="tl-pulse relative z-10 grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-accent bg-white" />
    );
  }
  return (
    <span className="relative z-10 grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-line bg-white" />
  );
}

/* ----------------------------- How it works ----------------------------- */

function HowItWorks() {
  return (
    <section id="how" className="border-t border-line-2 py-16 md:py-24 px-5 md:px-8">
      <div className="mx-auto max-w-[1180px]">
        <div className="mb-12 grid max-w-[760px] gap-3.5">
          <span className="eyebrow">The loop</span>
          <h2 className="font-display text-[clamp(34px,4.6vw,56px)] leading-[1.02] tracking-tight">
            One request in. <em className="not-italic italic text-accent">A verified action out.</em>
          </h2>
          <p className="max-w-[56ch] text-[17px] leading-relaxed text-ink-2">
            CrewLoop is intentionally one loop, not a pile of apps. The same primitives handle urgent staffing today
            and later support vendor emails, inventory purchases, invoices, payments, proof, and final reports.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-[18px] sm:grid-cols-2 lg:grid-cols-4">
          {LOOP_STEPS.map((step) => (
            <div
              key={step.n}
              className="flex min-h-[180px] flex-col justify-between gap-4 rounded-[14px] border border-line bg-panel p-5 transition hover:-translate-y-0.5 hover:border-[rgba(22,20,16,0.2)]"
            >
              <span className="font-mono text-[11px] tracking-widest text-muted">{step.n}</span>
              <h3 className="font-display m-0 text-[24px] leading-[1.1] tracking-tight">{step.title}</h3>
              <p className="m-0 text-[13.5px] leading-relaxed text-ink-2">{step.body}</p>
            </div>
          ))}
        </div>

        <QuoteStrip />
      </div>
    </section>
  );
}

function QuoteStrip() {
  return (
    <div className="mt-12 grid grid-cols-1 items-center gap-8 rounded-[14px] bg-ink p-6 md:grid-cols-[1.2fr_1fr] md:p-8 text-[#F0EDE3]">
      <div>
          <div className="font-display text-[clamp(22px,2.4vw,30px)] leading-[1.25] tracking-tight">
          &ldquo;Need a bartender tonight 6–10 PM in SoMa. Source page has the event details. Pay{" "}
          <span className="font-display text-accent text-[1.1em]">$120</span>. Urgent.&rdquo;
        </div>
        <div className="mt-3.5 font-mono text-[11px] uppercase tracking-widest text-[#8C887D]">
          — One owner request · enough context to start the operation
        </div>
      </div>
      <div className="flex flex-col gap-2.5">
        {[
          ["00:02", "Browser source captured"],
          ["00:05", "4 contractors ranked, Emma selected"],
          ["00:18", "SMS sent to Emma · call queued"],
          ["01:42", "Emma confirmed · shift locked"],
          ["22:07", "Proof received · $120 released"],
        ].map(([t, v]) => (
          <div
            key={t}
            className="flex items-center gap-2.5 rounded-[10px] border border-white/10 bg-white/5 px-3.5 py-2.5 text-[13.5px]"
          >
            <span className="min-w-[62px] font-mono text-[11px] uppercase tracking-wider text-[#A8A493]">{t}</span>
            <span className="text-[#F0EDE3]">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------- Who it's for ----------------------------- */

function WhoItsFor() {
  return (
    <section id="who" className="border-t border-line-2 py-16 md:py-24 px-5 md:px-8">
      <div className="mx-auto max-w-[1180px]">
        <div className="mb-12 max-w-[760px] grid gap-3.5">
          <span className="eyebrow">Built for</span>
          <h2 className="font-display text-[clamp(34px,4.6vw,56px)] leading-[1.02] tracking-tight">
            Businesses that run through <em className="not-italic italic text-accent">texts, tabs, emails, and payments.</em>
          </h2>
          <p className="max-w-[56ch] text-[17px] leading-relaxed text-ink-2">
            Use it where the owner needs action, not another dashboard: staff an event, ask a vendor for an invoice,
            order supplies, confirm proof, and release payment from one audited timeline.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          {INDUSTRIES.map((label) => (
            <span
              key={label}
              className="rounded-full border border-line bg-panel px-4 py-2.5 text-sm text-ink-2 transition hover:border-ink hover:bg-ink hover:text-panel"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------------------- Guardrails -------------------------------- */

function PaymentRule() {
  return (
    <section id="rule" className="border-t border-line-2 py-16 md:py-24 px-5 md:px-8">
      <div className="mx-auto max-w-[1180px]">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.05fr_1fr] items-stretch">
          <div>
            <span className="eyebrow">Actions with guardrails</span>
            <h3 className="font-display mt-3.5 text-[clamp(28px,3.4vw,40px)] leading-[1.05] tracking-tight">
              Calls, emails, browser actions, and payments stay accountable.
            </h3>
            <p className="mt-4 max-w-[48ch] text-base leading-relaxed text-ink-2">
              Every operation creates a timeline with source evidence, messages, approvals, and payment state. The
              agent can move fast, but releases are capped and conditional.
            </p>
            <p className="mt-4 max-w-[48ch] text-base leading-relaxed text-ink-2">
              Missing proof? Wrong person checked in? Unapproved vendor invoice? The release is blocked and the owner
              sees why.
            </p>
            <div className="mt-2 flex flex-wrap gap-3">
              <a
                href="/home"
                className="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2.5 text-sm font-medium text-ink transition hover:-translate-y-px hover:border-ink"
              >
                Open the live workflow
                <ArrowIcon />
              </a>
            </div>
          </div>

          <RuleCard />
        </div>
      </div>
    </section>
  );
}

function RuleCard() {
  return (
    <div
      className="relative flex flex-col gap-4 overflow-hidden rounded-[14px] border border-line bg-panel p-6"
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(400px 100px at 100% 0%, rgba(62,124,78,0.08), transparent 60%)" }}
      />
      <div className="relative flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-wider text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Released · 22:08
        </span>
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted">JOB #4218 · EMMA C.</span>
      </div>

      <div className="relative flex items-baseline justify-between gap-2 border-b border-line-2 pb-3.5">
        <span className="font-display text-[56px] leading-none tracking-[-0.03em]">
          $120<span className="ml-2 text-[0.32em] tracking-wider text-muted">.00</span>
        </span>
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Bartender · 4hr shift</span>
      </div>

      <div className="relative flex flex-col gap-2.5">
        {[
          ["Contractor accepted the shift", "17:45"],
          ["Contractor checked in on location", "17:58"],
          ["Proof submitted & verified", "22:04"],
          ["Owner approved completion", "22:07"],
        ].map(([label, time]) => (
          <div key={label} className="grid grid-cols-[20px_1fr_auto] items-center gap-3 py-1.5 text-sm text-ink-2">
            <span className="grid h-[18px] w-[18px] place-items-center rounded-md bg-accent">
              <span
                className="block h-1 w-[7px]"
                style={{
                  borderLeft: "1.5px solid #fff",
                  borderBottom: "1.5px solid #fff",
                  transform: "rotate(-45deg) translate(0,-1px)",
                }}
              />
            </span>
            <span>{label}</span>
            <span className="rounded-full bg-[#F0EDE3] px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider text-muted">
              {time}
            </span>
          </div>
        ))}
      </div>

      <div className="relative flex items-center justify-between border-t border-line-2 pt-3.5 text-[12.5px] text-muted">
        <span>Receipt #R-4218 · Sponge + Stripe</span>
        <span className="font-mono">payment.released</span>
      </div>
    </div>
  );
}

/* ----------------------------- Closing CTA ------------------------------ */

function ClosingCta() {
  return (
    <section id="cta" className="border-t border-line-2 py-16 md:py-24 px-5 md:px-8 pb-8">
      <div className="mx-auto max-w-[1180px]">
        <div className="grid grid-cols-1 items-end gap-8 rounded-3xl border border-line bg-panel p-10 md:p-16 md:grid-cols-[1.2fr_auto]">
          <h2 className="font-display m-0 max-w-[18ch] text-[clamp(34px,4.4vw,56px)] leading-[1.0] tracking-tight">
            Stop juggling texts, tabs, and payments. <em className="not-italic italic text-accent">Run one action loop.</em>
          </h2>
          <div className="flex flex-col items-start gap-2.5 md:items-end">
            <a
              href="/home"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3.5 text-[15px] font-medium text-white transition hover:-translate-y-px hover:bg-black"
            >
              Open demo flow
              <ArrowIcon />
            </a>
            <small className="text-[13px] text-muted">
              Start from the operator home, then move through chat, dispatch, supplies, proof, and payment.
            </small>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------- Footer -------------------------------- */

function Footer() {
  return (
    <footer className="border-t border-line-2 px-5 md:px-8 py-12 pb-16 text-[13px] text-muted">
      <div className="mx-auto max-w-[1180px] flex flex-wrap items-end justify-between gap-8">
        <div>
          <div className="mb-2 flex items-center gap-2.5 font-medium">
            <BrandMark />
            <b className="text-[17px] font-medium text-ink">CrewLoop</b>
          </div>
          <div className="max-w-[34ch]">The action layer for small business operations. © 2026 CrewLoop, Inc.</div>
        </div>
        <div className="flex flex-wrap gap-12">
          <div>
            <b className="mb-2.5 block text-[13px] font-medium text-ink">Product</b>
            <a href="#how" className="block mb-1.5 text-ink-2 hover:text-ink">How it works</a>
            <a href="#rule" className="block mb-1.5 text-ink-2 hover:text-ink">Action guardrails</a>
            <a href="#who" className="block mb-1.5 text-ink-2 hover:text-ink">Industries</a>
            <Link href="/dashboard" className="block mb-1.5 text-ink-2 hover:text-ink">Dashboard</Link>
          </div>
          <div>
            <b className="mb-2.5 block text-[13px] font-medium text-ink">Company</b>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">About</a>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">Careers</a>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">Contact</a>
          </div>
          <div>
            <b className="mb-2.5 block text-[13px] font-medium text-ink">Legal</b>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">Terms</a>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">Privacy</a>
            <a href="#" className="block mb-1.5 text-ink-2 hover:text-ink">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
