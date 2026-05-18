"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { API_BASE_URL, api } from "@/lib/api";
import type { SuppliesResponse, SupplyItem } from "@/lib/api";

const VENDOR_INITIALS: Record<string, string> = {
  "K&L Wine Merchants": "KL",
  "Bevmo SoMa": "BM",
  "Restaurant Depot SF": "RD",
  "Cocktail Kingdom": "CK",
  "Local Produce Co-op": "LP",
  "WebstaurantStore": "WS",
  "Amazon Fresh": "AM",
  "Walmart": "WM",
  "Amazon": "AM",
};

const VENDOR_TINT: Record<string, string> = {
  "K&L Wine Merchants": "bg-[#E6EFE5] text-[#2C5638]",
  "Bevmo SoMa": "bg-[#F4EAD0] text-[#7A5512]",
  "Restaurant Depot SF": "bg-[#E1EBF1] text-[#2F3F66]",
  "Cocktail Kingdom": "bg-[#EDE9DC] text-[#5B5648]",
  "Local Produce Co-op": "bg-[#E6EFE5] text-[#3E7C4E]",
  "WebstaurantStore": "bg-[#F1EEE5] text-ink-2",
  "Amazon Fresh": "bg-[#FFEBC9] text-[#7A5512]",
  "Walmart": "bg-[#E1EBF1] text-[#2F3F66]",
  "Amazon": "bg-[#FFEBC9] text-[#7A5512]",
};

function fmtUSD(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

type Stage = "empty" | "recommended" | "browsing" | "approved" | "paid";

function stageOf(items: SupplyItem[]): Stage {
  if (items.length === 0) return "empty";
  if (items.every((i) => i.payment_status === "paid")) return "paid";
  if (items.every((i) => i.status === "approved")) return "approved";
  if (items.some((i) => i.bu_session_id)) return "browsing";
  return "recommended";
}

export function SuppliesClient({ eventId }: { eventId: string }) {
  const [data, setData] = useState<SuppliesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommending, setRecommending] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [paying, setPaying] = useState<"sponge" | "stripe_mpp" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listSupplies(eventId);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "couldn't load supplies");
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    void load();
  }, [load]);

  const items = data?.items ?? [];
  const stage = stageOf(items);

  // Poll while any session is still running.
  useEffect(() => {
    const stillRunning = items.some((i) => i.bu_session_id && !["completed", "idle", "error", "timed_out"].includes(i.bu_status ?? ""));
    if (!stillRunning) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.pollLiveBrowse(eventId);
        setData(res);
      } catch {
        // swallow — just keep trying
      }
    }, 3500);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [eventId, items]);

  const recommend = async (regenerate = false) => {
    setRecommending(true);
    setError(null);
    try {
      const res = await api.recommendSupplies(eventId, regenerate);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "recommendation failed");
    } finally {
      setRecommending(false);
    }
  };

  const startBrowse = async () => {
    setBrowsing(true);
    setError(null);
    try {
      const res = await api.startLiveBrowse(eventId);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "couldn't start live browse");
    } finally {
      setBrowsing(false);
    }
  };

  const approve = async () => {
    setApproving(true);
    setError(null);
    try {
      const res = await api.approveSupplies(eventId);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "approval failed");
    } finally {
      setApproving(false);
    }
  };

  const pay = async (method: "sponge" | "stripe_mpp") => {
    setPaying(method);
    setError(null);
    try {
      const res = await api.paySupplies(eventId, method);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "payment failed");
    } finally {
      setPaying(null);
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <header
        className="sticky top-0 z-10 flex items-center justify-between border-b border-line px-6 py-3.5 backdrop-blur-md"
        style={{ background: "color-mix(in oklab, var(--color-bg) 88%, transparent)" }}
      >
        <Link href="/" className="flex items-center gap-2.5 font-medium">
          <BrandMark />
          <b className="text-base font-medium text-ink">CrewLoop</b>
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Supplies</span>
        </Link>
        <div className="flex items-center gap-2 text-[13px] text-ink-2">
          <Link href="/chat" className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Chat</Link>
          <Link href="/home" className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Home</Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1180px] px-6 pb-16 pt-8 md:px-9">
        <Crumb eventRole={data?.event?.role} eventTime={data?.event?.start_time} />
        <PageHead event={data?.event} summary={data?.summary} stage={stage} />

        {error && (
          <div className="mb-5 rounded-[12px] border border-[rgba(185,71,49,0.24)] bg-urgent-soft px-3.5 py-3 text-urgent">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <Empty title="Loading supplies…" />
        ) : items.length === 0 ? (
          <EmptyState onRecommend={() => recommend(false)} loading={recommending} />
        ) : (
          <>
            <ActionBar
              stage={stage}
              recommending={recommending}
              browsing={browsing}
              approving={approving}
              paying={paying}
              total={data?.summary?.total ?? 0}
              onRegenerate={() => recommend(true)}
              onStartBrowse={startBrowse}
              onApprove={approve}
              onPay={pay}
            />

            {stage === "browsing" && <LiveBrowsePanel items={items} />}

            <section className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
              {items.map((it) => (
                <SupplyCard key={it.id} item={it} />
              ))}
            </section>

            {(stage === "approved" || stage === "paid") && <VendorEvidence items={items} />}

            {stage === "paid" && <PaidReceipts items={items} />}
          </>
        )}
      </main>
    </div>
  );
}

/* ============================ shell ============================ */

function Crumb({ eventRole, eventTime }: { eventRole?: string; eventTime?: string }) {
  return (
    <div className="mb-3.5 flex items-center gap-2 text-[12px] text-muted">
      <Link href="/home" className="hover:text-ink">Home</Link>
      <CrumbCaret />
      <span>Events</span>
      <CrumbCaret />
      <span className="text-ink">{eventRole ? `${eventRole} · ${eventTime}` : "supplies"}</span>
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

function PageHead({
  event,
  summary,
  stage,
}: {
  event: SuppliesResponse["event"] | undefined;
  summary: SuppliesResponse["summary"] | undefined;
  stage: Stage;
}) {
  const headline =
    stage === "paid"
      ? "Supplies purchased."
      : stage === "approved"
        ? "Supplies approved."
        : stage === "browsing"
          ? "Browsing vendors live…"
          : "Supplies plan.";
  const sub =
    stage === "paid"
      ? "Sponge wallet held the spend, Stripe MPP settled the merchant — both refs are below."
      : stage === "approved"
        ? "Browser Use confirmed each item in cart. Approve a payment method to settle."
        : stage === "browsing"
          ? "Each item is being researched in parallel by a Browser Use agent. You can keep working — the result will land here."
          : "Loop matched these to your pantry and a likely vendor. Run Browser Use to verify current prices, then approve.";
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-6 border-b border-line-2 pb-5">
      <div>
        <span className="eyebrow">{event ? `${event.role} · ${event.start_time}` : "supplies"}</span>
        <h1 className="font-display m-0 mt-2 mb-2 text-[clamp(34px,4.6vw,52px)] leading-none tracking-tight">{headline}</h1>
        <p className="m-0 max-w-[60ch] text-[15px] text-ink-2">{sub}</p>
      </div>
      {summary && (
        <div className="flex flex-col items-end gap-1">
          <span className="font-display text-[40px] leading-none tracking-tight">{fmtUSD(summary.total)}</span>
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
            {summary.count} items · {summary.vendors.length} vendor{summary.vendors.length === 1 ? "" : "s"}
          </span>
        </div>
      )}
    </div>
  );
}

/* ============================ action bar ============================ */

function ActionBar({
  stage,
  recommending,
  browsing,
  approving,
  paying,
  total,
  onRegenerate,
  onStartBrowse,
  onApprove,
  onPay,
}: {
  stage: Stage;
  recommending: boolean;
  browsing: boolean;
  approving: boolean;
  paying: "sponge" | "stripe_mpp" | null;
  total: number;
  onRegenerate: () => void;
  onStartBrowse: () => void;
  onApprove: () => void;
  onPay: (m: "sponge" | "stripe_mpp") => void;
}) {
  const pill =
    stage === "paid"
      ? { tone: "bg-accent-soft text-accent", dot: "bg-accent", label: "Paid · settled" }
      : stage === "approved"
        ? { tone: "bg-accent-soft text-accent", dot: "bg-accent", label: "Approved · awaiting payment" }
        : stage === "browsing"
          ? { tone: "bg-[#E1EBF1] text-[#2F3F66]", dot: "bg-[#3D5BA0]", label: "Browser Use running" }
          : { tone: "bg-amber-soft text-amber", dot: "bg-amber", label: "Awaiting browse + approval" };

  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3.5 rounded-[14px] border border-line bg-panel px-4 py-3.5">
      <div className="flex items-center gap-2 text-[13px] text-ink-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${pill.tone}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${pill.dot}`} />
          {pill.label}
        </span>
        <span className="font-mono text-[11.5px] text-muted">{fmtUSD(total)} total</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {stage !== "paid" && (
          <button
            onClick={onRegenerate}
            disabled={recommending}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-2 text-[13px] font-medium text-ink-2 transition hover:border-ink hover:text-ink disabled:cursor-wait disabled:opacity-60"
          >
            {recommending ? "Re-recommending…" : "Re-recommend"}
          </button>
        )}
        {stage === "recommended" && (
          <button
            onClick={onStartBrowse}
            disabled={browsing}
            className="inline-flex items-center gap-2 rounded-full bg-[#3D5BA0] px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-[#2F3F66] disabled:cursor-wait disabled:opacity-60"
          >
            {browsing ? "Spinning up agents…" : "Browse vendors live"}
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.4" />
              <path d="M2 7h10M7 2.5c1.5 1.5 1.5 7.5 0 9M7 2.5c-1.5 1.5-1.5 7.5 0 9" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
        )}
        {(stage === "recommended" || stage === "browsing") && (
          <button
            onClick={onApprove}
            disabled={approving}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-wait disabled:opacity-60"
          >
            {approving ? "Approving…" : stage === "browsing" ? "Skip browse · approve now" : "Approve plan"}
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <path d="M3 7l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
        {stage === "approved" && (
          <>
            <button
              onClick={() => onPay("sponge")}
              disabled={paying !== null}
              className="inline-flex items-center gap-2 rounded-full bg-accent px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-[#2F6740] disabled:cursor-wait disabled:opacity-60"
            >
              {paying === "sponge" ? "Settling…" : "Pay via Sponge wallet"}
            </button>
            <button
              onClick={() => onPay("stripe_mpp")}
              disabled={paying !== null}
              className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-2 text-[13px] font-medium text-ink transition hover:border-ink hover:-translate-y-px disabled:cursor-wait disabled:opacity-60"
            >
              {paying === "stripe_mpp" ? "Settling…" : "Pay via Stripe MPP"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ============================ live browse panel ============================ */

function LiveBrowsePanel({ items }: { items: SupplyItem[] }) {
  const live = items.filter((i) => i.bu_session_id);
  if (live.length === 0) return null;
  const totalCost = live.reduce((a, i) => a + (i.bu_cost_usd ?? 0), 0);
  const totalSteps = live.reduce((a, i) => a + (i.bu_step_count ?? 0), 0);
  const allDone = live.every((i) => ["idle", "completed", "error", "timed_out"].includes(i.bu_status ?? ""));

  return (
    <section className="mb-5 rounded-[16px] border border-line bg-panel p-4">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-display m-0 text-[22px] leading-none tracking-tight">Browser Use agents</h3>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#E1EBF1] px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-[#2F3F66]">
            <span className={`h-1.5 w-1.5 rounded-full ${allDone ? "bg-[#3D5BA0]" : "bg-[#3D5BA0] dot-pulse"}`} />
            {live.length} session{live.length === 1 ? "" : "s"}{allDone ? " · done" : " · live"}
          </span>
        </div>
        <span className="font-mono text-[11.5px] text-muted">
          {totalSteps} steps · ~${totalCost.toFixed(3)}
        </span>
      </header>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {live.map((s) => (
          <BrowseTile key={s.id} item={s} />
        ))}
      </div>
    </section>
  );
}

function BrowseTile({ item }: { item: SupplyItem }) {
  const isSim = (item.bu_session_id || "").startsWith("sim_");
  const stillRunning = !["idle", "completed", "error", "timed_out"].includes(item.bu_status ?? "");
  const vendor = item.vendor || "vendor";
  const initial = VENDOR_INITIALS[vendor] || vendor.slice(0, 2).toUpperCase();
  const tint = VENDOR_TINT[vendor] || "bg-[#F1EEE5] text-ink-2";

  return (
    <article className="overflow-hidden rounded-[12px] border border-line bg-white">
      {/* fake browser chrome */}
      <div className="flex items-center gap-1.5 border-b border-line-2 bg-[#F1EEE5] px-3 py-2">
        <span className="h-2 w-2 rounded-full bg-[#E36964]" />
        <span className="h-2 w-2 rounded-full bg-[#E3C254]" />
        <span className="h-2 w-2 rounded-full bg-[#82B97C]" />
        <span className="ml-2 truncate font-mono text-[11px] text-muted">
          {item.vendor_url || "agent.browser-use.com"}
        </span>
        <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-muted">
          {item.bu_status || "starting"}
        </span>
      </div>
      <div className="relative aspect-[16/10] bg-[#F8F6F1]">
        {item.bu_live_url ? (
          <iframe
            src={item.bu_live_url}
            title={`Browser Use · ${item.name}`}
            className="absolute inset-0 h-full w-full"
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            referrerPolicy="no-referrer"
          />
        ) : (
          <BrowsePlaceholder running={stillRunning} step={item.bu_step_count || 0} name={item.name} vendor={vendor} />
        )}
        {isSim && (
          <span className="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-panel">
            simulated
          </span>
        )}
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 px-3 py-2.5">
        <div className="min-w-0">
          <b className="block truncate text-[13.5px] font-medium text-ink">{item.name}</b>
          <span className="font-mono text-[11px] text-muted">
            {item.qty} {item.unit}
          </span>
        </div>
        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${tint}`}>
          {initial} · {vendor}
        </span>
      </div>
    </article>
  );
}

function BrowsePlaceholder({
  running,
  step,
  name,
  vendor,
}: {
  running: boolean;
  step: number;
  name: string;
  vendor: string;
}) {
  const lines = [
    `Opening ${vendor.toLowerCase().replace(/\s+/g, "")}.com…`,
    `Searching for "${name}"…`,
    `Comparing prices across listings…`,
    `Adding ${name} to cart…`,
    `Capturing checkout snapshot…`,
  ];
  const idx = Math.min(lines.length - 1, Math.max(0, Math.floor(step / 2)));
  return (
    <div className="absolute inset-0 flex flex-col justify-center gap-2 px-4">
      {lines.map((l, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 font-mono text-[11.5px] transition ${i <= idx ? "text-ink-2" : "text-muted/50"}`}
        >
          <span
            className={`grid h-3.5 w-3.5 place-items-center rounded-full ${
              i < idx
                ? "bg-accent text-panel"
                : i === idx && running
                  ? "border border-accent bg-panel tl-pulse"
                  : "border border-line bg-white"
            }`}
          >
            {i < idx && (
              <span
                className="block h-[3px] w-[5px]"
                style={{ borderLeft: "1.5px solid #fff", borderBottom: "1.5px solid #fff", transform: "rotate(-45deg) translate(0,-1px)" }}
              />
            )}
          </span>
          {l}
        </div>
      ))}
    </div>
  );
}

/* ============================ supply card ============================ */

function SupplyCard({ item }: { item: SupplyItem }) {
  const approved = item.status === "approved";
  const paid = item.payment_status === "paid";
  const vendor = item.vendor || "vendor";
  const tint = VENDOR_TINT[vendor] || "bg-[#F1EEE5] text-ink-2";
  const initial = VENDOR_INITIALS[vendor] || vendor.slice(0, 2).toUpperCase();
  const imgSrc = item.image_path ? `${API_BASE_URL}${item.image_path}` : null;

  return (
    <article className="overflow-hidden rounded-[14px] border border-line bg-white">
      <div className="grid grid-cols-[96px_minmax(0,1fr)]">
        {imgSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imgSrc} alt={item.name} className="h-full w-[96px] object-cover" />
        ) : (
          <div className="grid h-full w-[96px] place-items-center bg-panel font-mono text-[11px] text-muted">{initial}</div>
        )}
        <div className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <b className="block text-[15px] font-medium text-ink">{item.name}</b>
              <span className="block font-mono text-[12px] text-muted">
                {item.qty} {item.unit} · {fmtUSD(item.unit_price)}/{item.unit.split(" ")[0]}
              </span>
            </div>
            <span className="font-display text-[20px] leading-none tracking-tight">{fmtUSD(item.total_price)}</span>
          </div>

          <div className="mt-2.5 flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${tint}`}>
              <span className="rounded-sm bg-current/10 px-1 text-[9px] font-bold">{initial}</span>
              {vendor}
            </span>
            {item.vendor_url && (
              <a
                href={item.vendor_url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-[11px] text-muted underline-offset-2 hover:text-ink hover:underline"
              >
                {new URL(item.vendor_url).hostname.replace("www.", "")}
              </a>
            )}
            {paid && item.payment_ref && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-accent">
                paid · {item.payment_ref.slice(0, 12)}…
              </span>
            )}
          </div>

          {item.notes && (
            <p className="mt-2.5 m-0 text-[13px] leading-snug text-ink-2">{item.notes}</p>
          )}

          {approved && item.evidence_eta && (
            <div className="mt-3 grid grid-cols-[18px_minmax(0,1fr)] gap-2 rounded-lg border border-accent-soft bg-accent-soft px-2.5 py-2 text-[12px] text-accent">
              <span className="grid h-4 w-4 place-items-center rounded-sm bg-accent">
                <span
                  className="block h-[3px] w-[6px]"
                  style={{ borderLeft: "1.5px solid #fff", borderBottom: "1.5px solid #fff", transform: "rotate(-45deg) translate(0,-1px)" }}
                />
              </span>
              <div className="leading-tight">
                <b className="block font-medium">ETA · {item.evidence_eta}</b>
                {item.evidence_note && <span className="mt-0.5 block text-[11.5px] opacity-90">{item.evidence_note}</span>}
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

/* ============================ post-approval ============================ */

function VendorEvidence({ items }: { items: SupplyItem[] }) {
  const byVendor = useMemo(() => {
    const m: Record<string, { items: SupplyItem[]; total: number; url: string | null; eta: string | null }> = {};
    for (const i of items) {
      const v = i.vendor || "vendor";
      if (!m[v]) m[v] = { items: [], total: 0, url: i.vendor_url ?? null, eta: i.evidence_eta ?? null };
      m[v].items.push(i);
      m[v].total += i.total_price;
    }
    return m;
  }, [items]);

  return (
    <section className="mt-7 rounded-[16px] border border-line bg-panel p-5">
      <header className="mb-3.5 flex items-center justify-between">
        <h3 className="font-display m-0 text-[22px] leading-none tracking-tight">Browser Use evidence</h3>
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">checkout confirmed</span>
      </header>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {Object.entries(byVendor).map(([vendor, info]) => (
          <article key={vendor} className="rounded-[12px] border border-line bg-white p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-[14px] font-medium text-ink">{vendor}</span>
              <span className="font-mono text-[12px] text-muted">{fmtUSD(info.total)}</span>
            </div>
            {info.url && (
              <a href={info.url} target="_blank" rel="noreferrer" className="block font-mono text-[12px] text-muted underline-offset-2 hover:text-ink hover:underline">
                {info.url}
              </a>
            )}
            {info.eta && (
              <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-accent">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" /> ETA · {info.eta}
              </div>
            )}
            <ul className="mt-3 grid gap-1.5">
              {info.items.map((i) => (
                <li key={i.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-3 text-[12.5px] text-ink-2">
                  <span className="truncate">{i.name} <span className="font-mono text-[11px] text-muted">× {i.qty}</span></span>
                  <span className="font-mono text-[11.5px] text-muted">{fmtUSD(i.total_price)}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function PaidReceipts({ items }: { items: SupplyItem[] }) {
  const method = items.find((i) => i.payment_method)?.payment_method ?? "sponge";
  const total = items.reduce((a, i) => a + (i.total_price || 0), 0);
  const methodLabel = method === "sponge" ? "Sponge wallet" : "Stripe MPP";
  return (
    <section className="mt-7 rounded-[16px] border border-accent-soft bg-accent-soft p-5">
      <header className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-panel">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 7l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <h3 className="font-display m-0 text-[22px] leading-none tracking-tight text-accent">
            Paid via {methodLabel}
          </h3>
        </div>
        <span className="font-mono text-[12px] text-accent">{fmtUSD(total)} · {items.length} items</span>
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((i) => (
          <div key={i.id} className="flex items-center justify-between rounded-lg border border-white/40 bg-white px-3 py-2 text-[13px]">
            <div className="min-w-0">
              <b className="block truncate font-medium text-ink">{i.name}</b>
              <span className="font-mono text-[10.5px] text-muted">{i.payment_ref}</span>
            </div>
            <span className="font-mono text-[12px] text-ink-2">{fmtUSD(i.total_price)}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 mb-0 text-[12.5px] text-accent/80">
        {method === "sponge"
          ? "Sponge wallet held the full spend with the same release rules as worker pay. Settled when each vendor confirms delivery."
          : "Stripe MPP routed the payout to each vendor's connected account. Receipts emailed to Bay Events Co."}
      </p>
    </section>
  );
}

/* ============================ empty state ============================ */

function EmptyState({ onRecommend, loading }: { onRecommend: () => void; loading: boolean }) {
  return (
    <div className="rounded-[16px] border border-line bg-panel px-6 py-12 text-center">
      <h3 className="font-display m-0 mb-2 text-[28px] leading-none tracking-tight">No supplies planned yet.</h3>
      <p className="m-0 mx-auto mb-5 max-w-[52ch] text-[14.5px] text-ink-2">
        Loop will check the event details against the pantry and recommend 3–5 items to buy ahead of service.
      </p>
      <button
        onClick={onRecommend}
        disabled={loading}
        className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-[14px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-wait disabled:opacity-60"
      >
        {loading ? "Recommending…" : "Recommend supplies"}
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
          <path d="M3 7h8M7.5 3.5L11 7l-3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}

function Empty({ title }: { title: string }) {
  return (
    <div className="rounded-[16px] border border-line bg-panel px-6 py-12 text-center text-muted">
      {title}
    </div>
  );
}
