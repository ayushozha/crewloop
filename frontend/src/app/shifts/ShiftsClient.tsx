"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { UnauthorizedError, api } from "@/lib/api";
import type { CreateShiftPayload, Shift } from "@/lib/types";

/* ----------------------------- helpers ----------------------------- */

function statusTone(status: string): { bg: string; text: string; dot: string } {
  switch (status) {
    case "filled":
    case "confirmed":
      return { bg: "bg-accent-soft", text: "text-accent", dot: "bg-accent" };
    case "cancelled":
    case "closed":
      return { bg: "bg-[#EEEAE0]", text: "text-muted", dot: "bg-[#A8A493]" };
    default:
      // open / sourcing / in-progress states
      return { bg: "bg-[#E4E8F0]", text: "text-[#2B4373]", dot: "bg-[#3D5BA0]" };
  }
}

function fmtEventAt(iso: string | null) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return (
    d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) +
    " · " +
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  );
}

/* ----------------------------- component ----------------------------- */

const EMPTY_FORM = {
  business_name: "",
  role: "",
  location: "",
  start_time: "",
  end_time: "",
  pay_amount: "",
  headcount: "1",
  event_at: "",
};

export function ShiftsClient() {
  const router = useRouter();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listShifts()
      .then(({ items }) => {
        if (!cancelled) setShifts(items);
      })
      .catch((e) => {
        if (cancelled || e instanceof UnauthorizedError) return;
        setError(e instanceof Error ? e.message : "Failed to load shifts");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const set = (key: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const createShift = async (e: React.FormEvent) => {
    e.preventDefault();
    if (creating) return;
    const pay = Number(form.pay_amount);
    const headcount = Number(form.headcount);
    if (!Number.isFinite(pay) || pay <= 0) {
      setCreateError("Pay must be a positive number.");
      return;
    }
    if (!Number.isInteger(headcount) || headcount < 1) {
      setCreateError("Headcount must be a whole number of at least 1.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    const payload: CreateShiftPayload = {
      business_name: form.business_name.trim(),
      role: form.role.trim(),
      location: form.location.trim(),
      start_time: form.start_time.trim(),
      end_time: form.end_time.trim(),
      pay_amount: pay,
      headcount,
      ...(form.event_at ? { event_at: form.event_at } : {}),
    };
    try {
      const { shift } = await api.createShift(payload);
      router.push(`/shifts/${shift.id}`);
    } catch (err) {
      if (!(err instanceof UnauthorizedError)) {
        setCreateError(err instanceof Error ? err.message : "Failed to create shift");
      }
      setCreating(false);
    }
  };

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
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Shifts</span>
        </div>
        <nav className="flex items-center gap-5">
          <Link href="/contractors" className="text-[13px] text-ink-2 hover:text-ink">
            Contractors
          </Link>
          <Link href="/contractors/import" className="text-[13px] text-ink-2 hover:text-ink">
            Import CSV
          </Link>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-[1100px] px-5 pb-20 pt-8 md:px-8">
        <div className="mb-6 border-b border-line-2 pb-6">
          <span className="eyebrow">{shifts.length} shifts</span>
          <h1 className="font-display m-0 mt-2 mb-1.5 text-[clamp(34px,4.4vw,48px)] leading-none tracking-tight">
            Fill a shift.
          </h1>
          <p className="max-w-[58ch] text-[15px] text-ink-2">
            Post the shift, text your roster in priority order, and watch the board fill in real time.
          </p>
        </div>

        {/* New shift form */}
        <section className="mb-8 rounded-[14px] border border-line bg-panel p-5">
          <h2 className="m-0 mb-4 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
            New shift
          </h2>
          <form onSubmit={createShift} className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Business name">
              <TextInput value={form.business_name} onChange={set("business_name")} placeholder="Bay Events Co." required />
            </Field>
            <Field label="Role">
              <TextInput value={form.role} onChange={set("role")} placeholder="Bartender" required />
            </Field>
            <Field label="Location">
              <TextInput value={form.location} onChange={set("location")} placeholder="Mission, SF" required />
            </Field>
            <Field label="Pay ($)">
              <TextInput
                value={form.pay_amount}
                onChange={set("pay_amount")}
                placeholder="250"
                required
                type="number"
                min="1"
                step="any"
              />
            </Field>
            <Field label="Start time">
              <TextInput value={form.start_time} onChange={set("start_time")} placeholder="Saturday 6:00 PM" required />
            </Field>
            <Field label="End time">
              <TextInput value={form.end_time} onChange={set("end_time")} placeholder="Saturday 11:30 PM" required />
            </Field>
            <Field label="Headcount">
              <TextInput
                value={form.headcount}
                onChange={set("headcount")}
                required
                type="number"
                min="1"
                step="1"
              />
            </Field>
            <Field label="Event date & time (optional)" hint="drives the T-48h/T-4h confirmation texts">
              <TextInput value={form.event_at} onChange={set("event_at")} type="datetime-local" />
            </Field>

            <div className="flex items-end gap-3 sm:col-span-2 lg:col-span-4">
              <button
                type="submit"
                disabled={creating}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-default disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create shift"}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                  <path d="M2 6h7M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {createError && <span className="text-[13px] text-urgent">{createError}</span>}
            </div>
          </form>
        </section>

        {/* Shift list */}
        <section>
          <h2 className="m-0 mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
            All shifts
          </h2>
          {error ? (
            <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-urgent">{error}</div>
          ) : loading ? (
            <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-muted">
              Loading shifts…
            </div>
          ) : shifts.length === 0 ? (
            <div className="rounded-[14px] border border-line bg-panel px-6 py-12 text-center text-muted">
              No shifts yet — create one above to start filling it.
            </div>
          ) : (
            <div className="overflow-hidden rounded-[14px] border border-line bg-white">
              {shifts.map((s) => (
                <ShiftRow key={s.id} shift={s} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

/* ----------------------------- pieces ----------------------------- */

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">{label}</span>
      {children}
      {hint && <span className="text-[11.5px] leading-snug text-muted">{hint}</span>}
    </label>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-[10px] border border-line bg-white px-3 py-2 text-[13.5px] outline-none transition focus:border-ink placeholder:text-muted"
    />
  );
}

function ShiftRow({ shift }: { shift: Shift }) {
  const tone = statusTone(shift.status);
  const eventAt = fmtEventAt(shift.event_at);
  return (
    <Link
      href={`/shifts/${shift.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 border-b border-line-2 px-5 py-4 transition last:border-b-0 hover:bg-[#F1EEE5] md:grid-cols-[minmax(180px,1.4fr)_minmax(160px,1.4fr)_minmax(120px,1fr)_auto_auto_auto]"
    >
      <div className="flex flex-col leading-tight">
        <b className="text-[14.5px] font-medium text-ink">{shift.role}</b>
        <small className="text-[12px] text-muted">{shift.business_name}</small>
      </div>
      <div className="hidden flex-col leading-tight md:flex">
        <span className="text-[13px] text-ink-2">
          {shift.start_time} → {shift.end_time}
        </span>
        {eventAt && <small className="font-mono text-[11px] text-muted">event {eventAt}</small>}
      </div>
      <span className="hidden text-[13px] text-ink-2 md:block">{shift.location}</span>
      <span className="hidden font-mono text-[13px] text-ink md:block">
        ${shift.pay_amount.toFixed(0)}
      </span>
      <span className="font-mono text-[12.5px] text-ink">
        {shift.yes_count}
        <span className="text-muted">/{shift.headcount} filled</span>
      </span>
      <span
        className={`inline-flex items-center gap-1.5 justify-self-end whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${tone.bg} ${tone.text}`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
        {shift.status}
      </span>
    </Link>
  );
}
