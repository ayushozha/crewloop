"use client";

import Link from "next/link";
import { useState } from "react";

import { BrandMark } from "@/components/Brand";
import { api } from "@/lib/api";
import type { BrowserImportResponse } from "@/lib/types";

export function BrowserImportClient() {
  const [sourceUrl, setSourceUrl] = useState("/bay-events/staffing");
  const [forceLocal, setForceLocal] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BrowserImportResponse | null>(null);

  const engineLabel = running
    ? "importing"
    : result
      ? result.used_browser_use
        ? "browser use"
        : "local"
      : "ready";

  const confidence = result
    ? Math.round((result.browser_source.extraction_confidence || 0) * 100)
    : 0;
  const confidenceTone = confidence >= 80 ? "accent" : "urgent";

  const runImport = async () => {
    setError(null);
    setRunning(true);
    try {
      const payload = await api.browserImport({
        source_url: sourceUrl.trim() || null,
        force_local: forceLocal,
      });
      setResult(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header
        className="sticky top-0 z-10 flex h-[62px] items-center justify-between border-b border-line px-7 backdrop-blur-md"
        style={{ background: "rgba(246,244,238,0.86)" }}
      >
        <div className="flex items-center gap-2.5 font-bold">
          <BrandMark />
          <b className="text-[16px] font-medium">CrewLoop</b>
          <span className="font-mono text-[12px] text-muted">Browser Import</span>
        </div>
        <nav className="flex gap-4 text-[13px] text-muted">
          <Link href="/bay-events/staffing" target="_blank">
            Bay Events
          </Link>
          <Link href="/dashboard">Dashboard</Link>
        </nav>
      </header>

      <main className="mx-auto max-w-[1180px] px-7 pb-14 pt-8">
        <section className="mb-6 flex flex-col items-start justify-between gap-6 md:flex-row md:items-end">
          <div>
            <h1 className="font-display m-0 mb-2.5 text-[42px] leading-none tracking-tight">Web source intake</h1>
            <p className="m-0 max-w-[58ch] text-muted">
              Bay Events staffing data flows into a CrewLoop job with source evidence, imported fields, and a
              persisted BrowserSource record.
            </p>
          </div>
          <Link
            href="/bay-events/staffing"
            target="_blank"
            className="inline-flex items-center gap-2 rounded-full border border-line bg-panel px-3 py-2.5 text-[13px] font-semibold text-ink"
          >
            Open source page
          </Link>
        </section>

        {error && (
          <div className="mb-5 rounded-[12px] border border-[rgba(185,71,49,0.24)] bg-urgent-soft px-3.5 py-3 text-urgent">
            {error}
          </div>
        )}

        <section className="mb-6 grid grid-cols-1 items-center gap-2.5 rounded-[16px] border border-line bg-panel p-3 sm:grid-cols-[1fr_auto_auto]">
          <input
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            aria-label="Source URL"
            className="w-full rounded-[11px] border border-line bg-white px-3.5 py-3.5 font-medium text-[14px]"
          />
          <label className="flex items-center gap-2 whitespace-nowrap text-[13px] text-muted">
            <input
              type="checkbox"
              checked={forceLocal}
              onChange={(e) => setForceLocal(e.target.checked)}
              className="h-4 w-4"
            />
            local demo
          </label>
          <button
            onClick={runImport}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-[11px] bg-ink px-4 py-3.5 text-[14px] font-bold text-white disabled:cursor-wait disabled:opacity-55"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M5 12h13M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Import shift
          </button>
        </section>

        <section className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_390px]">
          <article className="overflow-hidden rounded-[16px] border border-line bg-panel">
            <header className="flex items-center justify-between gap-3 border-b border-line-2 px-5 py-4">
              <h2 className="m-0 text-[15px] font-bold">Imported job fields</h2>
              <span
                className={`rounded-full px-2 py-1.5 font-mono text-[11px] uppercase tracking-wider ${
                  confidenceTone === "accent" ? "bg-accent-soft text-accent" : "bg-urgent-soft text-urgent"
                }`}
              >
                {engineLabel}
              </span>
            </header>

            {!result ? (
              <div className="px-5 py-12 text-center text-muted">No import yet.</div>
            ) : (
              <>
                <FieldsGrid result={result} />
                <RecordBlock result={result} />
              </>
            )}
          </article>

          <aside className="overflow-hidden rounded-[16px] border border-line bg-panel">
            <header className="flex items-center justify-between gap-3 border-b border-line-2 px-5 py-4">
              <h2 className="m-0 text-[15px] font-bold">Source evidence</h2>
              <span
                className={`rounded-full px-2 py-1.5 font-mono text-[11px] uppercase tracking-wider ${
                  confidenceTone === "accent" ? "bg-accent-soft text-accent" : "bg-urgent-soft text-urgent"
                }`}
              >
                {confidence}%
              </span>
            </header>
            {!result?.browser_source.screenshot_url ? (
              <div className="px-5 py-12 text-center text-muted">No screenshot yet.</div>
            ) : (
              <div className="p-3.5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={result.browser_source.screenshot_url}
                  alt="Browser source evidence"
                  className="block w-full rounded-[11px] border border-line bg-white"
                />
              </div>
            )}
            {result && (
              <div className="px-5 pb-5 pt-2.5">
                {(result.browser_source.browser_action_log || []).map((step, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[22px_1fr] gap-2.5 border-b border-line-2 py-2.5 last:border-b-0"
                  >
                    <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-accent" />
                    <div>
                      <strong className="text-[13px]">{step.step}</strong>
                      <div className="mt-0.5 text-[12px] text-muted">
                        {step.status}
                        {step.url ? ` · ${step.url}` : ""}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </aside>
        </section>
      </main>
    </div>
  );
}

function FieldsGrid({ result }: { result: BrowserImportResponse }) {
  const fields = result.browser_source.imported_fields;
  const job = result.job;
  const rows: Array<[string, string]> = [
    ["Business", fields.business_name ?? "—"],
    ["Role", fields.role ?? "—"],
    ["Window", `${fields.start_time ?? "—"} - ${fields.end_time ?? "—"}`],
    ["Location", fields.location ?? "—"],
    ["Pay", `$${fields.pay_amount ?? 0}`],
    ["Urgency", fields.urgency ?? "—"],
    ["Required skills", (fields.required_skills ?? []).join(", ")],
    ["Status", job.status],
  ];

  return (
    <div className="grid grid-cols-1 border-b border-line-2 sm:grid-cols-2">
      {rows.map(([label, value], i) => (
        <div
          key={label}
          className={`border-b border-line-2 px-5 py-4 ${i % 2 === 0 ? "sm:border-r" : ""}`}
        >
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
          <div className="break-words text-[17px] font-bold text-ink">{value}</div>
        </div>
      ))}
    </div>
  );
}

function RecordBlock({ result }: { result: BrowserImportResponse }) {
  const job = result.job;
  const source = result.browser_source;
  return (
    <div className="grid gap-2 border-t border-line-2 px-5 py-4 text-[13px] text-muted">
      <div>
        <span className="font-mono">job_id</span> <span className="text-ink">{job.id}</span>
      </div>
      <div>
        <span className="font-mono">browser_source_id</span> <span className="text-ink">{source.id}</span>
      </div>
      <div>
        <span className="font-mono">source_url</span>{" "}
        <a href={source.source_url} target="_blank" rel="noreferrer" className="text-ink underline">
          {source.source_url}
        </a>
      </div>
      {source.source_html_url && (
        <div>
          <span className="font-mono">html_snapshot</span>{" "}
          <a href={source.source_html_url} target="_blank" rel="noreferrer" className="text-ink underline">
            {source.source_html_url}
          </a>
        </div>
      )}
      <Link
        href={`/dispatch/${encodeURIComponent(job.id)}`}
        className="mt-2 inline-flex w-max items-center gap-2 rounded-[11px] border border-ink bg-ink px-3.5 py-3 text-[13px] font-bold text-white"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M5 12h13M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Open dispatch room
      </Link>
    </div>
  );
}
