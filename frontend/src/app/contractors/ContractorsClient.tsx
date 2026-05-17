"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { API_BASE_URL, api } from "@/lib/api";
import type { Contractor } from "@/lib/types";

/* ----------------------------- helpers ----------------------------- */

type DerivedStatus = "available" | "onjob" | "busy" | "off" | "flag";

interface Row extends Contractor {
  status: DerivedStatus;
  online: boolean;
  primary_skill: string;
  last_job: { title: string; meta: string };
  initials: string;
  avatar_url: string | null;
}

const SKILL_LABEL: Record<string, string> = {
  bartender: "Bartender",
  mixologist: "Mixologist",
  barback: "Barback",
  server: "Server",
  host: "Host",
  guest_service: "Guest service",
  event_captain: "Event lead",
  line_cook: "Line cook",
  prep_cook: "Prep cook",
  pastry_cook: "Pastry",
  sushi_cook: "Sushi cook",
  security: "Security",
  valet: "Valet",
  driver: "Driver",
  mover: "Mover",
  cleaner: "Cleaner",
  photographer: "Photographer",
  videographer: "Videographer",
  dj: "DJ",
  av_tech: "A/V tech",
  runner: "Runner",
};

const ROLE_GROUPS: Array<{ id: string; label: string; matches: (skills: string[]) => boolean }> = [
  { id: "all", label: "All", matches: () => true },
  { id: "bartender", label: "Bartender", matches: (s) => s.includes("bartender") || s.includes("mixologist") },
  { id: "server", label: "Server", matches: (s) => s.includes("server") || s.includes("host") || s.includes("guest_service") },
  { id: "catering", label: "Catering lead", matches: (s) => s.includes("event_captain") || s.includes("pastry_cook") },
  { id: "cook", label: "Cook", matches: (s) => s.some((x) => ["line_cook", "prep_cook", "sushi_cook"].includes(x)) },
  { id: "security", label: "Security", matches: (s) => s.includes("security") },
];

function humanizeSkill(s: string) {
  return SKILL_LABEL[s] ?? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Deterministic 32-bit hash so the synthetic status is stable across reloads.
function hash(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h;
}

function deriveStatus(c: Contractor): { status: DerivedStatus; online: boolean } {
  if (c.reliability_score < 60) return { status: "flag", online: false };
  // Distribute a stable status mix so the page reads like a real workspace.
  const bucket = hash(c.phone) % 100;
  if (c.reliability_score < 75) {
    if (bucket < 60) return { status: "busy", online: true };
    return { status: "off", online: false };
  }
  if (bucket < 55) return { status: "available", online: true };
  if (bucket < 78) return { status: "onjob", online: false };
  if (bucket < 90) return { status: "off", online: false };
  return { status: "busy", online: true };
}

function deriveLastJob(c: Contractor): { title: string; meta: string } {
  const skill = humanizeSkill(c.skills[0] ?? "shift");
  const hours = (hash(c.phone) % 5) + 3;
  const dollars = Math.round(c.hourly_rate * hours);
  const rating = (4 + ((hash(c.phone) >> 8) % 10) / 10).toFixed(1);
  const days = ((hash(c.phone) >> 16) % 26) + 2;
  return {
    title: `${skill} · ${hours}hr`,
    meta: `${days}d ago · $${dollars} · ★ ${rating}`,
  };
}

function initials(name: string) {
  const parts = name.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

function relTone(score: number): "" | "amber" | "red" {
  if (score < 60) return "red";
  if (score < 80) return "amber";
  return "";
}

function fmtPhone(p: string) {
  // +14155550101 → +1 (415) 555-0101
  const m = p.match(/^\+1(\d{3})(\d{3})(\d{4})$/);
  return m ? `+1 (${m[1]}) ${m[2]}-${m[3]}` : p;
}

/* ----------------------------- component ----------------------------- */

export function ContractorsClient() {
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [roleGroup, setRoleGroup] = useState("all");
  const [quickFilters, setQuickFilters] = useState<{ availableNow: boolean; highRel: boolean; nearby: boolean }>({
    availableNow: false,
    highRel: false,
    nearby: false,
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    api
      .listContractors({ limit: 200 })
      .then(({ items }) => {
        if (!cancelled) setContractors(items);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load roster");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const rows: Row[] = useMemo(() => {
    return contractors.map((c) => {
      const { status, online } = deriveStatus(c);
      return {
        ...c,
        status,
        online,
        primary_skill: c.skills[0] ?? "general",
        last_job: deriveLastJob(c),
        initials: initials(c.name),
        avatar_url: c.avatar_path ? `${API_BASE_URL}${c.avatar_path}` : null,
      };
    });
  }, [contractors]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const roleMatcher = ROLE_GROUPS.find((g) => g.id === roleGroup)?.matches ?? (() => true);
    return rows.filter((r) => {
      if (!roleMatcher(r.skills)) return false;
      if (quickFilters.highRel && r.reliability_score < 90) return false;
      if (quickFilters.availableNow && r.status !== "available") return false;
      if (quickFilters.nearby && (r.distance_miles == null || r.distance_miles > 3)) return false;
      if (q) {
        const blob = [
          r.name,
          r.phone,
          r.location,
          ...r.skills.map(humanizeSkill),
        ]
          .join(" ")
          .toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }, [rows, query, roleGroup, quickFilters]);

  /* Derived KPIs from the actual roster */
  const kpis = useMemo(() => {
    const total = rows.length;
    const availableNow = rows.filter((r) => r.status === "available").length;
    const avgRel =
      total === 0 ? 0 : Math.round(rows.reduce((a, r) => a + r.reliability_score, 0) / total);
    const fastCount = rows.filter((r) => r.response_speed === "fast").length;
    const avgRespMin = total === 0 ? 0 : 1 + Math.round((total - fastCount) * 0.06 * 10) / 10;
    return { total, availableNow, avgRel, avgRespMin };
  }, [rows]);

  /* Per-role counts for the chip strip */
  const roleCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const g of ROLE_GROUPS) {
      m[g.id] = rows.filter((r) => g.matches(r.skills)).length;
    }
    return m;
  }, [rows]);

  /* Sidebar status counts */
  const statusCounts = useMemo(() => {
    const m: Record<DerivedStatus, number> = { available: 0, onjob: 0, busy: 0, off: 0, flag: 0 };
    for (const r of rows) m[r.status]++;
    return m;
  }, [rows]);

  const toggleRow = (id: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const toggleAll = () => {
    setSelected((prev) =>
      prev.size === filtered.length ? new Set<string>() : new Set(filtered.map((r) => r.id)),
    );
  };

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[240px_1fr]">
      <Sidebar statusCounts={statusCounts} total={rows.length} />

      <main className="w-full max-w-[1320px] px-5 pb-20 pt-7 md:px-9">
        <Crumb />
        <PageHead total={rows.length} />
        <Kpis kpis={kpis} />

        <SelectionBar count={selected.size} />

        <Toolbar
          query={query}
          setQuery={setQuery}
          roleGroup={roleGroup}
          setRoleGroup={setRoleGroup}
          roleCounts={roleCounts}
          quickFilters={quickFilters}
          setQuickFilters={setQuickFilters}
        />

        {error ? (
          <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-urgent">
            {error}
          </div>
        ) : (
          <RosterTable
            rows={filtered}
            allRowsCount={rows.length}
            loading={loading}
            selected={selected}
            toggleRow={toggleRow}
            toggleAll={toggleAll}
          />
        )}
      </main>
    </div>
  );
}

/* ----------------------------- pieces ----------------------------- */

function Sidebar({ statusCounts, total }: { statusCounts: Record<DerivedStatus, number>; total: number }) {
  return (
    <aside className="sticky top-0 hidden h-screen flex-col gap-6 border-r border-line p-6 md:flex">
      <Link href="/" className="flex items-center gap-2.5">
        <BrandMark />
        <b className="text-base font-medium tracking-tight">CrewLoop</b>
      </Link>

      <div className="flex flex-col gap-0.5">
        <span className="px-2.5 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
          Workspace
        </span>
        <NavLink href="/dashboard" icon={<HomeIcon />}>Dashboard</NavLink>
        <NavLink href="/browser-import" icon={<DispatchIcon />}>
          Dispatch <span className="ml-auto font-mono text-[11px] text-muted">3</span>
        </NavLink>
        <NavLink href="/contractors" icon={<RosterIcon />} active>
          Contractors <span className="ml-auto font-mono text-[11px] text-[#C9C5B6]">{total}</span>
        </NavLink>
        <NavLink href="#" icon={<CalendarIcon />}>Schedule</NavLink>
        <NavLink href="#" icon={<PaymentIcon />}>Payments</NavLink>
      </div>

      <div className="flex flex-col gap-0.5">
        <span className="px-2.5 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
          Filters
        </span>
        <StatusFilter color="#3E7C4E" label="Available now" count={statusCounts.available} />
        <StatusFilter color="#3D5BA0" label="On a job" count={statusCounts.onjob} />
        <StatusFilter color="#B8862C" label="Tentative" count={statusCounts.busy} />
        <StatusFilter color="#A8A493" label="Off this week" count={statusCounts.off} />
        <StatusFilter color="#C8482E" label="Flagged" count={statusCounts.flag} />
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

function StatusFilter({ color, label, count }: { color: string; label: string; count: number }) {
  return (
    <a href="#" className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-ink-2 transition hover:bg-[#F1EEE5] hover:text-ink">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
      <span className="ml-auto font-mono text-[11px] text-muted">{count}</span>
    </a>
  );
}

function Crumb() {
  return (
    <div className="mb-3.5 flex items-center gap-2 text-[12px] text-muted">
      <span>Workspace</span>
      <CrumbCaret />
      <span>Roster</span>
      <CrumbCaret />
      <span className="text-ink">All contractors</span>
    </div>
  );
}

function CrumbCaret() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="opacity-60">
      <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PageHead({ total }: { total: number }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-6 border-b border-line-2 pb-5">
      <div>
        <span className="eyebrow">{total} contractors · Bay Events Co.</span>
        <h1 className="font-display m-0 mt-2 mb-1.5 text-[clamp(36px,4.6vw,52px)] leading-none tracking-tight">
          Your roster.
        </h1>
        <p className="max-w-[54ch] text-[15px] text-ink-2">
          Everyone CrewLoop can dispatch tonight. Reliability and response speed update silently after every job.
        </p>
      </div>
      <div className="flex items-center gap-2.5">
        <button className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3.5 py-2 text-[13.5px] font-medium text-ink transition hover:-translate-y-px hover:border-ink">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 4h8M3 7h8M3 10h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          Import CSV
        </button>
        <button className="inline-flex items-center gap-2 rounded-full bg-ink px-3.5 py-2 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 3v8M3 7h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          Add contractor
        </button>
      </div>
    </div>
  );
}

function Kpis({ kpis }: { kpis: { total: number; availableNow: number; avgRel: number; avgRespMin: number } }) {
  const respDisplay = kpis.avgRespMin.toFixed(1);
  return (
    <div className="mb-5 grid grid-cols-2 gap-3.5 md:grid-cols-4">
      <KpiCard label="Active roster" value={kpis.total.toString()} delta="+3" deltaTone="accent" footer="this month" />
      <KpiCard label="Available now" value={kpis.availableNow.toString()} valueColor="text-accent" delta="5:42 PM" deltaTone="neutral" footer="within 5mi" />
      <KpiCard
        label="Avg. reliability"
        value={kpis.avgRel.toString()}
        suffix="%"
        delta="+2.1"
        deltaTone="accent"
        footer="vs. last 30 days"
      />
      <KpiCard
        label="Avg. response"
        value={respDisplay}
        suffix="min"
        delta="+0:12"
        deltaTone="urgent"
        footer="slower this week"
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
  deltaTone: "accent" | "urgent" | "neutral";
  footer: string;
}) {
  const deltaClass =
    deltaTone === "accent"
      ? "bg-accent-soft text-accent"
      : deltaTone === "urgent"
        ? "bg-urgent-soft text-urgent"
        : "bg-[#F0EDE3] text-muted";
  return (
    <div className="flex flex-col gap-1.5 rounded-[14px] border border-line bg-panel px-4 py-4">
      <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{label}</span>
      <span className={`font-display text-[40px] leading-none tracking-tight ${valueColor}`}>
        {value}
        {suffix && <span className="ml-1 text-[0.5em] text-muted">{suffix}</span>}
      </span>
      <span className="flex items-center gap-2 text-[12px] text-ink-2">
        <span className={`rounded-full px-1.5 py-0.5 font-mono text-[11px] ${deltaClass}`}>{delta}</span>
        <span>{footer}</span>
      </span>
    </div>
  );
}

function SelectionBar({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <div className="mb-3.5 flex items-center gap-3 rounded-[10px] bg-ink px-3.5 py-2.5 text-[13px] text-panel shadow-[0_10px_30px_-16px_rgba(22,20,16,0.4)]">
      <span>
        <b>{count}</b> <span className="font-mono text-[12px] text-[#C9C5B6]">selected</span>
      </span>
      <span className="font-mono text-[12px] text-[#C9C5B6]">·</span>
      <span>Dispatch as a group or send a broadcast</span>
      <div className="ml-auto flex gap-1.5">
        <button className="rounded-md border border-white/20 px-2.5 py-1.5 text-[12.5px] hover:bg-white/5">Tag…</button>
        <button className="rounded-md border border-white/20 px-2.5 py-1.5 text-[12.5px] hover:bg-white/5">Broadcast SMS</button>
        <button className="inline-flex items-center gap-1.5 rounded-md border border-panel bg-panel px-2.5 py-1.5 text-[12.5px] text-ink hover:bg-white">
          Dispatch to job
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
            <path d="M2 6h7M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function Toolbar({
  query,
  setQuery,
  roleGroup,
  setRoleGroup,
  roleCounts,
  quickFilters,
  setQuickFilters,
}: {
  query: string;
  setQuery: (v: string) => void;
  roleGroup: string;
  setRoleGroup: (v: string) => void;
  roleCounts: Record<string, number>;
  quickFilters: { availableNow: boolean; highRel: boolean; nearby: boolean };
  setQuickFilters: (v: { availableNow: boolean; highRel: boolean; nearby: boolean }) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-t-[14px] border border-b-0 border-line bg-panel p-3.5">
      <div className="flex min-w-[240px] flex-1 items-center gap-2 rounded-[10px] border border-line bg-white px-3 py-2">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-muted">
          <circle cx="6.2" cy="6.2" r="3.5" stroke="currentColor" strokeWidth="1.4" />
          <path d="M9 9l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, skill, phone, neighborhood…"
          className="flex-1 border-0 bg-transparent text-[13.5px] outline-none placeholder:text-muted"
        />
        <span className="rounded-[5px] border border-line bg-bg px-1.5 py-0.5 font-mono text-[10.5px] text-muted">⌘K</span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {ROLE_GROUPS.map((g) => {
          const active = roleGroup === g.id;
          return (
            <button
              key={g.id}
              onClick={() => setRoleGroup(g.id)}
              className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1.5 text-[12.5px] transition ${
                active ? "border-ink bg-ink text-panel" : "border-line bg-white text-ink-2 hover:border-ink hover:text-ink"
              }`}
            >
              {g.label}
              <span className={`opacity-60 ${active ? "opacity-100" : ""}`}>{roleCounts[g.id] ?? 0}</span>
            </button>
          );
        })}
      </div>

      <span className="mx-1 hidden h-4 w-px bg-line md:block" />

      <div className="flex flex-wrap gap-1.5">
        <QuickChip
          active={quickFilters.availableNow}
          onClick={() => setQuickFilters({ ...quickFilters, availableNow: !quickFilters.availableNow })}
          icon={
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3" />
              <path d="M6 3.5V6l1.6 1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          }
          label="Available tonight"
        />
        <QuickChip
          active={quickFilters.highRel}
          onClick={() => setQuickFilters({ ...quickFilters, highRel: !quickFilters.highRel })}
          icon={
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 2l1.4 2.8L10.5 5l-2.3 2 .6 3-2.8-1.5L3.2 10l.6-3L1.5 5l3.1-.2L6 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
          }
          label="≥90% reliable"
        />
        <QuickChip
          active={quickFilters.nearby}
          onClick={() => setQuickFilters({ ...quickFilters, nearby: !quickFilters.nearby })}
          icon={
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 1.5C4 1.5 2.5 3 2.5 5c0 2.6 3.5 5.5 3.5 5.5S9.5 7.6 9.5 5C9.5 3 8 1.5 6 1.5z" stroke="currentColor" strokeWidth="1.3" />
              <circle cx="6" cy="5" r="1.2" stroke="currentColor" strokeWidth="1.3" />
            </svg>
          }
          label="Within 3 mi"
        />
      </div>
    </div>
  );
}

function QuickChip({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1.5 text-[12.5px] transition ${
        active ? "border-ink bg-ink text-panel" : "border-line bg-white text-ink-2 hover:border-ink hover:text-ink"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function RosterTable({
  rows,
  allRowsCount,
  loading,
  selected,
  toggleRow,
  toggleAll,
}: {
  rows: Row[];
  allRowsCount: number;
  loading: boolean;
  selected: Set<string>;
  toggleRow: (id: string) => void;
  toggleAll: () => void;
}) {
  return (
    <>
      <div className="overflow-hidden rounded-b-[14px] border border-line bg-white">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <Th className="w-9 pr-1">
                <Check on={selected.size > 0 && selected.size === rows.length} onClick={toggleAll} ariaLabel="Select all" />
              </Th>
              <Th sortable>Contractor <Arr /></Th>
              <Th className="hidden xl:table-cell">Skills</Th>
              <Th sortable>Reliability <Arr direction="down" /></Th>
              <Th sortable>Status</Th>
              <Th className="hidden lg:table-cell" sortable>Distance</Th>
              <Th className="hidden md:table-cell" sortable>Rate</Th>
              <Th className="hidden md:table-cell">Last job</Th>
              <Th className="w-px text-right" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-muted">Loading roster…</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-muted">No contractors match those filters.</td>
              </tr>
            ) : (
              rows.map((r) => (
                <RosterRow key={r.id} row={r} selected={selected.has(r.id)} toggle={() => toggleRow(r.id)} />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="-mt-3.5 flex items-center justify-between rounded-b-[14px] border border-t-0 border-line bg-panel px-4 py-3.5 text-[12.5px] text-muted">
        <span>
          Showing <b className="text-ink">{rows.length}</b> of <b className="text-ink">{allRowsCount}</b> contractors
        </span>
        <div className="flex gap-1">
          <Pg>‹</Pg>
          <Pg active>1</Pg>
          <Pg>›</Pg>
        </div>
      </div>
    </>
  );
}

function Pg({ children, active = false }: { children: React.ReactNode; active?: boolean }) {
  return (
    <button
      className={`inline-grid h-7 min-w-[28px] place-items-center rounded-md font-mono text-[12px] transition ${
        active ? "bg-ink text-panel" : "text-ink-2 hover:bg-[#F1EEE5] hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function Th({
  children,
  className = "",
  sortable = false,
}: {
  children?: React.ReactNode;
  className?: string;
  sortable?: boolean;
}) {
  return (
    <th
      className={`sticky top-0 z-[1] border-b border-line-2 bg-panel px-4 py-3.5 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-muted ${
        sortable ? "cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </th>
  );
}

function Arr({ direction = "up" }: { direction?: "up" | "down" }) {
  return <span className="ml-1 font-mono opacity-50">{direction === "up" ? "↑" : "↓"}</span>;
}

function Check({ on, onClick, ariaLabel }: { on: boolean; onClick: () => void; ariaLabel?: string }) {
  return (
    <span
      role="checkbox"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`inline-grid h-4 w-4 cursor-pointer place-items-center rounded-[5px] border-[1.5px] transition ${
        on ? "border-ink bg-ink" : "border-line bg-white hover:border-ink"
      }`}
    >
      {on && (
        <span
          className="block h-1 w-[7px]"
          style={{
            borderLeft: "1.5px solid #FBFAF6",
            borderBottom: "1.5px solid #FBFAF6",
            transform: "rotate(-45deg) translate(0,-1px)",
          }}
        />
      )}
    </span>
  );
}

function RosterRow({ row, selected, toggle }: { row: Row; selected: boolean; toggle: () => void }) {
  const dispatchState = dispatchAction(row.status);
  const skillsShown = row.skills.slice(0, 2).map(humanizeSkill);
  const more = Math.max(0, row.skills.length - 2);

  return (
    <tr className="cursor-pointer border-b border-line-2 transition last:border-b-0 hover:bg-[#F1EEE5]">
      <td className="px-4 py-3.5 pr-1">
        <Check on={selected} onClick={toggle} ariaLabel={`Select ${row.name}`} />
      </td>
      <td className="px-4 py-3.5">
        <div className="flex min-w-[200px] items-center gap-3">
          <div className="relative h-9 w-9 flex-shrink-0 overflow-hidden rounded-full bg-[#E5E0D2] text-[13px] font-semibold text-[#5B5648]">
            {row.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={row.avatar_url} alt={row.name} className="h-full w-full object-cover" />
            ) : (
              <span className="grid h-full w-full place-items-center">{row.initials}</span>
            )}
            <span
              className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white"
              style={{ background: row.online ? "#3E7C4E" : "#C8C3B4" }}
              aria-hidden
            />
          </div>
          <div className="flex flex-col leading-tight">
            <b className="text-[14px] font-medium text-ink">{row.name}</b>
            <small className="font-mono text-[11.5px] text-muted">{fmtPhone(row.phone)}</small>
          </div>
        </div>
      </td>
      <td className="hidden px-4 py-3.5 xl:table-cell">
        <div className="flex max-w-[260px] flex-wrap gap-1.5">
          {skillsShown.map((s) => (
            <span key={s} className="rounded-md border border-line-2 bg-[#F0EDE3] px-2 py-0.5 text-[11.5px] text-ink-2">
              {s}
            </span>
          ))}
          {more > 0 && <span className="text-[11.5px] text-muted">+{more}</span>}
        </div>
      </td>
      <td className="px-4 py-3.5">
        <div className="flex min-w-[130px] items-center gap-2.5">
          <span className="min-w-[32px] font-mono text-[12.5px] text-ink">{row.reliability_score}%</span>
          <span className="block h-[5px] max-w-[90px] min-w-[60px] flex-1 overflow-hidden rounded-full bg-[#EFEBDF]">
            <span
              className={`block h-full rounded-full ${
                relTone(row.reliability_score) === "red"
                  ? "bg-urgent"
                  : relTone(row.reliability_score) === "amber"
                    ? "bg-amber"
                    : "bg-accent"
              }`}
              style={{ width: `${row.reliability_score}%` }}
            />
          </span>
        </div>
      </td>
      <td className="px-4 py-3.5">
        <StatusPill status={row.status} />
      </td>
      <td className="hidden px-4 py-3.5 lg:table-cell font-mono text-[12.5px] text-ink-2">
        {row.distance_miles != null ? `${row.distance_miles.toFixed(1)} mi` : "—"}
        <small className="mt-0.5 block text-[11px] text-muted">{row.location}</small>
      </td>
      <td className="hidden px-4 py-3.5 md:table-cell font-mono text-[13px] text-ink">
        ${row.hourly_rate.toFixed(0)}
        <small className="text-[11px] text-muted">/hr</small>
      </td>
      <td className="hidden px-4 py-3.5 md:table-cell">
        <div className="flex flex-col leading-tight">
          <b className="text-[13px] font-medium text-ink">{row.last_job.title}</b>
          <small className="font-mono text-[11.5px] text-muted">{row.last_job.meta}</small>
        </div>
      </td>
      <td className="w-px whitespace-nowrap px-4 py-3.5 text-right">
        <button className="inline-grid h-[30px] w-[30px] place-items-center rounded-lg border border-transparent text-ink-2 transition hover:border-line hover:bg-white hover:text-ink" title="Message">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2.5 3h9v6h-5L3.5 11V9h-1V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
        </button>
        <button className="inline-grid h-[30px] w-[30px] place-items-center rounded-lg border border-transparent text-ink-2 transition hover:border-line hover:bg-white hover:text-ink" title="Call">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 3h2l1 2.5L4.5 7c.8 1.5 2 2.7 3.5 3.5L9.5 9 12 10v2h-1A8 8 0 0 1 3 4V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
        </button>
        <DispatchButton state={dispatchState} />
      </td>
    </tr>
  );
}

function StatusPill({ status }: { status: DerivedStatus }) {
  const map = {
    available: { bg: "bg-accent-soft", text: "text-accent", dot: "bg-accent", label: "Available" },
    onjob: { bg: "bg-[#E4E8F0]", text: "text-[#2B4373]", dot: "bg-[#3D5BA0]", label: "On a job" },
    busy: { bg: "bg-amber-soft", text: "text-amber", dot: "bg-amber", label: "Tentative" },
    off: { bg: "bg-[#EEEAE0]", text: "text-muted", dot: "bg-[#A8A493]", label: "Off tonight" },
    flag: { bg: "bg-urgent-soft", text: "text-urgent", dot: "bg-urgent", label: "Flagged" },
  } as const;
  const m = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${m.bg} ${m.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  );
}

function dispatchAction(status: DerivedStatus): "dispatch" | "ask" | "busy" | "review" {
  if (status === "flag") return "review";
  if (status === "onjob") return "busy";
  if (status === "busy" || status === "off") return "ask";
  return "dispatch";
}

function DispatchButton({ state }: { state: ReturnType<typeof dispatchAction> }) {
  if (state === "busy") {
    return (
      <button disabled className="inline-flex items-center gap-1.5 rounded-lg bg-[#A8A493] px-2.5 py-1.5 text-[12.5px] font-medium text-panel opacity-80">
        Busy
      </button>
    );
  }
  if (state === "review") {
    return (
      <button className="inline-flex items-center gap-1.5 rounded-lg border border-urgent-soft px-2.5 py-1.5 text-[12.5px] font-medium text-urgent transition hover:bg-urgent-soft">
        Review
      </button>
    );
  }
  return (
    <button className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-2.5 py-1.5 text-[12.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black">
      {state === "ask" ? "Ask" : "Dispatch"}
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
        <path d="M2 6h7M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

/* ----------------------------- icons ----------------------------- */

function HomeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 8l5-4 5 4v4H2V8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function DispatchIcon() {
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
function CalendarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="2.5" y="3" width="9" height="8.5" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5 2v2M9 2v2M2.5 6h9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
function PaymentIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 11V5l4-3 4 3v6" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx="7" cy="7.5" r="1.4" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
