"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { ApiError, UnauthorizedError, api } from "@/lib/api";
import type { InviteStatus, OutreachResult, ShiftBoard, ShiftInvite } from "@/lib/types";

/* ----------------------------- helpers ----------------------------- */

const POLL_MS = 5000;

const STATUS_BADGE: Record<InviteStatus, { bg: string; text: string; dot: string; label: string }> = {
  confirmed: { bg: "bg-accent-soft", text: "text-accent", dot: "bg-accent", label: "Confirmed" },
  yes: { bg: "bg-[#DCEDE9]", text: "text-[#1E6E61]", dot: "bg-[#2C8D7C]", label: "Yes" },
  maybe: { bg: "bg-amber-soft", text: "text-amber", dot: "bg-amber", label: "Maybe" },
  no: { bg: "bg-[#EEEAE0]", text: "text-muted", dot: "bg-[#A8A493]", label: "No" },
  invited: { bg: "bg-[#E4E8F0]", text: "text-[#2B4373]", dot: "bg-[#3D5BA0]", label: "Invited" },
  cancelled: { bg: "bg-[#EEEAE0]", text: "text-muted line-through", dot: "bg-[#A8A493]", label: "Cancelled" },
};

function fmtClock(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function relTime(iso: string | null) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const min = Math.round((Date.now() - t) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.round(hr / 24)}d ago`;
}

function fmtPhone(p: string) {
  const m = p.match(/^\+1(\d{3})(\d{3})(\d{4})$/);
  return m ? `+1 (${m[1]}) ${m[2]}-${m[3]}` : p;
}

interface CallState {
  tone: "busy" | "ok" | "err";
  message: string;
}

/* ----------------------------- component ----------------------------- */

export function BoardClient({ shiftId }: { shiftId: string }) {
  const [board, setBoard] = useState<ShiftBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshLabel, setRefreshLabel] = useState("refreshing…");

  const [actionBusy, setActionBusy] = useState<"outreach" | "cascade" | null>(null);
  const [actionResult, setActionResult] = useState<{ kind: string; result: OutreachResult } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [calls, setCalls] = useState<Record<string, CallState>>({});

  const tick = useCallback(async () => {
    try {
      const data = await api.getShiftBoard(shiftId);
      setBoard(data);
      setError(null);
      setRefreshLabel(`updated ${fmtClock(new Date())}`);
    } catch (e) {
      if (e instanceof UnauthorizedError) return; // PasswordGate takes over
      setRefreshLabel("offline");
      setError(e instanceof Error ? e.message : "Failed to load board");
    }
  }, [shiftId]);

  useEffect(() => {
    const run = () => {
      void tick();
    };
    const initialId = setTimeout(run, 0);
    const intervalId = setInterval(run, POLL_MS);
    return () => {
      clearTimeout(initialId);
      clearInterval(intervalId);
    };
  }, [tick]);

  const runBatch = async (kind: "outreach" | "cascade") => {
    if (actionBusy) return;
    setActionBusy(kind);
    setActionError(null);
    try {
      const result =
        kind === "outreach"
          ? await api.sendShiftOutreach(shiftId, { batch_size: 5, match_role: true })
          : await api.cascadeShiftOutreach(shiftId, { batch_size: 3, match_role: true });
      setActionResult({ kind, result });
      void tick();
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) {
        setActionError(e instanceof Error ? e.message : "Request failed");
      }
    } finally {
      setActionBusy(null);
    }
  };

  const placeCall = async (inv: ShiftInvite) => {
    setCalls((m) => ({ ...m, [inv.contractor_id]: { tone: "busy", message: "Calling…" } }));
    try {
      const res = await api.callShiftContractor(shiftId, inv.contractor_id);
      setCalls((m) => ({
        ...m,
        [inv.contractor_id]: { tone: "ok", message: `Call placed to ${fmtPhone(res.to)}` },
      }));
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      const message =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Call failed";
      setCalls((m) => ({ ...m, [inv.contractor_id]: { tone: "err", message } }));
    }
  };

  // Group invites by batch, ordered by batch then priority.
  const batches = useMemo(() => {
    if (!board) return [];
    const byBatch = new Map<number, ShiftInvite[]>();
    for (const inv of board.invites) {
      const list = byBatch.get(inv.batch) ?? [];
      list.push(inv);
      byBatch.set(inv.batch, list);
    }
    return [...byBatch.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([batch, invites]) => ({
        batch,
        invites: invites.sort((a, b) => a.priority - b.priority),
      }));
  }, [board]);

  const job = board?.job;
  const counts = board?.counts;

  return (
    <div className="min-h-screen">
      <header
        className="sticky top-0 z-10 flex items-center justify-between border-b border-line px-6 py-3.5 backdrop-blur-md"
        style={{ background: "color-mix(in oklab, var(--color-bg) 88%, transparent)" }}
      >
        <div className="flex items-center gap-2.5 font-medium">
          <Link href="/" aria-label="CrewLoop home" className="flex items-center gap-2.5">
            <BrandMark />
            <b className="text-base font-medium text-ink">CrewLoop</b>
          </Link>
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Fill board</span>
        </div>
        <span className="font-mono text-[11px] tracking-wider text-muted">{refreshLabel}</span>
      </header>

      <main className="mx-auto w-full max-w-[1100px] px-5 pb-20 pt-7 md:px-8">
        <div className="mb-3.5 flex items-center gap-2 text-[12px] text-muted">
          <Link href="/shifts" className="hover:text-ink">
            Shifts
          </Link>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="opacity-60" aria-hidden>
            <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-ink">{job ? job.role : "…"}</span>
        </div>

        {error && !board ? (
          <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-urgent">{error}</div>
        ) : !board || !job || !counts ? (
          <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-muted">
            Loading board…
          </div>
        ) : (
          <>
            {/* Header: shift facts + big filled indicator */}
            <div className="mb-5 flex flex-wrap items-end justify-between gap-6 border-b border-line-2 pb-5">
              <div>
                <span className="eyebrow">{job.business_name}</span>
                <h1 className="font-display m-0 mt-2 mb-1.5 text-[clamp(32px,4.2vw,46px)] leading-none tracking-tight">
                  {job.role}
                </h1>
                <p className="m-0 text-[14.5px] text-ink-2">
                  {job.start_time} → {job.end_time} · {job.location} ·{" "}
                  <span className="font-mono text-ink">${job.pay_amount.toFixed(0)}</span>
                </p>
              </div>
              <div className="flex flex-col items-end leading-none">
                <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">Filled</span>
                <span className="font-display mt-1 text-[56px] tracking-tight">
                  <span className={counts.filled >= counts.needed ? "text-accent" : "text-ink"}>
                    {counts.filled}
                  </span>
                  <span className="text-[0.45em] text-muted"> of {counts.needed}</span>
                </span>
              </div>
            </div>

            {/* Counts strip */}
            <div className="mb-5 grid grid-cols-3 gap-2.5 sm:grid-cols-6">
              <CountCard label="Yes" value={counts.yes} valueClass="text-[#1E6E61]" />
              <CountCard label="Confirmed" value={counts.confirmed} valueClass="text-accent" />
              <CountCard label="Maybe" value={counts.maybe} valueClass="text-amber" />
              <CountCard label="No" value={counts.no} valueClass="text-muted" />
              <CountCard label="Awaiting reply" value={counts.invited} valueClass="text-[#2B4373]" />
              <CountCard label="At risk" value={counts.at_risk} valueClass="text-urgent" />
            </div>

            {/* Actions */}
            <div className="mb-5 flex flex-wrap items-center gap-2.5">
              <button
                onClick={() => runBatch("outreach")}
                disabled={actionBusy !== null}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-default disabled:opacity-50"
              >
                {actionBusy === "outreach" ? "Sending…" : "Send outreach (batch of 5)"}
              </button>
              <button
                onClick={() => runBatch("cascade")}
                disabled={actionBusy !== null}
                className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-4 py-2.5 text-[13.5px] font-medium text-ink transition hover:-translate-y-px hover:border-ink disabled:cursor-default disabled:opacity-50"
              >
                {actionBusy === "cascade" ? "Sending…" : "Cascade next 3"}
              </button>
              {error && <span className="text-[12.5px] text-urgent">{error}</span>}
            </div>

            {actionError && (
              <div className="mb-5 rounded-[10px] border border-urgent-soft bg-urgent-soft px-4 py-3 text-[13px] text-urgent">
                {actionError}
              </div>
            )}

            {actionResult && (
              <div className="mb-5 rounded-[10px] border border-line bg-panel px-4 py-3 text-[13px] text-ink-2">
                <b className="text-ink">
                  Batch {actionResult.result.batch}
                  {actionResult.kind === "cascade" ? " (cascade)" : ""}:
                </b>{" "}
                {actionResult.result.sent.length === 0 ? (
                  <span>no one texted — {actionResult.result.candidates} candidates matched.</span>
                ) : (
                  <span>
                    texted {actionResult.result.sent.map((s) => s.name).join(", ")} ·{" "}
                    <span className="font-mono text-[12px] text-muted">
                      {actionResult.result.candidates} candidates
                    </span>
                  </span>
                )}
                {actionResult.result.errors.length > 0 && (
                  <ul className="m-0 mt-1.5 list-disc pl-5 text-urgent">
                    {actionResult.result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* Invite table */}
            {board.invites.length === 0 ? (
              <div className="rounded-[14px] border border-line bg-panel px-6 py-14 text-center text-muted">
                No invites sent — start outreach to text your roster in priority order.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-[14px] border border-line bg-white">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <Th>Contractor</Th>
                      <Th>Status</Th>
                      <Th>Last reply</Th>
                      <Th className="hidden md:table-cell">Reliability</Th>
                      <Th className="w-px text-right" />
                    </tr>
                  </thead>
                  <tbody>
                    {batches.map(({ batch, invites }) => (
                      <BatchGroup
                        key={batch}
                        batch={batch}
                        invites={invites}
                        calls={calls}
                        placeCall={placeCall}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

/* ----------------------------- pieces ----------------------------- */

function CountCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: number;
  valueClass: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-[12px] border border-line bg-panel px-3 py-2.5">
      <span className="font-mono text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <span className={`font-display text-[26px] leading-none tracking-tight ${valueClass}`}>{value}</span>
    </div>
  );
}

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th
      className={`border-b border-line-2 bg-panel px-4 py-3 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-muted ${className}`}
    >
      {children}
    </th>
  );
}

function BatchGroup({
  batch,
  invites,
  calls,
  placeCall,
}: {
  batch: number;
  invites: ShiftInvite[];
  calls: Record<string, CallState>;
  placeCall: (inv: ShiftInvite) => void;
}) {
  return (
    <>
      <tr>
        <td
          colSpan={5}
          className="border-b border-line-2 bg-[#F4F1E8] px-4 py-1.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted"
        >
          Batch {batch} · {invites.length} invited
        </td>
      </tr>
      {invites.map((inv) => (
        <InviteRow key={inv.id} inv={inv} call={calls[inv.contractor_id]} placeCall={placeCall} />
      ))}
    </>
  );
}

function InviteRow({
  inv,
  call,
  placeCall,
}: {
  inv: ShiftInvite;
  call: CallState | undefined;
  placeCall: (inv: ShiftInvite) => void;
}) {
  const badge = STATUS_BADGE[inv.status] ?? STATUS_BADGE.invited;
  const cancelled = inv.status === "cancelled";
  const replyAt = relTime(inv.last_reply_at);

  return (
    <tr className="border-b border-line-2 transition last:border-b-0 hover:bg-[#F8F6F0]">
      <td className="px-4 py-3">
        <div className={`flex flex-col leading-tight ${cancelled ? "opacity-60" : ""}`}>
          <b className={`text-[14px] font-medium text-ink ${cancelled ? "line-through" : ""}`}>{inv.name}</b>
          <small className="font-mono text-[11.5px] text-muted">{fmtPhone(inv.phone)}</small>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${badge.bg} ${badge.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
            {badge.label}
          </span>
          {inv.at_risk && (
            <span className="inline-flex items-center whitespace-nowrap rounded-full bg-urgent-soft px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider text-urgent">
              At risk
            </span>
          )}
        </div>
      </td>
      <td className="max-w-[260px] px-4 py-3">
        {inv.last_reply_body ? (
          <div className="flex flex-col leading-tight">
            <span className="truncate text-[13px] text-ink-2" title={inv.last_reply_body}>
              “{inv.last_reply_body}”
            </span>
            {replyAt && <small className="font-mono text-[11px] text-muted">{replyAt}</small>}
          </div>
        ) : (
          <span className="text-[13px] text-muted">—</span>
        )}
      </td>
      <td className="hidden px-4 py-3 font-mono text-[12.5px] text-ink-2 md:table-cell">
        {inv.reliability_score}%
      </td>
      <td className="w-px whitespace-nowrap px-4 py-3 text-right">
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={() => placeCall(inv)}
            disabled={call?.tone === "busy"}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[12.5px] font-medium text-ink transition hover:border-ink hover:bg-panel disabled:cursor-default disabled:opacity-50"
          >
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
              <path d="M3 3h2l1 2.5L4.5 7c.8 1.5 2 2.7 3.5 3.5L9.5 9 12 10v2h-1A8 8 0 0 1 3 4V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
            {call?.tone === "busy" ? "Calling…" : "Call"}
          </button>
          {call && call.tone !== "busy" && (
            <span
              className={`max-w-[200px] truncate text-[11.5px] ${call.tone === "ok" ? "text-accent" : "text-urgent"}`}
              title={call.message}
            >
              {call.message}
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}
