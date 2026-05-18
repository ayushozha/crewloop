"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { API_BASE_URL, api } from "@/lib/api";
import type {
  DispatchContractor,
  DispatchPayload,
  DispatchTimelineEvent,
  SuppliesResponse,
  SupplyItem,
} from "@/lib/api";

/* ============================== helpers ============================== */

const money = (v: number | string | null | undefined) =>
  `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const moneyExact = (v: number) =>
  `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const cap = (v: string | undefined) =>
  v ? v.charAt(0).toUpperCase() + v.slice(1) : "";
const assetUrl = (src: string | null | undefined) =>
  !src ? "" : src.startsWith("http") ? src : `${API_BASE_URL}${src.startsWith("/") ? "" : "/"}${src}`;

type ChipTone = "default" | "green" | "red" | "amber" | "blue" | "purple";

function chipClasses(tone: ChipTone = "default") {
  const map: Record<ChipTone, string> = {
    default: "bg-[#ECE7DC] text-muted",
    green:   "bg-accent-soft text-accent",
    red:     "bg-urgent-soft text-urgent",
    amber:   "bg-[#F4EAD0] text-amber",
    blue:    "bg-[#E1EBF1] text-[#315B7A]",
    purple:  "bg-[#E5DEEF] text-[#5C3E94]",
  };
  return `inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${map[tone]}`;
}

/* ============================== component ============================== */

export function DispatchClient({ jobId }: { jobId: string }) {
  const [dispatch, setDispatch] = useState<DispatchPayload | null>(null);
  const [supplies, setSupplies] = useState<SuppliesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [invoiceState, setInvoiceState] = useState<"draft" | "sent" | "paid">("draft");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [d, s] = await Promise.all([
        api.getDispatch(jobId),
        api.listSupplies(jobId).catch(() => null),
      ]);
      setDispatch(d);
      setSupplies(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Event Fulfillment Room unavailable");
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

  /* ---- derived numbers ---- */
  const invoice = useMemo(() => computeInvoice(dispatch, supplies), [dispatch, supplies]);
  const workerPayments = useMemo(() => computeWorkerPayments(dispatch), [dispatch]);

  if (error) {
    return (
      <div className="min-h-screen bg-bg">
        <Topbar jobId={jobId} />
        <main className="mx-auto max-w-[1440px] px-6 py-8">
          <div className="rounded-lg border border-[rgba(185,71,49,0.24)] bg-urgent-soft px-4 py-3.5 text-urgent">
            {error}
          </div>
        </main>
      </div>
    );
  }

  if (!dispatch) {
    return (
      <div className="min-h-screen bg-bg">
        <Topbar jobId={jobId} />
        <main className="mx-auto max-w-[1440px] px-6 py-8">
          <div className="px-5 py-12 text-center text-muted">Loading Event Fulfillment Room…</div>
        </main>
      </div>
    );
  }

  const { job, contractors, timeline, payment, proof, owner_summary, web_source } = dispatch;

  return (
    <div className="min-h-screen bg-bg">
      <Topbar jobId={jobId} />

      <main className="mx-auto max-w-[1440px] px-5 pb-20 pt-7 md:px-8">
        <PageHead job={job} contractors={contractors} supplies={supplies} invoice={invoice} />

        <ActionStrip
          job={job}
          payment={payment}
          proof={proof}
          acting={acting}
          onAction={doAction}
        />

        {/* TOP ROW: event card + timeline + owner summary */}
        <div className="mt-5 grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(360px,1.05fr)_minmax(440px,1.25fr)_minmax(320px,0.95fr)]">
          <section className="grid gap-4">
            <EventRequestCard job={job} />
            <WebSourcePanel source={web_source} />
          </section>
          <section className="grid gap-4">
            <TimelinePanel timeline={timeline} />
            <CrewPanel contractors={contractors} />
          </section>
          <section className="grid gap-4">
            <OwnerSummaryPanel
              summary={owner_summary}
              invoice={invoice}
              payment={payment}
              workers={workerPayments}
            />
            <ProofPanel proof={proof} />
          </section>
        </div>

        {/* BOTTOM ROW: supplies + invoice + worker payments */}
        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <SupplyPanel supplies={supplies} jobId={jobId} />
          <InvoicePanel
            invoice={invoice}
            state={invoiceState}
            onSend={() => setInvoiceState("sent")}
            onMarkPaid={() => setInvoiceState("paid")}
          />
          <WorkerPaymentsPanel
            workers={workerPayments}
            jobPayment={payment}
            onApproveAll={() => doAction("approve-release", { owner_approved: true })}
            acting={acting === "approve-release"}
          />
        </div>
      </main>
    </div>
  );
}

/* ============================== panels ============================== */

function Topbar({ jobId }: { jobId: string }) {
  return (
    <header
      className="sticky top-0 z-10 flex items-center justify-between border-b border-line px-6 py-3.5 backdrop-blur-md"
      style={{ background: "color-mix(in oklab, var(--color-bg) 88%, transparent)" }}
    >
      <Link href="/" className="flex items-center gap-2.5 font-medium">
        <BrandMark />
        <b className="text-base font-medium text-ink">CrewLoop</b>
        <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Event Fulfillment Room</span>
      </Link>
      <nav className="hidden gap-2 text-[13px] text-ink-2 md:flex">
        <Link href="/home" className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Home</Link>
        <Link href="/chat" className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Chat</Link>
        <Link href={`/events/${jobId}/supplies`} className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Supplies</Link>
        <Link href="/contractors" className="rounded-full border border-line px-3 py-1.5 hover:border-ink">Roster</Link>
      </nav>
    </header>
  );
}

function PageHead({
  job,
  contractors,
  supplies,
  invoice,
}: {
  job: DispatchPayload["job"];
  contractors: DispatchContractor[];
  supplies: SuppliesResponse | null;
  invoice: ComputedInvoice;
}) {
  const filled = contractors.filter((c) => c.status === "recommended" || c.status === "ready").length;
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-5 border-b border-line-2 pb-5">
      <div>
        <span className="eyebrow">
          {job.business_name} · {job.location} · {job.start_time}
        </span>
        <h1 className="font-display m-0 mt-2 mb-1.5 text-[clamp(34px,4.4vw,52px)] leading-none tracking-tight">
          {cap(job.role)} event.
        </h1>
        <p className="m-0 max-w-[68ch] text-[15px] text-ink-2">
          {job.description ||
            "Fulfill this event end-to-end — crew, supplies, invoice, worker pay, proof, audit trail."}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className={chipClasses(urgencyTone(job.urgency))}>{job.urgency}</span>
          <span className={chipClasses("blue")}>{job.status}</span>
          <span className={chipClasses("default")}>
            Crew {filled}/{contractors.length || "—"}
          </span>
          {supplies && supplies.items.length > 0 && (
            <span className={chipClasses("default")}>
              Supplies {supplies.summary.count} · {moneyExact(supplies.summary.total)}
            </span>
          )}
          <span className={chipClasses("amber")}>Invoice {moneyExact(invoice.total)}</span>
        </div>
      </div>
    </div>
  );
}

function urgencyTone(u: string): ChipTone {
  if (u === "urgent") return "red";
  if (u === "standard") return "default";
  return "amber";
}

function ActionStrip({
  job,
  payment,
  proof,
  acting,
  onAction,
}: {
  job: DispatchPayload["job"];
  payment: DispatchPayload["payment"];
  proof: DispatchPayload["proof"];
  acting: string | null;
  onAction: (
    action: "outreach" | "accept" | "check-in" | "approve-release",
    body?: Record<string, unknown>,
  ) => void;
}) {
  const hasProof = (proof.items || []).some((i) => i.status === "received");
  const paymentReleased = payment.status === "released";
  const sentLike = ["outreach_sent", "accepted", "completed"].includes(job.status);
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-[14px] border border-line bg-panel px-3 py-2.5">
      <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Workflow</span>
      <ActionBtn
        primary
        disabled={sentLike || acting === "outreach"}
        onClick={() => onAction("outreach", { send_real: false })}
      >
        Send outreach
      </ActionBtn>
      <ActionBtn
        disabled={["accepted", "completed"].includes(job.status) || acting === "accept"}
        onClick={() => onAction("accept", { response: "yes, I can take it" })}
      >
        Simulate accept
      </ActionBtn>
      <ActionBtn
        disabled={!job.assigned_contractor_id || hasProof || acting === "check-in"}
        onClick={() =>
          onAction("check-in", { proof_type: "sms", content: "Arrived at venue and checked in by SMS." })
        }
      >
        Check in
      </ActionBtn>
      <ActionBtn
        disabled={!hasProof || paymentReleased || acting === "approve-release"}
        onClick={() => onAction("approve-release", { owner_approved: true })}
      >
        Approve release
      </ActionBtn>
    </div>
  );
}

function ActionBtn({
  children,
  onClick,
  disabled,
  primary = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-[30px] items-center justify-center gap-2 rounded-md px-2.5 py-1.5 text-[12.5px] font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
        primary
          ? "bg-ink text-panel hover:bg-black"
          : "border border-line bg-white text-ink hover:border-ink"
      }`}
    >
      {children}
    </button>
  );
}

function Panel({
  title,
  headRight,
  children,
  className = "",
}: {
  title: string;
  headRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article
      className={`overflow-hidden rounded-[14px] border border-line bg-panel ${className}`}
      style={{ boxShadow: "0 1px 0 rgba(22,20,16,0.02), 0 18px 50px -36px rgba(22,20,16,0.22)" }}
    >
      <header className="flex items-center justify-between gap-3 border-b border-line-2 px-4 py-3.5">
        <h2 className="m-0 font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
          {title}
        </h2>
        {headRight}
      </header>
      <div className="bg-panel">{children}</div>
    </article>
  );
}

function EventRequestCard({ job }: { job: DispatchPayload["job"] }) {
  return (
    <Panel
      title="Event Request"
      headRight={<span className={chipClasses(urgencyTone(job.urgency))}>{job.urgency}</span>}
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-4 p-4 text-[13.5px] text-ink-2">
        <Field label="Role" value={cap(job.role)} />
        <Field label="Time" value={`${job.start_time} – ${job.end_time}`} />
        <Field label="Location" value={job.location} />
        <Field label="Pay" value={money(job.pay_amount)} />
        <Field label="Required skills" value={(job.required_skills || []).join(", ") || "—"} wide />
        <Field label="Status" value={job.status} />
        {job.description && <Field label="Description" value={job.description} wide />}
      </div>
      <div className="border-t border-line-2 px-4 py-3">
        <span className="mr-2 font-mono text-[10px] uppercase tracking-wider text-muted">Outcomes</span>
        <span className={`${chipClasses("default")} mr-1`}>Staff</span>
        <span className={`${chipClasses("default")} mr-1`}>Supplies</span>
        <span className={`${chipClasses("default")} mr-1`}>Invoice</span>
        <span className={chipClasses("default")}>Pay</span>
      </div>
    </Panel>
  );
}

function Field({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="break-words text-[14px] font-medium text-ink">{value}</div>
    </div>
  );
}

function TimelinePanel({ timeline }: { timeline: DispatchTimelineEvent[] }) {
  return (
    <Panel title="Live Timeline" headRight={<span className={chipClasses("blue")}>stream</span>}>
      <div className="px-4 pb-3.5 pt-2">
        {timeline.map((event, i) => (
          <div
            key={i}
            className="grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2.5 border-b border-line-2 py-3 last:border-b-0"
          >
            <span className={`mx-auto mt-1.5 h-2.5 w-2.5 rounded-full ${nodeColor(event.status)}`} />
            <div>
              <div className="text-[13.5px] font-medium text-ink">{event.label}</div>
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
  if (status === "pending") return "bg-amber";
  if (status === "blocked") return "bg-urgent";
  return "bg-[#BDB5A7]";
}

function CrewPanel({ contractors }: { contractors: DispatchContractor[] }) {
  return (
    <Panel
      title="Crew Plan + Match List"
      headRight={<span className={chipClasses("green")}>{contractors.length} ranked</span>}
    >
      <div>
        {contractors.length === 0 ? (
          <div className="px-5 py-8 text-center text-muted">No contractors yet</div>
        ) : (
          contractors.map((c) => {
            const photoUrl = c.profile_image_url ? assetUrl(c.profile_image_url) : null;
            return (
              <div
                key={c.name}
                className={`grid grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-3 border-b border-line-2 px-4 py-3.5 last:border-b-0 ${
                  c.status === "recommended" ? "bg-[rgba(47,111,78,0.06)]" : ""
                }`}
              >
                {photoUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={photoUrl} alt={c.name} className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <div className="grid h-10 w-10 place-items-center rounded-full bg-[#E8E1D4] text-[13px] font-bold text-[#514A3E]">
                    {c.initials}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="text-[14px] font-medium text-ink">{c.name}</b>
                    <span className={chipClasses(crewStatusTone(c.status))}>{c.status}</span>
                  </div>
                  <div className="mt-1 truncate text-[12px] text-muted">
                    {(c.skills || []).join(", ")} · {c.distance_miles} mi · {c.reliability_score}% reliability ·{" "}
                    {c.response_speed}
                  </div>
                </div>
                <div className="text-right font-mono text-[16px] font-bold">
                  {c.match_score}
                  <span className="mt-0.5 block font-mono text-[10px] font-medium uppercase tracking-wider text-muted">
                    match
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}

function crewStatusTone(status: string): ChipTone {
  if (status === "recommended") return "green";
  if (status === "backup" || status === "ready") return "blue";
  if (status === "partial") return "amber";
  return "default";
}

/* ---- Supply panel (real data) ---- */

function SupplyPanel({ supplies, jobId }: { supplies: SuppliesResponse | null; jobId: string }) {
  if (!supplies || supplies.items.length === 0) {
    return (
      <Panel title="Supply Panel" headRight={<span className={chipClasses("amber")}>not planned</span>}>
        <div className="px-4 py-5 text-[13px] text-ink-2">
          No supplies planned yet for this event.
          <Link
            href={`/events/${jobId}/supplies`}
            className="ml-1 inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline"
          >
            Open supplies panel →
          </Link>
        </div>
      </Panel>
    );
  }
  const tone: ChipTone =
    supplies.summary.status === "approved"
      ? "green"
      : supplies.items.some((i) => i.bu_session_id)
        ? "blue"
        : "amber";
  return (
    <Panel
      title="Supply Panel"
      headRight={<span className={chipClasses(tone)}>{supplies.summary.status}</span>}
    >
      <div className="border-b border-line-2 px-4 py-3 text-[12.5px] text-ink-2">
        {supplies.summary.count} items · {supplies.summary.vendors.length} vendor
        {supplies.summary.vendors.length === 1 ? "" : "s"} ·{" "}
        <b className="font-medium text-ink">{moneyExact(supplies.summary.total)}</b>
      </div>
      <div>
        {supplies.items.slice(0, 5).map((it) => (
          <SupplyRow key={it.id} item={it} />
        ))}
      </div>
      <div className="border-t border-line-2 bg-white px-4 py-3 text-right">
        <Link
          href={`/events/${jobId}/supplies`}
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-accent underline-offset-2 hover:underline"
        >
          Open full panel →
        </Link>
      </div>
    </Panel>
  );
}

function SupplyRow({ item }: { item: SupplyItem }) {
  const imgSrc = item.image_path ? assetUrl(item.image_path) : null;
  return (
    <div className="grid grid-cols-[44px_minmax(0,1fr)_auto] items-center gap-3 border-b border-line-2 px-4 py-2.5 last:border-b-0">
      {imgSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={imgSrc} alt={item.name} className="h-11 w-11 rounded-md object-cover" />
      ) : (
        <div className="h-11 w-11 rounded-md bg-[#F1EEE5]" />
      )}
      <div className="min-w-0">
        <b className="block truncate text-[13.5px] font-medium text-ink">{item.name}</b>
        <span className="block truncate font-mono text-[11px] text-muted">
          {item.qty} {item.unit} · {item.vendor}
        </span>
      </div>
      <div className="text-right">
        <div className="font-mono text-[12.5px] text-ink">{moneyExact(item.total_price)}</div>
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted">
          {item.payment_status === "paid" ? "paid" : item.status}
        </div>
      </div>
    </div>
  );
}

/* ---- Invoice panel (computed) ---- */

interface ComputedInvoice {
  labor: number;
  supplies: number;
  service_fee: number;
  total: number;
  deposit: number;
  balance: number;
  crew_count: number;
}

function computeInvoice(
  dispatch: DispatchPayload | null,
  supplies: SuppliesResponse | null,
): ComputedInvoice {
  const crewCount = dispatch?.contractors.length || 0;
  const perHead = Number(dispatch?.job.pay_amount || 0);
  const labor = perHead * Math.max(crewCount, 1);
  const supTotal = supplies?.summary.total ?? 0;
  const fee = Math.round((labor + supTotal) * 0.1 * 100) / 100;
  const total = Math.round((labor + supTotal + fee) * 100) / 100;
  return {
    labor: Math.round(labor * 100) / 100,
    supplies: Math.round(supTotal * 100) / 100,
    service_fee: fee,
    total,
    deposit: Math.round(total * 0.5 * 100) / 100,
    balance: Math.round(total * 0.5 * 100) / 100,
    crew_count: crewCount,
  };
}

function InvoicePanel({
  invoice,
  state,
  onSend,
  onMarkPaid,
}: {
  invoice: ComputedInvoice;
  state: "draft" | "sent" | "paid";
  onSend: () => void;
  onMarkPaid: () => void;
}) {
  const tone: ChipTone = state === "paid" ? "green" : state === "sent" ? "blue" : "amber";
  return (
    <Panel title="Invoice Panel" headRight={<span className={chipClasses(tone)}>{state}</span>}>
      <div className="border-b border-line-2 px-4 py-3.5">
        <div className="flex items-baseline justify-between">
          <span className="font-display text-[36px] leading-none tracking-tight">
            {moneyExact(invoice.total)}
          </span>
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">total invoice</span>
        </div>
      </div>
      <div className="grid gap-2 px-4 py-3.5 text-[13px] text-ink-2">
        <InvoiceLine label={`Labor · ${invoice.crew_count} crew`} amount={invoice.labor} />
        <InvoiceLine label="Supplies" amount={invoice.supplies} />
        <InvoiceLine label="Service fee · 10%" amount={invoice.service_fee} />
        <div className="my-1 border-t border-line-2" />
        <InvoiceLine label="Deposit (50%)" amount={invoice.deposit} muted />
        <InvoiceLine label="Balance due" amount={invoice.balance} muted />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line-2 bg-white px-4 py-3">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
          AgentMail · client.team@bayevents.co
        </span>
        {state === "draft" && (
          <button
            onClick={onSend}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-3 py-1.5 text-[12.5px] font-medium text-panel hover:bg-black"
          >
            Send invoice
          </button>
        )}
        {state === "sent" && (
          <button
            onClick={onMarkPaid}
            className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1.5 text-[12.5px] font-medium text-panel hover:bg-[#2F6740]"
          >
            Mark deposit received
          </button>
        )}
        {state === "paid" && (
          <span className="font-mono text-[11px] uppercase tracking-wider text-accent">Deposit · received</span>
        )}
      </div>
    </Panel>
  );
}

function InvoiceLine({ label, amount, muted = false }: { label: string; amount: number; muted?: boolean }) {
  return (
    <div className={`flex items-center justify-between ${muted ? "text-muted" : ""}`}>
      <span>{label}</span>
      <span className="font-mono text-[12.5px]">{moneyExact(amount)}</span>
    </div>
  );
}

/* ---- Worker payments (synthesized per contractor) ---- */

interface WorkerPaymentRow {
  name: string;
  role: string;
  amount: number;
  status: "held" | "blocked" | "released" | "pending";
  release_conditions: Array<{ label: string; complete: boolean }>;
}

function computeWorkerPayments(dispatch: DispatchPayload | null): WorkerPaymentRow[] {
  if (!dispatch) return [];
  const perHead = Number(dispatch.job.pay_amount || 0);
  const hasProof = (dispatch.proof?.items || []).some((i) => i.status === "received");
  const released = dispatch.payment.status === "released";
  return dispatch.contractors.slice(0, 6).map((c) => ({
    name: c.name,
    role: dispatch.job.role,
    amount: perHead,
    status: released ? "released" : hasProof ? "held" : "pending",
    release_conditions: [
      { label: "Accepted shift", complete: c.status === "recommended" || c.status === "ready" },
      { label: "Checked in", complete: hasProof },
      { label: "Proof submitted", complete: hasProof },
      { label: "Owner approved", complete: released },
    ],
  }));
}

function WorkerPaymentsPanel({
  workers,
  jobPayment,
  onApproveAll,
  acting,
}: {
  workers: WorkerPaymentRow[];
  jobPayment: DispatchPayload["payment"];
  onApproveAll: () => void;
  acting: boolean;
}) {
  const releasable = workers.some((w) => w.status === "held");
  const total = workers.reduce((a, w) => a + w.amount, 0);
  const released = jobPayment.status === "released";
  return (
    <Panel
      title="Worker Payment Panel"
      headRight={
        <span className={chipClasses(released ? "green" : releasable ? "amber" : "default")}>
          {released ? "released" : releasable ? "ready to release" : jobPayment.status}
        </span>
      }
    >
      <div className="border-b border-line-2 px-4 py-3.5">
        <div className="flex items-baseline justify-between">
          <span className="font-display text-[28px] leading-none tracking-tight">{moneyExact(total)}</span>
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
            {workers.length} workers · Sponge wallet
          </span>
        </div>
      </div>
      <div className="max-h-[260px] overflow-auto">
        {workers.length === 0 ? (
          <div className="px-4 py-6 text-center text-muted">No workers yet</div>
        ) : (
          workers.map((w) => (
            <div
              key={w.name}
              className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-line-2 px-4 py-2.5 last:border-b-0"
            >
              <div className="min-w-0">
                <b className="block truncate text-[13px] font-medium text-ink">{w.name}</b>
                <span className="block truncate font-mono text-[11px] text-muted">{cap(w.role)}</span>
              </div>
              <div className="text-right">
                <div className="font-mono text-[12.5px] text-ink">{moneyExact(w.amount)}</div>
                <div className="mt-1">
                  <span
                    className={chipClasses(
                      w.status === "released" ? "green" : w.status === "held" ? "amber" : "default",
                    )}
                  >
                    {w.status}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      <div className="border-t border-line-2 bg-white px-4 py-3">
        <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">Release conditions</div>
        <div className="flex flex-wrap gap-1.5">
          {(workers[0]?.release_conditions || [
            { label: "Accepted shift", complete: false },
            { label: "Checked in", complete: false },
            { label: "Proof submitted", complete: false },
            { label: "Owner approved", complete: false },
          ]).map((r) => (
            <span
              key={r.label}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${
                r.complete ? "bg-accent-soft text-accent" : "bg-[#F0EDE3] text-muted"
              }`}
            >
              {r.complete && (
                <span
                  className="block h-[3px] w-[5px]"
                  style={{
                    borderLeft: "1.5px solid currentColor",
                    borderBottom: "1.5px solid currentColor",
                    transform: "rotate(-45deg) translate(0,-1px)",
                  }}
                />
              )}
              {r.label}
            </span>
          ))}
        </div>
        <button
          onClick={onApproveAll}
          disabled={!releasable || acting}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px hover:bg-[#2F6740] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {acting ? "Releasing…" : released ? "Released" : releasable ? "Approve release for all" : "Awaiting proof"}
        </button>
      </div>
    </Panel>
  );
}

/* ---- Proof + Owner Summary + Web Source ---- */

function ProofPanel({ proof }: { proof: DispatchPayload["proof"] }) {
  return (
    <Panel
      title="Proof Panel"
      headRight={<span className={chipClasses(proof.status === "received" ? "green" : "amber")}>{proof.status}</span>}
    >
      <div className="grid gap-2.5 px-4 py-3.5">
        {proof.items.length === 0 ? (
          <div className="px-2 py-4 text-center text-muted">No proof received yet</div>
        ) : (
          proof.items.map((it, i) => (
            <div
              key={i}
              className="grid grid-cols-[18px_minmax(0,1fr)] items-start gap-2.5 border-b border-line-2 py-2 last:border-b-0"
            >
              <span className="mt-0.5 h-3 w-3 rounded-md border border-line bg-white" />
              <div>
                <b className="block text-[13px] font-medium text-ink">{it.type}</b>
                <div className="mt-0.5 text-[12px] text-muted">
                  {it.status} · {it.detail}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}

function OwnerSummaryPanel({
  summary,
  invoice,
  payment,
  workers,
}: {
  summary: DispatchPayload["owner_summary"];
  invoice: ComputedInvoice;
  payment: DispatchPayload["payment"];
  workers: WorkerPaymentRow[];
}) {
  return (
    <Panel title="Owner Summary" headRight={<span className={chipClasses("blue")}>{summary.business_name}</span>}>
      <div className="px-4 py-3.5">
        <p className="m-0 mb-3 text-[14.5px] font-medium leading-snug text-ink">{summary.message}</p>
        <div className="grid gap-2.5">
          <SummaryRow label="Crew" value={`${workers.length} confirmed`} />
          <SummaryRow label="ETA" value={summary.eta} />
          <SummaryRow label="Per-head pay" value={money(summary.pay)} />
          <SummaryRow label="Supplies" value={moneyExact(invoice.supplies)} />
          <SummaryRow label="Invoice total" value={moneyExact(invoice.total)} />
          <SummaryRow label="Proof" value={summary.proof} />
          <SummaryRow label="Worker pay" value={cap(payment.status)} />
        </div>
      </div>
    </Panel>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[22px_minmax(0,1fr)] gap-2.5 border-b border-line-2 py-1.5 last:border-b-0">
      <span className="mt-1 h-3 w-3 rounded-md border border-line bg-white" />
      <div>
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted">{label}</div>
        <div className="text-[13.5px] font-medium text-ink">{value}</div>
      </div>
    </div>
  );
}

function WebSourcePanel({ source }: { source: DispatchPayload["web_source"] }) {
  if (!source) {
    return (
      <Panel title="Web Source Panel" headRight={<span className={chipClasses("amber")}>none</span>}>
        <div className="px-4 py-6 text-center text-muted">No Browser Use source attached.</div>
      </Panel>
    );
  }
  return (
    <Panel
      title="Web Source Panel"
      headRight={
        <span className={chipClasses("green")}>
          {Math.round((source.extraction_confidence || 0) * 100)}%
        </span>
      }
    >
      <div className="grid gap-2 px-4 py-3 text-[12px] text-muted">
        <div>
          <span className="font-mono">source</span>{" "}
          <a
            href={source.source_url}
            target="_blank"
            rel="noreferrer"
            className="break-words text-ink underline-offset-2 hover:underline"
          >
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
            <a
              href={source.source_html_url}
              target="_blank"
              rel="noreferrer"
              className="text-ink underline-offset-2 hover:underline"
            >
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
            className="block w-full rounded-md border border-line bg-white"
          />
        </div>
      )}
    </Panel>
  );
}
