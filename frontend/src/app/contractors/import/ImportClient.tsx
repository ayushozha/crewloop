"use client";

import Link from "next/link";
import { useState } from "react";

import { BrandMark } from "@/components/Brand";
import { ApiError, UnauthorizedError, api } from "@/lib/api";
import type { ContractorImportResult } from "@/lib/types";

const PLACEHOLDER = `name,phone,roles,priority,rate,notes
Maria Lopez,+14155550101,bartender;server,1,38,Fast replies
Devon Park,+14155550102,server,2,32,`;

export function ImportClient() {
  const [csvText, setCsvText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ContractorImportResult | null>(null);
  const [rowErrors, setRowErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") setCsvText(reader.result);
    };
    reader.onerror = () => setError("Could not read that file.");
    reader.readAsText(file);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !csvText.trim()) return;
    setSubmitting(true);
    setResult(null);
    setRowErrors([]);
    setError(null);
    try {
      const res = await api.importContractors(csvText);
      setResult(res);
      setRowErrors(res.errors);
    } catch (err) {
      if (err instanceof UnauthorizedError) return;
      if (err instanceof ApiError && err.status === 422) {
        const detail = (err.body as { detail?: { errors?: unknown } } | null)?.detail;
        const errors = Array.isArray(detail?.errors)
          ? detail.errors.filter((x): x is string => typeof x === "string")
          : [];
        setError("Import rejected — no rows were saved.");
        setRowErrors(errors.length > 0 ? errors : [err.message]);
      } else {
        setError(err instanceof Error ? err.message : "Import failed");
      }
    } finally {
      setSubmitting(false);
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
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Import roster</span>
        </div>
        <nav className="flex items-center gap-5">
          <Link href="/contractors" className="text-[13px] text-ink-2 hover:text-ink">
            Contractors
          </Link>
          <Link href="/shifts" className="text-[13px] text-ink-2 hover:text-ink">
            Shifts
          </Link>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-[760px] px-5 pb-20 pt-8 md:px-8">
        <div className="mb-6 border-b border-line-2 pb-6">
          <span className="eyebrow">Roster</span>
          <h1 className="font-display m-0 mt-2 mb-1.5 text-[clamp(32px,4.2vw,44px)] leading-none tracking-tight">
            Import your roster.
          </h1>
          <p className="max-w-[58ch] text-[15px] text-ink-2">
            Paste a CSV or pick a file. Existing contractors (matched by phone) are updated, new ones
            are created.
          </p>
        </div>

        <form onSubmit={submit} className="rounded-[14px] border border-line bg-panel p-5">
          <p className="m-0 mb-3 text-[12.5px] leading-relaxed text-muted">
            Columns: <b className="text-ink-2">name</b> and <b className="text-ink-2">phone</b> are
            required; <span className="font-mono text-[12px]">roles, priority, rate, notes, email, location</span>{" "}
            are optional. Multiple roles split on <span className="font-mono text-[12px]">;</span>
          </p>

          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder={PLACEHOLDER}
            rows={12}
            spellCheck={false}
            className="w-full resize-y rounded-[10px] border border-line bg-white px-3 py-2.5 font-mono text-[12.5px] leading-relaxed outline-none transition focus:border-ink placeholder:text-muted"
          />

          <div className="mt-3.5 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={submitting || !csvText.trim()}
              className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-panel transition hover:-translate-y-px hover:bg-black disabled:cursor-default disabled:opacity-50"
            >
              {submitting ? "Importing…" : "Import CSV"}
            </button>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-line px-3.5 py-2 text-[13px] font-medium text-ink transition hover:-translate-y-px hover:border-ink">
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path d="M7 9V2.5M4.5 5L7 2.5L9.5 5M3 9.5v2h8v-2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Choose file…
              <input type="file" accept=".csv,text/csv,text/plain" onChange={onFile} className="hidden" />
            </label>
            {error && <span className="text-[13px] text-urgent">{error}</span>}
          </div>
        </form>

        {result && (
          <div className="mt-5 rounded-[14px] border border-line bg-panel p-5">
            <h2 className="m-0 mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-muted">
              Import result
            </h2>
            <div className="flex flex-wrap gap-6">
              <Stat label="Imported" value={result.imported} valueClass="text-accent" />
              <Stat label="Updated" value={result.updated} valueClass="text-ink" />
              <Stat label="Rows" value={result.total_rows} valueClass="text-ink-2" />
              <Stat label="Errors" value={result.errors.length} valueClass={result.errors.length > 0 ? "text-urgent" : "text-muted"} />
            </div>
            {result.errors.length === 0 && (
              <p className="m-0 mt-3 text-[13px] text-ink-2">
                Roster updated — see it on the{" "}
                <Link href="/contractors" className="text-ink underline underline-offset-2">
                  contractors page
                </Link>
                .
              </p>
            )}
          </div>
        )}

        {rowErrors.length > 0 && (
          <div className="mt-5 rounded-[14px] border border-urgent-soft bg-urgent-soft/60 p-5">
            <h2 className="m-0 mb-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-urgent">
              Row errors
            </h2>
            <ul className="m-0 list-disc pl-5 text-[13px] leading-relaxed text-urgent">
              {rowErrors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, valueClass }: { label: string; value: number; valueClass: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{label}</span>
      <span className={`font-display text-[30px] leading-none tracking-tight ${valueClass}`}>{value}</span>
    </div>
  );
}
