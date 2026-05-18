"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

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
};

const VENDOR_TINT: Record<string, string> = {
  "K&L Wine Merchants": "bg-[#E6EFE5] text-[#2C5638]",
  "Bevmo SoMa": "bg-[#F4EAD0] text-[#7A5512]",
  "Restaurant Depot SF": "bg-[#E1EBF1] text-[#2F3F66]",
  "Cocktail Kingdom": "bg-[#EDE9DC] text-[#5B5648]",
  "Local Produce Co-op": "bg-[#E6EFE5] text-[#3E7C4E]",
  "WebstaurantStore": "bg-[#F1EEE5] text-ink-2",
};

function fmtUSD(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function SuppliesClient({ eventId }: { eventId: string }) {
  const [data, setData] = useState<SuppliesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommending, setRecommending] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
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

  const items = data?.items ?? [];
  const allApproved = items.length > 0 && items.every((i) => i.status === "approved");
  const allRecommended = items.length > 0 && items.every((i) => i.status === "recommended");

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
        <PageHead event={data?.event} summary={data?.summary} allApproved={allApproved} />

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
              status={allApproved ? "approved" : allRecommended ? "recommended" : "mixed"}
              recommending={recommending}
              approving={approving}
              onApprove={approve}
              onRegenerate={() => recommend(true)}
              total={data?.summary?.total ?? 0}
            />

            <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {items.map((it) => (
                <SupplyCard key={it.id} item={it} />
              ))}
            </section>

            {allApproved && <VendorEvidence items={items} />}
          </>
        )}
      </main>
    </div>
  );
}

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
  allApproved,
}: {
  event: SuppliesResponse["event"] | undefined;
  summary: SuppliesResponse["summary"] | undefined;
  allApproved: boolean;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-6 border-b border-line-2 pb-5">
      <div>
        <span className="eyebrow">{event ? `${event.role} · ${event.start_time}` : "supplies"}</span>
        <h1 className="font-display m-0 mt-2 mb-2 text-[clamp(34px,4.6vw,52px)] leading-none tracking-tight">
          {allApproved ? "Supplies approved." : "Supplies plan."}
        </h1>
        <p className="m-0 max-w-[60ch] text-[15px] text-ink-2">
          {allApproved
            ? "Browser Use simulated checkout on each vendor. Items are queued for delivery and will close out automatically when the event finishes."
            : "Loop matched these to your pantry and a likely vendor for each. Approve to fire the Browser Use checkout."}
        </p>
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

function ActionBar({
  status,
  recommending,
  approving,
  onApprove,
  onRegenerate,
  total,
}: {
  status: "recommended" | "approved" | "mixed";
  recommending: boolean;
  approving: boolean;
  onApprove: () => void;
  onRegenerate: () => void;
  total: number;
}) {
  const approved = status === "approved";
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3.5 rounded-[14px] border border-line bg-panel px-4 py-3.5">
      <div className="flex items-center gap-2 text-[13px] text-ink-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${
            approved
              ? "bg-accent-soft text-accent"
              : "bg-amber-soft text-amber"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${approved ? "bg-accent" : "bg-amber"}`} />
          {approved ? "Approved · Browser Use checkout" : "Awaiting owner approval"}
        </span>
        <span className="font-mono text-[11.5px] text-muted">{fmtUSD(total)} total</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onRegenerate}
          disabled={recommending}
          className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-2 text-[13px] font-medium text-ink-2 transition hover:border-ink hover:text-ink disabled:cursor-wait disabled:opacity-60"
        >
          {recommending ? "Re-recommending…" : "Re-recommend"}
        </button>
        {!approved && (
          <button
            onClick={onApprove}
            disabled={approving}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-wait disabled:opacity-60"
          >
            {approving ? "Checking out…" : "Approve & purchase"}
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <path d="M3 7h8M7.5 3.5L11 7l-3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

function SupplyCard({ item }: { item: SupplyItem }) {
  const approved = item.status === "approved";
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

          <div className="mt-2.5 flex items-center gap-2">
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

function VendorEvidence({ items }: { items: SupplyItem[] }) {
  // Group by vendor for the post-approval evidence summary.
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
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">simulated checkout</span>
      </header>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {Object.entries(byVendor).map(([vendor, info]) => (
          <article key={vendor} className="rounded-[12px] border border-line bg-white p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-[14px] font-medium text-ink">{vendor}</span>
              <span className="font-mono text-[12px] text-muted">{fmtUSD(info.total)}</span>
            </div>
            {info.url && (
              <a
                href={info.url}
                target="_blank"
                rel="noreferrer"
                className="block font-mono text-[12px] text-muted underline-offset-2 hover:text-ink hover:underline"
              >
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
