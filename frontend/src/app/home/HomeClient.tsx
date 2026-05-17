"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { api } from "@/lib/api";

/* ------------------------------------------------------------------ */
/* Mock data                                                          */
/* ------------------------------------------------------------------ */
/* The Dashboard.html design references an "operations" data shape    */
/* that doesn't exist in the backend yet. Everything below is mock    */
/* data ported verbatim from the prototype so the page reads end-to-  */
/* end. Only the contractor count (sidebar) and the composer submit   */
/* (-> /chat) are wired to real systems.                              */
/* ------------------------------------------------------------------ */

interface LoopStep {
  state: "done" | "live" | "pending";
  title: string;
  detail: string;
  time: string;
}

const FEATURED_LOOP: LoopStep[] = [
  { state: "done", title: "Parsed", detail: "role · time · pay · urgency", time: "5:42" },
  { state: "done", title: "Sourced", detail: "browser-use · venue confirmed", time: "5:42" },
  { state: "done", title: "Texted & called Maya", detail: "top of 11 bartenders", time: "5:44" },
  { state: "done", title: "Scheduled & held $135", detail: "release rule active", time: "5:45" },
  { state: "live", title: "Awaiting check-in", detail: "SMS reminder at 5:55", time: "5:55" },
  { state: "pending", title: "Proof submitted", detail: "photo or QR", time: "—" },
  { state: "pending", title: "Release & receipt", detail: "owner approval", time: "—" },
];

interface FeedEntry {
  ic: "sms" | "call" | "email" | "pay" | "proof" | "browser";
  who: string;
  meta: string;
  time: string;
}

const LIVE_FEED: FeedEntry[] = [
  { ic: "call", who: "Called Maya · 42s", meta: "OP-4218 · accepted at $135", time: "5:45" },
  { ic: "sms", who: "Texted Maya", meta: "SoMa · 4hr · $135 flat", time: "5:43" },
  { ic: "browser", who: "Imported Bay Events brief", meta: "browser-use · 4 pages · verified host", time: "5:42" },
  { ic: "email", who: "Emailed Sutro Catering", meta: "OP-4211 · invoice confirmation", time: "5:21" },
  { ic: "pay", who: "Released $156 to Luis", meta: "OP-4209 · proof verified", time: "4:58" },
  { ic: "proof", who: "Proof photo verified", meta: "OP-4209 · server setup, Pier 39", time: "4:54" },
];

interface PipelineOp {
  id: string;
  title: string;
  progress: number;
  progressTone?: "accent" | "amber" | "urgent";
  meta: string;
  stampTone?: "muted" | "live" | "urgent" | "blue";
}

const PIPELINE: { label: string; items: PipelineOp[] }[] = [
  {
    label: "Parsing",
    items: [
      {
        id: "OP-4221",
        title: "2 servers for Friday catering, $25/hr each",
        progress: 14,
        meta: "just now",
        stampTone: "live",
      },
    ],
  },
  {
    label: "Sourcing",
    items: [
      {
        id: "OP-4220",
        title: "Order ice + 200 cups by Fri 4pm, cap $80",
        progress: 32,
        progressTone: "amber",
        meta: "3m",
        stampTone: "blue",
      },
    ],
  },
  {
    label: "Contacting",
    items: [
      {
        id: "OP-4211",
        title: "Confirm May 24 invoice — Sutro Catering",
        progress: 55,
        meta: "21m",
        stampTone: "blue",
      },
    ],
  },
  {
    label: "In progress",
    items: [
      {
        id: "OP-4218",
        title: "Bartender · Bay Events SoMa · 4hr",
        progress: 72,
        progressTone: "urgent",
        meta: "Maya · 5:45",
        stampTone: "urgent",
      },
      {
        id: "OP-4214",
        title: "Server · Marina event · 6hr",
        progress: 64,
        meta: "Theo · on site",
        stampTone: "blue",
      },
    ],
  },
  {
    label: "Releasing",
    items: [
      {
        id: "OP-4209",
        title: "Pier setup proof verified — release $340",
        progress: 96,
        meta: "awaiting you",
      },
      {
        id: "OP-4207",
        title: "Server shift completed — release $156",
        progress: 100,
        meta: "auto · 4:58",
      },
    ],
  },
];

interface Approval {
  tone: "urgent" | "accent";
  icon: "envelope" | "cart" | "mail";
  title: string;
  sub: string;
  evidence: string;
  primary: string;
  secondary: string;
}

const APPROVALS: Approval[] = [
  {
    tone: "urgent",
    icon: "envelope",
    title: "Release $340 to Jordan Reyes",
    sub: "Pier 39 setup · 4hr · proof photo + manager sign-off verified",
    evidence: "OP-4209 · 3 of 4 rules met · 1 awaiting you",
    primary: "Approve",
    secondary: "Review",
  },
  {
    tone: "accent",
    icon: "cart",
    title: "Order ice + 200 cups under $80",
    sub: "Restaurant Depot · est. delivery Fri 3:45 PM · auto-receipt to AgentMail",
    evidence: "OP-4220 · cap honored · 1 vendor matched",
    primary: "Approve order",
    secondary: "Edit cap",
  },
  {
    tone: "accent",
    icon: "mail",
    title: "Send invoice reminder to Sutro Catering",
    sub: 'Drafted email · "Confirm May 24 invoice — could you itemize?"',
    evidence: "OP-4211 · drafted from your tone history",
    primary: "Send",
    secondary: "Edit",
  },
];

interface Receipt {
  kind: "email" | "photo" | "pdf";
  badge: string;
  title: string;
  sub: string;
  amount: string;
  time: string;
}

const RECEIPTS: Receipt[] = [
  {
    kind: "email",
    badge: "M",
    title: "Owner summary · OP-4218",
    sub: '"Maya confirmed at $135 — arriving 5:55 PM."',
    amount: "—",
    time: "5:45",
  },
  {
    kind: "photo",
    badge: "IMG",
    title: "Bar setup photo",
    sub: "uploaded by owner · attached to OP-4218",
    amount: "320 KB",
    time: "5:43",
  },
  {
    kind: "pdf",
    badge: "PDF",
    title: "Bay-Events-Brief.pdf",
    sub: "imported from bay-events.com via browser-use",
    amount: "1.2 MB",
    time: "5:42",
  },
  {
    kind: "email",
    badge: "$",
    title: "Receipt #R-4209 · Luis Romero",
    sub: "Stripe via Sponge · proof verified",
    amount: "$156.00",
    time: "4:58",
  },
  {
    kind: "photo",
    badge: "IMG",
    title: "Pier 39 setup proof",
    sub: "OP-4209 · matched venue layout · manager OK",
    amount: "2 photos",
    time: "4:54",
  },
  {
    kind: "email",
    badge: "@",
    title: "Vendor email · Sutro Catering",
    sub: "OP-4211 · sent, awaiting reply",
    amount: "—",
    time: "5:21",
  },
];

interface ExampleChip {
  fill: string;
  label: string;
  tone: "urgent" | "amber" | "blue" | "accent";
}

const EXAMPLE_CHIPS: ExampleChip[] = [
  {
    fill: "Need a bartender tonight 6–10 PM at Bay Events, SoMa, $120. Must have event experience. Urgent.",
    label: "Urgent bartender shift",
    tone: "urgent",
  },
  {
    fill: "Order 4 bags of ice + 200 cups for the Friday event, deliver by 4pm Fri. Cap $80.",
    label: "Inventory run",
    tone: "amber",
  },
  {
    fill: "Email Vincent at Sutro Catering — confirm the May 24 invoice and ask for itemized receipts.",
    label: "Email a vendor",
    tone: "blue",
  },
  {
    fill: "Release final payment to Jordan once the pier setup photos clear.",
    label: "Approve a release",
    tone: "accent",
  },
];

/* ------------------------------------------------------------------ */

export function HomeClient() {
  const [contractorCount, setContractorCount] = useState<number | null>(null);
  const [composerValue, setComposerValue] = useState("");
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    api
      .listContractors({ limit: 200 })
      .then(({ items }) => {
        if (!cancelled) setContractorCount(items.length);
      })
      .catch(() => {
        /* leave count null; sidebar will show a dash */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-grow composer (mirrors the prototype's behaviour).
  useEffect(() => {
    const ta = composerRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(180, ta.scrollHeight)}px`;
  }, [composerValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/chat");
  };

  const fillExample = (text: string) => {
    setComposerValue(text);
    composerRef.current?.focus();
  };

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[240px_1fr]">
      <Sidebar contractorCount={contractorCount} />

      <main className="w-full max-w-[1320px] px-5 pb-20 pt-7 md:px-9">
        <TopRow />

        <Hero
          composerRef={composerRef}
          composerValue={composerValue}
          setComposerValue={setComposerValue}
          onSubmit={handleSubmit}
          onFillExample={fillExample}
        />

        <Kpis />

        <SectionHead title="Active right now" right={<a href="#" className="hover:text-ink">All operations →</a>} />

        <div className="mb-9 grid grid-cols-1 gap-[18px] lg:grid-cols-[1.4fr_1fr]">
          <FeaturedOp />
          <LivePanel />
        </div>

        <SectionHead
          title="Operations pipeline"
          right={
            <>
              <span><span className="mr-1 text-urgent">●</span>1 urgent</span>
              <span><span className="mr-1 text-accent">●</span>4 live</span>
              <a href="#" className="hover:text-ink">Open all →</a>
            </>
          }
        />
        <Pipeline />

        <div className="mb-9 grid grid-cols-1 gap-[18px] lg:grid-cols-[1.1fr_1fr]">
          <ApprovalsCol />
          <ReceiptsCol />
        </div>

        <CapabilityHint />
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar                                                            */
/* ------------------------------------------------------------------ */

function Sidebar({ contractorCount }: { contractorCount: number | null }) {
  return (
    <aside className="sticky top-0 hidden h-screen flex-col gap-5 overflow-y-auto border-r border-line p-6 md:flex">
      <Link href="/" className="flex items-center gap-2.5" aria-label="CrewLoop">
        <BrandMark />
        <b className="text-base font-medium tracking-tight">CrewLoop</b>
      </Link>

      <div className="flex flex-col gap-0.5">
        <span className="px-2.5 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
          Workspace
        </span>
        <NavLink href="/home" icon={<HomeIcon />} active>
          Dashboard
        </NavLink>
        <NavLink href="/chat" icon={<ChatIcon />}>
          Chat with Loop <span className="ml-auto font-mono text-[11px] text-accent">●</span>
        </NavLink>
        <NavLink href="#" icon={<OpsIcon />}>
          Operations <span className="ml-auto font-mono text-[11px] text-muted">7</span>
        </NavLink>
        <NavLink href="/contractors" icon={<RosterIcon />}>
          Contractors
          <span className="ml-auto font-mono text-[11px] text-muted">
            {contractorCount ?? "—"}
          </span>
        </NavLink>
        <NavLink href="#" icon={<PaymentsIcon />}>Payments</NavLink>
      </div>

      <div className="flex flex-col gap-0.5">
        <span className="px-2.5 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
          Approvals
        </span>
        <a href="#" className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-ink-2 transition hover:bg-[#F1EEE5] hover:text-ink">
          <span className="inline-block h-2 w-2 rounded-full bg-urgent" />
          Awaiting you
          <span className="ml-auto font-mono text-[11px] text-muted">2</span>
        </a>
        <a href="#" className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-ink-2 transition hover:bg-[#F1EEE5] hover:text-ink">
          <span className="inline-block h-2 w-2 rounded-full bg-amber" />
          Scheduled releases
          <span className="ml-auto font-mono text-[11px] text-muted">3</span>
        </a>
      </div>

      <div className="mt-auto flex items-center gap-2.5 rounded-[10px] border border-line bg-panel p-2.5">
        <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-[#D7E5D8] text-xs font-semibold text-[#2C5638]">
          BE
        </span>
        <span className="flex flex-col leading-tight">
          <b className="text-[13px] font-medium">Bay Events Co.</b>
          <small className="text-[11.5px] text-muted">SF · admin</small>
        </span>
      </div>
    </aside>
  );
}

function NavLink({
  href,
  icon,
  children,
  active = false,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] transition ${
        active ? "bg-ink text-panel" : "text-ink-2 hover:bg-[#F1EEE5] hover:text-ink"
      }`}
    >
      <span className="inline-grid h-3.5 w-3.5 place-items-center">{icon}</span>
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Top row + hero composer                                            */
/* ------------------------------------------------------------------ */

function TopRow() {
  return (
    <div className="mb-3.5 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-2.5 text-[13px] text-ink-2">
        <span className="eyebrow">Tue · May 19</span>
        <span className="font-mono text-[11.5px] text-ink-2">·</span>
        <span className="font-mono text-[11.5px] text-muted">5:42 PM PT</span>
      </div>
      <div className="flex gap-2">
        <button className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3.5 py-2 text-[13.5px] font-medium text-ink transition hover:-translate-y-px hover:border-ink">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <rect x="1.5" y="2.5" width="10" height="8" rx="1.3" stroke="currentColor" strokeWidth="1.3" />
            <path d="M3.5 2v1.5M9.5 2v1.5M1.5 5h10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          Today
        </button>
        <button className="inline-flex items-center gap-2 rounded-full bg-ink px-3.5 py-2 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 2v9M2 6.5h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          New operation
        </button>
      </div>
    </div>
  );
}

function Hero({
  composerRef,
  composerValue,
  setComposerValue,
  onSubmit,
  onFillExample,
}: {
  composerRef: React.RefObject<HTMLTextAreaElement | null>;
  composerValue: string;
  setComposerValue: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onFillExample: (v: string) => void;
}) {
  return (
    <section className="relative mb-6 overflow-hidden rounded-[18px] border border-line bg-panel px-8 pb-6 pt-8">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(700px 200px at 100% 0%, rgba(62,124,78,0.06), transparent 60%)",
        }}
      />
      <div className="relative">
        <h1 className="font-display m-0 mb-1.5 max-w-[22ch] text-[clamp(34px,4.4vw,52px)] font-normal leading-none tracking-[-0.022em]">
          Good evening, Jen. <em className="italic text-accent">What needs to get done?</em>
        </h1>
        <p className="m-0 mb-[22px] max-w-[60ch] text-[15.5px] text-ink-2">
          Tell Loop what your business needs in plain English. It&apos;ll parse the request, verify the source, contact the right people, hold payment, collect proof, and report back — all in one tracked operation.
        </p>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-line bg-white px-4 pb-3 pt-3.5 shadow-[0_1px_0_rgba(22,20,16,0.02),0_18px_40px_-28px_rgba(22,20,16,0.22)] transition focus-within:border-[rgba(22,20,16,0.32)]"
        >
          <textarea
            ref={composerRef}
            value={composerValue}
            onChange={(e) => setComposerValue(e.target.value)}
            placeholder={'e.g. "Need a bartender tonight 6–10 PM at Bay Events, SoMa, $120 — urgent."'}
            className="block min-h-[46px] w-full resize-none border-0 bg-transparent px-1 py-1.5 text-[16px] leading-[1.5] text-ink outline-none placeholder:text-muted"
            style={{ maxHeight: 180 }}
          />
          <div className="mt-1.5 flex items-center gap-1 border-t border-line-2 pt-1.5">
            <ComposerButton title="Attach image">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <rect x="2" y="3" width="11" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
                <circle cx="5.5" cy="6" r="1" stroke="currentColor" strokeWidth="1.3" />
                <path d="M2.5 10.5l3-2.5 2.5 2 2-1.5 2.5 2" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
              </svg>
            </ComposerButton>
            <ComposerButton title="Attach file">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <path d="M9.5 6l-3.5 3.5a1.6 1.6 0 1 0 2.3 2.3l4-4a2.8 2.8 0 1 0-4-4L4 7.5a4.2 4.2 0 1 0 6 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </ComposerButton>
            <ComposerButton title="Record voice">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <rect x="5.5" y="2" width="4" height="7" rx="2" stroke="currentColor" strokeWidth="1.3" />
                <path d="M3.5 6.5v1a4 4 0 0 0 8 0v-1M7.5 11.5V13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
            </ComposerButton>
            <ComposerButton title="Paste a link / browser source">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <circle cx="7.5" cy="7.5" r="5" stroke="currentColor" strokeWidth="1.3" />
                <path d="M2.5 7.5h10M7.5 2.5c1.6 1.5 2.5 3.3 2.5 5s-.9 3.5-2.5 5M7.5 2.5C5.9 4 5 5.8 5 7.5s.9 3.5 2.5 5" stroke="currentColor" strokeWidth="1.3" />
              </svg>
            </ComposerButton>
            <ComposerButton title="Mark urgent" className="text-urgent">
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <path d="M7.5 2v6.5M7.5 11v1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </ComposerButton>
            <button
              type="submit"
              className="ml-auto inline-flex items-center gap-1.5 rounded-[9px] bg-ink px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-black"
            >
              Send to Loop
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6h7M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </form>

        <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 font-mono text-[11px] uppercase tracking-[0.08em] text-muted">Try</span>
          {EXAMPLE_CHIPS.map((c) => (
            <button
              key={c.label}
              type="button"
              onClick={() => onFillExample(c.fill)}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-[12.5px] text-ink-2 transition hover:-translate-y-px hover:border-ink hover:text-ink"
            >
              <span
                className={`inline-block h-[5px] w-[5px] rounded-full ${
                  c.tone === "urgent"
                    ? "bg-urgent"
                    : c.tone === "amber"
                    ? "bg-amber"
                    : c.tone === "blue"
                    ? "bg-[#2B4373]"
                    : "bg-accent"
                }`}
              />
              {c.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function ComposerButton({
  children,
  title,
  className = "",
}: {
  children: React.ReactNode;
  title: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      className={`grid h-[34px] w-[34px] place-items-center rounded-[9px] border border-transparent text-ink-2 transition hover:border-line hover:bg-bg hover:text-ink ${className}`}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* KPIs                                                               */
/* ------------------------------------------------------------------ */

function Kpis() {
  return (
    <div className="mb-6 grid grid-cols-2 gap-3.5 md:grid-cols-4">
      <KpiCard label="Operations today" value="7" delta="+2" deltaTone="accent" footer="vs. yesterday" />
      <KpiCard
        label="Filled in < 5 min"
        value="6/7"
        valueColor="text-accent"
        delta="86%"
        deltaTone="accent"
        footer="fill rate"
      />
      <KpiCard
        label="Money held"
        value="$1,247"
        delta="3 holds"
        deltaTone="amber"
        footer="across active ops"
      />
      <KpiCard
        label="Owner time saved"
        value="2:14"
        suffix="hr"
        delta="+0:38"
        deltaTone="accent"
        footer="this week"
      />
    </div>
  );
}

function KpiCard({
  label,
  value,
  suffix,
  valueColor = "",
  delta,
  deltaTone,
  footer,
}: {
  label: string;
  value: string;
  suffix?: string;
  valueColor?: string;
  delta: string;
  deltaTone: "accent" | "amber" | "urgent" | "neutral";
  footer: string;
}) {
  const tone =
    deltaTone === "accent"
      ? "bg-accent-soft text-accent"
      : deltaTone === "amber"
      ? "bg-amber-soft text-amber"
      : deltaTone === "urgent"
      ? "bg-urgent-soft text-urgent"
      : "bg-[#F0EDE3] text-muted";
  return (
    <div className="flex flex-col gap-1.5 rounded-[14px] border border-line bg-panel px-[18px] py-4">
      <span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted">{label}</span>
      <span className={`font-display text-[40px] leading-none tracking-[-0.02em] ${valueColor}`}>
        {value}
        {suffix ? (
          <span className="ml-1 text-[0.4em] text-muted">{suffix}</span>
        ) : null}
      </span>
      <span className="flex items-center gap-2 text-[12px] text-ink-2">
        <span className={`rounded-full px-1.5 py-0.5 font-mono text-[11px] ${tone}`}>{delta}</span>
        <span>{footer}</span>
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Section head                                                       */
/* ------------------------------------------------------------------ */

function SectionHead({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="mb-3.5 flex items-baseline justify-between gap-3">
      <h2 className="font-display m-0 text-[28px] font-normal leading-none tracking-[-0.01em]">
        {title}
      </h2>
      {right ? (
        <div className="flex items-center gap-3.5 font-mono text-[12.5px] tracking-[0.06em] text-muted">
          {right}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Featured op                                                        */
/* ------------------------------------------------------------------ */

function FeaturedOp() {
  return (
    <article className="flex flex-col overflow-hidden rounded-[18px] border border-line bg-white">
      <div
        className="flex flex-wrap items-center gap-3 border-b border-line-2 px-[22px] py-[18px]"
        style={{ background: "linear-gradient(180deg, rgba(62,124,78,0.04), transparent)" }}
      >
        <span className="inline-flex items-center gap-1.5 rounded-full bg-urgent-soft px-2 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.08em] text-urgent">
          ● Urgent
        </span>
        <Pill tone="blue">Staffing</Pill>
        <Pill tone="green">Maya · confirmed</Pill>
        <span className="ml-auto font-mono text-[11px] uppercase tracking-[0.08em] text-muted">
          OP-4218 · Bay Events
        </span>
      </div>
      <h3 className="font-display m-0 max-w-[24ch] px-[22px] pb-1 pt-[18px] text-[30px] leading-[1.1] tracking-[-0.015em]">
        Bartender tonight, 6–10 PM SoMa
      </h3>
      <p className="m-0 border-b border-line-2 px-[22px] pb-[18px] text-[14px] text-ink-2">
        From a single SMS at 5:42 PM — Loop parsed the brief, browsed the Bay Events portal for venue details, ranked your bartenders, and just confirmed Maya at $135 with proof rules attached.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-[1.05fr_1fr]">
        <div className="border-b border-line-2 px-[22px] py-[18px] md:border-b-0 md:border-r">
          <h5 className="m-0 mb-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted">
            The loop · step 5 of 7
          </h5>
          <div className="flex flex-col">
            {FEATURED_LOOP.map((step, i) => (
              <LoopRow key={i} step={step} isLast={i === FEATURED_LOOP.length - 1} />
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3.5 px-[22px] py-[18px]">
          <div>
            <h5 className="m-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted">
              Details
            </h5>
            <div className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px]">
              <Fact label="Window" value="6:00–10:00 PM" />
              <Fact label="Pay" value="$135 · 4 hr" />
              <Fact label="Location" value="SoMa, SF" />
              <Fact label="Guests" value="60 · cocktail" />
            </div>
          </div>

          <div>
            <h5 className="m-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted">
              Assigned
            </h5>
            <PersonRow initials="M" avatarBg="#D7E5D8" avatarFg="#2C5638" name="Maya Okafor" sub="98% reliable · 2.1 mi" pill={<Pill tone="green">Confirmed</Pill>} />
            <PersonRow initials="K" avatarBg="#E5E0D2" avatarFg="#5B5648" name="Kai Nakamura" sub="93% · standby" pill={<Pill>Backup</Pill>} />
          </div>

          <div>
            <h5 className="m-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted">
              Payment hold
            </h5>
            <div className="mt-2.5 flex items-center justify-between rounded-xl bg-bg px-3.5 py-3.5">
              <span className="flex flex-col leading-tight">
                <b className="font-display text-[30px] leading-none tracking-[-0.02em]">$135.00</b>
                <small className="mt-1 font-mono text-[11px] uppercase tracking-[0.08em] text-muted">
                  4 rules · 1 met
                </small>
              </span>
              <span className="flex flex-col items-end gap-1 text-right">
                <Pill tone="amber">Held · Sponge</Pill>
                <span className="font-mono text-[10.5px] text-muted">JOB #4218</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 border-t border-line-2 bg-panel px-[22px] py-3.5">
        <Link
          href="/chat"
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3.5 py-2 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black"
        >
          Open in chat
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 6h7M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Link>
        <a
          href="#"
          className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3.5 py-2 text-[13.5px] font-medium text-ink transition hover:-translate-y-px hover:border-ink"
        >
          View dispatch room
        </a>
        <span className="ml-auto font-mono text-[12.5px] tracking-[0.04em] text-muted">
          Auto-escalates to Kai if no check-in by 6:05 PM
        </span>
      </div>
    </article>
  );
}

function LoopRow({ step, isLast }: { step: LoopStep; isLast: boolean }) {
  const muted = step.state === "pending";
  return (
    <div className="relative grid grid-cols-[22px_1fr_auto] items-center gap-2.5 py-2">
      {!isLast ? (
        <span className="absolute left-[10px] top-[22px] -bottom-2 w-[1.5px] bg-line" />
      ) : null}
      <LoopDot state={step.state} />
      <span className={`text-[13.5px] ${muted ? "text-muted" : "text-ink-2"}`}>
        <b className={`font-medium ${muted ? "text-muted" : "text-ink"}`}>{step.title}</b>{" "}
        {step.detail ? <span className="ml-0.5">{step.state === "pending" ? "" : "the request"}</span> : null}
        <small className="mt-[1px] block font-mono text-[11px] tracking-[0.02em] text-muted">
          {step.detail}
        </small>
      </span>
      <span className="font-mono text-[11px] text-muted">{step.time}</span>
    </div>
  );
}

function LoopDot({ state }: { state: LoopStep["state"] }) {
  if (state === "done") {
    return (
      <span className="relative z-[1] grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-accent bg-accent">
        <span className="block h-1 w-[7px] rotate-[-45deg] -translate-y-[1px] border-b-[1.5px] border-l-[1.5px] border-white" />
      </span>
    );
  }
  if (state === "live") {
    return (
      <span className="tl-pulse relative z-[1] grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-accent bg-white" />
    );
  }
  return (
    <span className="relative z-[1] grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] border-line bg-white" />
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <small className="mb-[2px] block font-mono text-[10px] uppercase tracking-[0.08em] text-muted">
        {label}
      </small>
      <b className="font-medium text-ink">{value}</b>
    </div>
  );
}

function PersonRow({
  initials,
  avatarBg,
  avatarFg,
  name,
  sub,
  pill,
}: {
  initials: string;
  avatarBg: string;
  avatarFg: string;
  name: string;
  sub: string;
  pill: React.ReactNode;
}) {
  return (
    <div className="mt-2.5 flex items-center gap-2.5 text-[13px]">
      <span
        className="grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-full text-[11px] font-semibold"
        style={{ background: avatarBg, color: avatarFg }}
      >
        {initials}
      </span>
      <span className="flex flex-1 flex-col leading-[1.15]">
        <b className="font-medium text-ink">{name}</b>
        <small className="font-mono text-[10.5px] text-muted">{sub}</small>
      </span>
      {pill}
    </div>
  );
}

function Pill({
  tone,
  children,
}: {
  tone?: "green" | "amber" | "blue";
  children: React.ReactNode;
}) {
  const cls =
    tone === "green"
      ? "bg-accent text-panel"
      : tone === "amber"
      ? "bg-amber-soft text-amber"
      : tone === "blue"
      ? "bg-[#E4E8F0] text-[#2B4373]"
      : "bg-[#F0EDE3] text-ink-2";
  return (
    <span className={`whitespace-nowrap rounded-full px-2 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.06em] ${cls}`}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Live panel                                                         */
/* ------------------------------------------------------------------ */

function LivePanel() {
  return (
    <aside className="flex flex-col gap-3.5 rounded-[18px] border border-line bg-white px-[18px] py-[18px]">
      <div className="flex items-center justify-between">
        <h3 className="m-0 text-[14px] font-medium">What Loop is doing</h3>
        <span className="inline-flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-[0.08em] text-accent">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_0_3px_rgba(62,124,78,0.18)]" />
          Live
        </span>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-line bg-panel p-3.5">
        <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-[9px] bg-ink text-panel">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 8a5 5 0 1 1 8.5 3.5" stroke="#FBFAF6" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M11.5 8.5V11.5H8.5" stroke="#FBFAF6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="text-[13.5px] leading-snug text-ink-2">
          <b className="font-medium text-ink">Watching for Maya&apos;s check-in.</b> If she hasn&apos;t texted YES from the venue by 6:05, I&apos;ll call her and queue Kai. Owner approval is still required before any payment moves.
          <span className="mt-1.5 block font-mono text-[11px] tracking-[0.02em] text-muted">
            Updated 12s ago
          </span>
        </div>
      </div>

      <div className="flex flex-col">
        {LIVE_FEED.map((row, i) => (
          <FeedRow key={i} row={row} isLast={i === LIVE_FEED.length - 1} />
        ))}
      </div>
    </aside>
  );
}

function FeedRow({ row, isLast }: { row: FeedEntry; isLast: boolean }) {
  const tone =
    row.ic === "sms"
      ? "bg-[#E4E8F0] text-[#2B4373]"
      : row.ic === "call"
      ? "bg-accent-soft text-accent"
      : row.ic === "email"
      ? "bg-[#EEEAE0] text-ink-2"
      : row.ic === "pay"
      ? "bg-amber-soft text-amber"
      : row.ic === "proof"
      ? "bg-[#E5D5E5] text-[#6E2C66]"
      : "bg-urgent-soft text-urgent";

  return (
    <div
      className={`grid grid-cols-[26px_1fr_auto] items-center gap-2.5 px-1 py-2.5 text-[13px] ${
        isLast ? "" : "border-b border-line-2"
      }`}
    >
      <span className={`grid h-[26px] w-[26px] place-items-center rounded-[7px] ${tone}`}>
        <FeedIcon kind={row.ic} />
      </span>
      <div className="flex flex-col leading-tight">
        <b className="font-medium text-ink">{row.who}</b>
        <small className="font-mono text-[10.5px] text-muted">{row.meta}</small>
      </div>
      <span className="font-mono text-[10.5px] text-muted">{row.time}</span>
    </div>
  );
}

function FeedIcon({ kind }: { kind: FeedEntry["ic"] }) {
  switch (kind) {
    case "call":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M2.5 2.5h2l1 2.5L4 6c.8 1.5 2 2.7 3.5 3.5L9 8l2.5 1v2h-1A8 8 0 0 1 2.5 3.5v-1z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
        </svg>
      );
    case "sms":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M2 3h9v6H5L3 11V9H2V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
        </svg>
      );
    case "browser":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.3" />
          <path d="M2 6.5h9" stroke="currentColor" strokeWidth="1.3" />
        </svg>
      );
    case "email":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <rect x="2" y="3" width="9" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
          <path d="M2 4.5L6.5 7.5 11 4.5" stroke="currentColor" strokeWidth="1.3" />
        </svg>
      );
    case "pay":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <rect x="1.5" y="3.5" width="10" height="6.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
          <path d="M1.5 5.5h10" stroke="currentColor" strokeWidth="1.3" />
        </svg>
      );
    case "proof":
      return (
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.3" />
          <path d="M4.5 6.5L6 8l3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
}

/* ------------------------------------------------------------------ */
/* Pipeline                                                           */
/* ------------------------------------------------------------------ */

function Pipeline() {
  return (
    <div className="mb-9 grid gap-3.5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
      {PIPELINE.map((col) => (
        <div
          key={col.label}
          className="flex min-h-[170px] flex-col gap-2.5 rounded-[14px] border border-line bg-panel p-3"
        >
          <h5 className="m-0 flex items-center justify-between border-b border-line-2 px-1 pb-1.5 pt-0.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted">
            <span>{col.label}</span>
            <span className="rounded-full border border-line bg-white px-1.5 py-px text-[10.5px] font-medium text-ink-2">
              {col.items.length}
            </span>
          </h5>
          {col.items.map((op) => (
            <PipelineCard key={op.id} op={op} />
          ))}
        </div>
      ))}
    </div>
  );
}

function PipelineCard({ op }: { op: PipelineOp }) {
  const stampClass =
    op.stampTone === "urgent"
      ? "bg-urgent shadow-[0_0_0_3px_rgba(200,72,46,0.16)]"
      : op.stampTone === "live"
      ? "bg-accent shadow-[0_0_0_3px_rgba(62,124,78,0.16)]"
      : op.stampTone === "blue"
      ? "bg-[#2B4373]"
      : "bg-muted";

  const fillClass =
    op.progressTone === "urgent"
      ? "bg-urgent"
      : op.progressTone === "amber"
      ? "bg-amber"
      : "bg-accent";

  return (
    <button
      type="button"
      className="relative flex flex-col gap-1.5 rounded-[10px] border border-line bg-white px-3 py-2.5 text-left transition hover:-translate-y-px hover:border-ink"
    >
      <span className={`absolute right-3 top-3 h-2 w-2 rounded-full ${stampClass}`} />
      <span className="pr-5 text-[13px] font-medium leading-snug text-ink">{op.title}</span>
      <span className="h-[3px] overflow-hidden rounded-full bg-[#EFEBDF]">
        <span className={`block h-full rounded-full ${fillClass}`} style={{ width: `${op.progress}%` }} />
      </span>
      <span className="flex items-center justify-between font-mono text-[11px] tracking-[0.04em] text-muted">
        <span>{op.id}</span>
        <span>{op.meta}</span>
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Approvals + receipts                                               */
/* ------------------------------------------------------------------ */

function ApprovalsCol() {
  return (
    <div>
      <SectionHead title="Needs your approval" right={<a href="#" className="hover:text-ink">All approvals →</a>} />
      <div className="flex flex-col gap-2.5">
        {APPROVALS.map((a, i) => (
          <ApprovalRow key={i} item={a} />
        ))}
      </div>
    </div>
  );
}

function ApprovalRow({ item }: { item: Approval }) {
  const iconTone =
    item.tone === "urgent" ? "bg-urgent-soft text-urgent" : "bg-accent-soft text-accent";

  return (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-panel px-3.5 py-3.5">
      <span className={`grid h-9 w-9 flex-shrink-0 place-items-center rounded-[10px] ${iconTone}`}>
        <ApprovalIcon kind={item.icon} />
      </span>
      <div className="min-w-0 flex-1">
        <b className="block text-[13.5px] font-medium text-ink">{item.title}</b>
        <small className="mt-px block text-[12.5px] text-ink-2">{item.sub}</small>
        <span className="mt-1 block font-mono text-[10.5px] tracking-[0.04em] text-muted">
          {item.evidence}
        </span>
      </div>
      <div className="flex gap-1.5">
        <button className="rounded-lg border border-line px-2.5 py-1.5 text-[12.5px] text-ink-2 transition hover:border-ink hover:text-ink">
          {item.secondary}
        </button>
        <button className="rounded-lg bg-ink px-2.5 py-1.5 text-[12.5px] font-medium text-panel transition hover:bg-black">
          {item.primary}
        </button>
      </div>
    </div>
  );
}

function ApprovalIcon({ kind }: { kind: Approval["icon"] }) {
  if (kind === "envelope") {
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="2" y="4" width="14" height="10" rx="1.6" stroke="currentColor" strokeWidth="1.5" />
        <path d="M2 7h14" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (kind === "cart") {
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M3.5 4h11l-1.2 8H4.7L3.5 4zM2 4h1.5M6.5 14.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM12.5 14.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="2" y="3" width="14" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2 7l7 4 7-4" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

function ReceiptsCol() {
  return (
    <div>
      <SectionHead title="Proof & receipts" right={<a href="#" className="hover:text-ink">Audit log →</a>} />
      <div className="overflow-hidden rounded-[14px] border border-line bg-panel">
        {RECEIPTS.map((r, i) => (
          <ReceiptRow key={i} row={r} isLast={i === RECEIPTS.length - 1} />
        ))}
      </div>
    </div>
  );
}

function ReceiptRow({ row, isLast }: { row: Receipt; isLast: boolean }) {
  const icCls =
    row.kind === "email"
      ? "bg-ink text-panel border-ink"
      : row.kind === "pdf"
      ? "bg-white text-urgent border-line"
      : "bg-white text-[#2B4373] border-line";

  return (
    <div
      className={`grid cursor-pointer grid-cols-[30px_1fr_auto_auto] items-center gap-3 px-3.5 py-3 text-[13px] transition hover:bg-white ${
        isLast ? "" : "border-b border-line-2"
      }`}
    >
      <span
        className={`grid h-[34px] w-[28px] place-items-center rounded-[5px] border font-mono text-[9px] font-semibold ${icCls}`}
      >
        {row.badge}
      </span>
      <div className="flex min-w-0 flex-col leading-tight">
        <b className="truncate text-[13px] font-medium text-ink">{row.title}</b>
        <small className="truncate font-mono text-[10.5px] text-muted">{row.sub}</small>
      </div>
      <span className="font-mono text-[12.5px] text-ink">{row.amount}</span>
      <span className="min-w-[54px] text-right font-mono text-[10.5px] text-muted">{row.time}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Capability hint                                                    */
/* ------------------------------------------------------------------ */

function CapabilityHint() {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3.5 rounded-[14px] border border-dashed border-line bg-panel px-5 py-[18px]">
      <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[10px] bg-ink text-panel">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M3 9a6 6 0 1 1 10.2 4.2" stroke="#FBFAF6" strokeWidth="1.6" strokeLinecap="round" />
          <path d="M13.2 9.5V13H9.7" stroke="#FBFAF6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="min-w-[200px] flex-1 text-[14px] text-ink-2">
        <b className="font-medium text-ink">Same loop, different operation.</b> Loop can also order inventory, email vendors, confirm deliveries, or pay invoices — every action holds money, captures proof, and waits for your approval.
      </span>
      <span className="flex flex-wrap gap-1.5">
        {["Order inventory", "Email a vendor", "Confirm a delivery", "Pay an invoice"].map((c) => (
          <span
            key={c}
            className="rounded-full border border-line bg-white px-2.5 py-1 text-[12px] text-ink-2"
          >
            {c}
          </span>
        ))}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar icons                                                      */
/* ------------------------------------------------------------------ */

function HomeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 8l5-4 5 4v4H2V8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function ChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2.5 3.5h9v6h-5L3.5 11.5v-2h-1v-6z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function OpsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="2" y="3" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2 6h10" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
function RosterIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="5" cy="5" r="2.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2 11.5c0-1.7 1.4-3 3-3s3 1.3 3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="10" cy="6" r="1.8" stroke="currentColor" strokeWidth="1.4" />
      <path d="M9 11.5c0-1.1.9-2 2-2s1 .4 1 .8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
function PaymentsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 11V5l4-3 4 3v6" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx="7" cy="7.5" r="1.4" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
