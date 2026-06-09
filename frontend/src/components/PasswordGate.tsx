"use client";

import { Fragment, useEffect, useState } from "react";

import { BrandMark } from "@/components/Brand";
import {
  UNAUTHORIZED_EVENT,
  UnauthorizedError,
  api,
  setAppPassword,
} from "@/lib/api";

/**
 * Wraps operator pages behind the backend's X-App-Password check.
 *
 * Children render optimistically. If any API request answers 401 (the api
 * layer dispatches UNAUTHORIZED_EVENT) — or the mount-time probe fails — the
 * page is replaced by a minimal unlock card. A successful unlock stores the
 * password in localStorage and remounts children so they refetch.
 */
export function PasswordGate({ children }: { children: React.ReactNode }) {
  const [locked, setLocked] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  // Bumped after a successful unlock so children remount and refetch.
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const onUnauthorized = () => setLocked(true);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  // Probe once on mount so pages that don't fetch immediately still gate.
  useEffect(() => {
    api.listShifts().catch(() => {
      // A 401 already dispatched UNAUTHORIZED_EVENT; other failures (API
      // down, network) are surfaced by the page's own error states.
    });
  }, []);

  const unlock = async (e: React.FormEvent) => {
    e.preventDefault();
    const candidate = password.trim();
    if (!candidate || checking) return;
    setChecking(true);
    setError(null);
    setAppPassword(candidate);
    try {
      await api.listShifts();
      setPassword("");
      setLocked(false);
      setEpoch((n) => n + 1);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setError("That password was rejected — check it and try again.");
      } else {
        setError(err instanceof Error ? err.message : "Could not reach the API.");
      }
    } finally {
      setChecking(false);
    }
  };

  if (locked) {
    return (
      <div className="grid min-h-screen place-items-center px-5">
        <form
          onSubmit={unlock}
          className="w-full max-w-[360px] rounded-[14px] border border-line bg-panel p-6"
        >
          <div className="mb-5 flex items-center gap-2.5">
            <BrandMark />
            <b className="text-[15px] font-medium tracking-tight">CrewLoop</b>
          </div>
          <h1 className="font-display m-0 mb-1.5 text-[26px] leading-tight tracking-tight">
            Workspace locked
          </h1>
          <p className="mb-4 text-[13.5px] leading-relaxed text-ink-2">
            This workspace requires the app password to talk to the API.
          </p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="App password"
            autoFocus
            autoComplete="current-password"
            className="w-full rounded-[10px] border border-line bg-white px-3 py-2.5 text-[14px] outline-none transition focus:border-ink placeholder:text-muted"
          />
          {error && <p className="mt-2 text-[12.5px] text-urgent">{error}</p>}
          <button
            type="submit"
            disabled={checking || !password.trim()}
            className="mt-3.5 w-full rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-panel transition hover:bg-black disabled:cursor-default disabled:opacity-50"
          >
            {checking ? "Checking…" : "Unlock"}
          </button>
          <p className="mt-3 text-center font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
            Stored locally on this device
          </p>
        </form>
      </div>
    );
  }

  return <Fragment key={epoch}>{children}</Fragment>;
}
