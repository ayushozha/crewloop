"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { BrandMark } from "@/components/Brand";
import type { DispatchContractor, DispatchPayload, DispatchTimelineEvent } from "@/lib/api";
import { api } from "@/lib/api";

const money = (v: number | string | null | undefined) =>
  `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const cap = (v: string | undefined) => (v ? v.charAt(0).toUpperCase() + v.slice(1) : "");

type ChipTone = "default" | "green" | "red" | "amber" | "blue";

function chipClasses(tone: ChipTone = "default") {
  const map: Record<ChipTone, string> = {
    default: "bg-[#ECE7DC] text-muted",
    green: "bg-accent-soft text-accent",
    red: "bg-urgent-soft text-urgent",
    amber: "bg-[#F1E7D0] text-[#9A6A18]",
    blue: "bg-[#E1EBF1] text-[#315B7A]",
  };
  return `inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-wider ${map[tone]}`;
}

function statusTone(status: string): ChipTone {
  if (status === "recommended") return "green";
  if (status === "backup" || status === "ready") return "blue";
  if (status === "partial") return "amber";
  return "red";
}

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SendIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path d="M4 12L20 4l-4 16-4-7-8-1Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
  </svg>
);

export function DispatchClient({ jobId }: { jobId: string }) {
  const [data, setData] = useState<DispatchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const payload = await api.getDispatch(jobId);
      setData(payload);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dispatch room unavailable");
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  const doAction = async (
    action: "outreach" | "accept" | "check-in" | "approve-release",
    body: Record<string, unknown> = {},
  ) => {
    setActing(action);
    try {
      await api.dispatchAction(jobId, action, body);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActing(null);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen">
        <Topbar />
        <main className="mx-auto max-w-[1440px] px-6 py-8">
          <div className="rounded-lg border border-[rgba(185,71,49,0.24)] bg-urgent-soft px-4 py-3.5 text-urgent">
            {error}
          </div>
        </main>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen">
        <Topbar />
        <main className="mx-auto max-w-[1440px] px-6 py-8">
          <div className="px-5 py-12 text-center text-muted">Loading…</div>
        </main>
      </div>
    );
  }

  const { job, contractors, timeline, payment, proof, owner_summary, web_source } = data;
  const recommended = contractors[0];
  const hasProof = (proof.items || []).some((i) => i.status === "received");
  const paymentReleased = payment.status === "released";

  return (
    <div className="min-h-screen">
      <Topbar />

      <main className="mx-auto max-w-[1440px] px-6 py-7">
        <section className="mb-5 grid grid-cols-1 items-end gap-5 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <h1 className="font-display m-0 mb-2 text-[42px] leading-none tracking-tight">
              {cap(job.role)} shift
            </h1>
            <p className="m-0 max-w-[72ch] text-muted">
              {job.business_name} · {job.location} · {job.start_time} - {job.end_time}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2.5">
            <div className="flex flex-wrap justify-end gap-2">
              <span className={chipClasses("red")}>{job.urgency}</span>
              <span className={chipClasses("blue")}>{job.status}</span>
              <span className={chipClasses("green")}>
                {recommended ? recommended.name : "No match"}
              </span>
              <span className={chipClasses("amber")}>{money(job.pay_amount)}</span>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <ActionButton
                onClick={() => doAction("outreach", { send_real: false })}
                disabled={["outreach_sent", "accepted", "completed"].includes(job.status) || acting === "outreach"}
                primary
                icon={<SendIcon />}
              >
                Send outreach
              </ActionButton>
              <ActionButton
                onClick={() => doAction("accept", { response: "yes, I can take it" })}
                disabled={["accepted", "completed"].includes(job.status) || acting === "accept"}
                icon={<CheckIcon />}
              >
                Simulate accept
              </ActionButton>
              <ActionButton
                onClick={() =>
                  doAction("check-in", {
                    proof_type: "sms",
                    content: "Arrived at venue and checked in by SMS.",
                  })
                }
                disabled={!job.assigned_contractor_id || hasProof || acting === "check-in"}
                icon={<CheckIcon />}
              >
                Check in
              </ActionButton>
              <ActionButton
                onClick={() => doAction("approve-release", { owner_approved: true })}
                disabled={!hasProof || paymentReleased || acting === "approve-release"}
                icon={<CheckIcon />}
              >
                Approve release
              </ActionButton>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(320px,1.05fr)_minmax(340px,1.25fr)_minmax(300px,0.9fr)]">
          <section className="grid gap-4">
            <JobCard job={job} />
            <ContractorCard contractors={contractors} />
            <WebSourceCard source={web_source} />
          </section>
          <section className="grid gap-4">
            <TimelineCard timeline={timeline} />
          </section>
          <section className="grid gap-4">
            <PaymentCard
              payment={payment}
              disabled={!hasProof || paymentReleased}
              onApprove={() => doAction("approve-release", { owner_approved: true })}
            />
            <ProofCard proof={proof} />
            <OwnerSummaryCard summary={owner_summary} />
          </section>
        </div>
      </main>
    </div>
  );
}

function Topbar() {
  return (
    <header
      className="sticky top-0 z-10 flex h-[62px] items-center justify-between gap-4 border-b border-line px-6 backdrop-blur-md"
      style={{ background: "rgba(246,244,238,0.88)" }}
    >
      <Link href="/" className="flex items-center gap-2.5 font-bold">
        <BrandMark />
        <b className="text-[16px] font-medium">CrewLoop</b>
        <span className="font-mono text-[12px] text-muted">Dispatch Room</span>
      </Link>
      <nav className="hidden gap-4 text-[13px] text-muted md:flex">
        <Link href="/browser-import">Browser Import</Link>
        <Link href="/bay-events/staffing" target="_blank">
          Bay Events
        </Link>
        <Link href="/dashboard">Dashboard</Link>
      </nav>
    </header>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  primary = false,
  icon,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-[34px] items-center justify-center gap-2 rounded-lg border px-2.5 py-2 text-[12.5px] font-extrabold transition disabled:cursor-not-allowed disabled:opacity-50 ${
        primary
          ? "border-ink bg-ink text-white hover:bg-black"
          : "border-line bg-white text-ink hover:border-ink"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

function Panel({ title, headRight, children }: { title: string; headRight?: React.ReactNode; children: React.ReactNode }) {
  return (
    <article
      className="overflow-hidden rounded-lg border border-line bg-panel"
      style={{ boxShadow: "0 1px 0 rgba(22,20,16,0.02), 0 18px 50px -36px rgba(22,20,16,0.22)" }}
    >
      <header className="flex items-center justify-between gap-3 border-b border-line-2 px-4 py-3.5">
        <h2 className="m-0 text-[14px] font-bold">{title}</h2>
        {headRight}
      </header>
      {children}
    </article>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border-b border-r border-line-2 px-3.5 py-3.5 last:border-r-0">
      <div className="mb-2 font-mono text-[10.5px] uppercase tracking-wider text-muted">{label}</div>
      <div className="break-words text-[15px] font-bold text-ink">{value}</div>
    </div>
  );
}

function JobCard({ job }: { job: DispatchPayload["job"] }) {
  return (
    <Panel title="Job Request" headRight={<span className={chipClasses("red")}>{job.urgency}</span>}>
      <div className="grid grid-cols-1 border-l border-t border-line-2 sm:grid-cols-2">
        <Field label="Role" value={cap(job.role)} />
        <Field label="Time" value={`${job.start_time} - ${job.end_time}`} />
        <Field label="Location" value={job.location} />
        <Field label="Pay" value={money(job.pay_amount)} />
        <Field label="Required skills" value={(job.required_skills || []).join(", ")} />
        <Field label="Status" value={job.status} />
      </div>
      {job.description && <div className="px-4 py-4 text-ink-2">{job.description}</div>}
    </Panel>
  );
}

function ContractorCard({ contractors }: { contractors: DispatchContractor[] }) {
  return (
    <Panel
      title="Contractor Match List"
      headRight={<span className={chipClasses("green")}>{contractors.length} ranked</span>}
    >
      <div>
        {contractors.map((c) => (
          <div
            key={c.name}
            className={`grid grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-3 border-b border-line-2 px-4 py-3.5 last:border-b-0 ${
              c.status === "recommended" ? "bg-[rgba(47,111,78,0.08)]" : ""
            }`}
          >
            <div className="grid h-10 w-10 place-items-center rounded-full bg-[#E8E1D4] text-[13px] font-extrabold text-[#514A3E]">
              {c.initials}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 font-extrabold">
                {c.name}
                <span className={chipClasses(statusTone(c.status))}>{c.status}</span>
              </div>
              <div className="mt-1 break-words text-[12.5px] text-muted">
                {(c.skills || []).join(", ")} · {c.distance_miles} mi · {c.reliability_score}% reliability ·{" "}
                {c.response_speed} · {c.memory_source || "seeded_moss_memory"}
              </div>
            </div>
            <div className="text-right font-mono text-[18px] font-bold">
              {c.match_score}
              <span className="mt-1 block font-mono text-[10px] font-medium uppercase tracking-wider text-muted">
                match
              </span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function TimelineCard({ timeline }: { timeline: DispatchTimelineEvent[] }) {
  return (
    <Panel title="Live Timeline" headRight={<span className={chipClasses("blue")}>stream ready</span>}>
      <div className="px-4 pb-3.5 pt-2">
        {timeline.map((event, i) => (
          <div
            key={i}
            className="grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2.5 border-b border-line-2 py-3 last:border-b-0"
          >
            <span className={`mx-auto mt-1.5 h-2.5 w-2.5 rounded-full ${nodeColor(event.status)}`} />
            <div>
              <div className="font-extrabold">{event.label}</div>
              <div className="mt-1 break-words text-[12.5px] text-muted">{event.detail}</div>
            </div>
            <div className="mt-1 whitespace-nowrap font-mono text-[11px] text-muted">{event.time}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function nodeColor(status: string) {
  if (status === "complete") return "bg-accent";
  if (status === "ready") return "bg-[#315B7A]";
  if (status === "pending") return "bg-[#9A6A18]";
  if (status === "blocked") return "bg-urgent";
  return "bg-[#BDB5A7]";
}

function PaymentCard({
  payment,
  disabled,
  onApprove,
}: {
  payment: DispatchPayload["payment"];
  disabled: boolean;
  onApprove: () => void;
}) {
  return (
    <Panel title="Payment Panel" headRight={<span className={chipClasses("amber")}>{payment.status}</span>}>
      <div className="px-4 py-4">
        <div className="-mx-4 mb-3.5 grid grid-cols-1 border-y border-line-2 sm:grid-cols-2">
          <Field label="Amount" value={money(payment.amount)} />
          <Field label="Provider" value={payment.provider} />
        </div>
        <div className="grid gap-2.5">
          {payment.release_conditions.map((item) => (
            <div key={item.label} className="grid grid-cols-[22px_minmax(0,1fr)] items-start gap-2.5 border-b border-line-2 py-2.5 last:border-b-0">
              <span
                className={`mt-0.5 grid h-[18px] w-[18px] place-items-center rounded-md border ${
                  item.complete ? "border-accent bg-accent text-white" : "border-line text-muted"
                }`}
              >
                {item.complete && <CheckIcon />}
              </span>
              <div className="font-extrabold">{item.label}</div>
            </div>
          ))}
        </div>
        <div className="mt-3.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <button
            disabled
            className="inline-flex min-h-[40px] items-center justify-center gap-2 rounded-lg border border-ink bg-ink px-3 py-3 font-extrabold text-white opacity-50"
          >
            <SendIcon />
            Hold payment
          </button>
          <button
            onClick={onApprove}
            disabled={disabled}
            className="inline-flex min-h-[40px] items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 py-3 font-extrabold text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckIcon />
            Approve release
          </button>
        </div>
      </div>
    </Panel>
  );
}

function ProofCard({ proof }: { proof: DispatchPayload["proof"] }) {
  return (
    <Panel title="Proof Panel" headRight={<span className={chipClasses("amber")}>{proof.status}</span>}>
      <div className="grid gap-2.5 px-4 py-4">
        {proof.items.map((item, i) => (
          <div key={i} className="grid grid-cols-[22px_minmax(0,1fr)] items-start gap-2.5 border-b border-line-2 py-2.5 last:border-b-0">
            <span className="mt-0.5 grid h-[18px] w-[18px] place-items-center rounded-md border border-line text-muted" />
            <div>
              <div className="font-extrabold">{item.type}</div>
              <div className="mt-0.5 text-[12.5px] text-muted">
                {item.status} · {item.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function OwnerSummaryCard({ summary }: { summary: DispatchPayload["owner_summary"] }) {
  return (
    <Panel title="Owner Summary" headRight={<span className={chipClasses("blue")}>{summary.business_name}</span>}>
      <div className="px-4 py-4">
        <p className="m-0 mb-3 text-[16px] font-bold leading-tight">{summary.message}</p>
        <div className="grid gap-2.5">
          {[
            ["Confirmed contractor", summary.confirmed_contractor],
            ["ETA", summary.eta],
            ["Pay", money(summary.pay)],
            ["Proof", summary.proof],
            ["Payment", summary.payment_status],
          ].map(([label, value]) => (
            <div key={label} className="grid grid-cols-[22px_minmax(0,1fr)] items-start gap-2.5 border-b border-line-2 py-2.5 last:border-b-0">
              <span className="mt-0.5 grid h-[18px] w-[18px] place-items-center rounded-md border border-line text-muted" />
              <div>
                <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{label}</div>
                <div className="font-extrabold">{value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function WebSourceCard({ source }: { source: DispatchPayload["web_source"] }) {
  if (!source) {
    return (
      <Panel title="Web Source Panel" headRight={<span className={chipClasses("amber")}>none</span>}>
        <div className="px-5 py-12 text-center text-muted">No browser source attached.</div>
      </Panel>
    );
  }
  return (
    <Panel
      title="Web Source Panel"
      headRight={<span className={chipClasses("green")}>{Math.round((source.extraction_confidence || 0) * 100)}%</span>}
    >
      <div className="grid gap-2.5 px-4 py-3.5 text-[12.5px] text-muted">
        <div>
          <span className="font-mono">source</span>{" "}
          <a href={source.source_url} target="_blank" rel="noreferrer" className="break-words text-ink underline">
            {source.source_url}
          </a>
        </div>
        <div>
          <span className="font-mono">type</span> {source.source_type}
        </div>
        <div>
          <span className="font-mono">update</span> {source.update_status}
        </div>
        {source.source_html_url && (
          <div>
            <span className="font-mono">snapshot</span>{" "}
            <a href={source.source_html_url} target="_blank" rel="noreferrer" className="text-ink underline">
              HTML captured
            </a>
          </div>
        )}
      </div>
      {source.screenshot_url && (
        <div className="border-t border-line-2 p-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={source.screenshot_url}
            alt="Captured staffing source"
            className="block w-full rounded-lg border border-line bg-white"
          />
        </div>
      )}
    </Panel>
  );
}
