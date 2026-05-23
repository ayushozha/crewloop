"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { api } from "@/lib/api";
import type { Call, Conversation, Message } from "@/lib/types";

interface ThreadItem {
  kind: "msg" | "call";
  at: string;
  data: Message | Call;
}

function fmtTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return (
    d.toLocaleDateString([], { month: "short", day: "numeric" }) +
    " · " +
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  );
}

function fmtRefresh(d: Date) {
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function DashboardClient() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [thread, setThread] = useState<{
    conversation: Conversation;
    messages: Message[];
    calls: Call[];
  } | null>(null);
  const [refreshLabel, setRefreshLabel] = useState<string>("refreshing…");

  const fetchConversations = useCallback(async () => {
    const { items } = await api.listConversations();
    setConversations(items);
  }, []);

  const fetchThread = useCallback(async (phone: string) => {
    try {
      const data = await api.getConversation(phone);
      setThread(data);
    } catch {
      setThread(null);
    }
  }, []);

  const tick = useCallback(async () => {
    setRefreshLabel("refreshing…");
    try {
      await fetchConversations();
      if (selectedPhone) await fetchThread(selectedPhone);
      setRefreshLabel(`updated ${fmtRefresh(new Date())}`);
    } catch {
      setRefreshLabel("offline");
    }
  }, [fetchConversations, fetchThread, selectedPhone]);

  useEffect(() => {
    const run = () => {
      void tick();
    };
    const initialId = setTimeout(run, 0);
    const intervalId = setInterval(run, 5000);
    return () => {
      clearTimeout(initialId);
      clearInterval(intervalId);
    };
  }, [tick]);

  const items = useMemo<ThreadItem[]>(() => {
    if (!thread) return [];
    return [
      ...thread.messages.map((m) => ({ kind: "msg" as const, at: m.created_at, data: m })),
      ...thread.calls.map((c) => ({ kind: "call" as const, at: c.started_at, data: c })),
    ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [thread]);

  const onSelect = (phone: string) => {
    setSelectedPhone(phone);
    fetchThread(phone);
  };

  return (
    <div className="flex h-screen flex-col">
      <header
        className="sticky top-0 z-10 flex items-center justify-between border-b border-line px-6 py-3.5 backdrop-blur-md"
        style={{ background: "color-mix(in oklab, var(--color-bg) 88%, transparent)" }}
      >
        <div className="flex items-center gap-2.5 font-medium">
          <Link href="/" aria-label="CrewLoop home" className="flex items-center gap-2.5">
            <BrandMark />
            <b className="text-base font-medium text-ink">CrewLoop</b>
          </Link>
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">· Conversations</span>
        </div>
        <span className="font-mono text-[11px] tracking-wider text-muted">{refreshLabel}</span>
      </header>

      <div className="grid h-[calc(100vh-57px)] grid-cols-1 md:grid-cols-[340px_1fr]">
        <aside className="overflow-auto border-r border-line bg-panel md:block">
          <div className="flex items-baseline justify-between border-b border-line-2 px-5 py-4">
            <h2 className="font-display m-0 text-[22px] leading-tight tracking-tight">Conversations</h2>
            <span className="font-mono text-[11px] text-muted">{conversations.length}</span>
          </div>
          {conversations.length === 0 ? (
            <div className="px-5 py-8 text-[13.5px] text-muted">
              No conversations yet. Send an SMS via{" "}
              <span className="font-mono">POST /api/sms/send</span> to start one.
            </div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => onSelect(c.phone)}
                className={`grid w-full grid-cols-[1fr_auto] gap-x-3 gap-y-1.5 border-b border-line-2 px-5 py-3.5 text-left transition hover:bg-[#F0EDE3] ${
                  selectedPhone === c.phone ? "bg-[#EDE9DC]" : ""
                }`}
              >
                <div className="text-[14px] font-medium text-ink">{c.display_name || c.phone}</div>
                <div className="self-start font-mono text-[11px] text-muted">{fmtTime(c.last_message_at)}</div>
                <div className="col-span-full overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-ink-2">
                  {c.last_direction === "outbound" ? "→ " : "← "}
                  {c.last_message ?? "(no messages)"}
                </div>
                <div className="col-span-full flex items-center gap-2 font-mono text-[10.5px] tracking-wide text-muted">
                  <span>{c.message_count ?? 0} msg</span>
                  {c.call_count ? (
                    <span>
                      · {c.call_count} call{c.call_count === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </div>
              </button>
            ))
          )}
        </aside>

        <main className="overflow-auto">
          {thread ? (
            <>
              <div className="flex items-baseline justify-between gap-4 border-b border-line px-7 py-5">
                <div>
                  <h1 className="font-display m-0 text-[30px] leading-none tracking-tight">
                    {thread.conversation.display_name || thread.conversation.phone}
                  </h1>
                  <div className="font-mono text-[11.5px] tracking-wider text-muted">
                    {thread.conversation.phone} · {thread.messages.length} message
                    {thread.messages.length === 1 ? "" : "s"}
                    {thread.calls.length
                      ? ` · ${thread.calls.length} call${thread.calls.length === 1 ? "" : "s"}`
                      : ""}
                  </div>
                </div>
              </div>
              {items.length === 0 ? (
                <Placeholder>No messages yet</Placeholder>
              ) : (
                <div className="flex max-w-[780px] flex-col gap-2.5 px-7 py-6">
                  {items.map((it, i) => (
                    <ThreadEntry key={i} item={it} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <Placeholder>Select a conversation</Placeholder>
          )}
        </main>
      </div>
    </div>
  );
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-display grid h-full place-items-center px-7 py-14 text-[24px] tracking-tight text-muted">
      {children}
    </div>
  );
}

function ThreadEntry({ item }: { item: ThreadItem }) {
  if (item.kind === "msg") {
    const m = item.data as Message;
    const out = m.direction === "outbound";
    return (
      <div className={`flex flex-col ${out ? "items-end" : "items-start"}`}>
        <div
          className={`max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-[14px] leading-snug ${
            out ? "rounded-br-md bg-ink text-panel" : "rounded-bl-md bg-[#F0EDE3] text-ink"
          }`}
        >
          {m.body}
        </div>
        <div className="mt-1 mx-1.5 font-mono text-[10.5px] tracking-wider text-muted">
          {fmtTime(m.created_at)}
          {m.from_number ? ` · ${m.from_number}` : ""}
        </div>
      </div>
    );
  }
  const c = item.data as Call;
  const transcript = Array.isArray(c.transcript) ? c.transcript : null;
  const dur = c.duration_seconds ? `${Math.round(c.duration_seconds)}s` : "—";
  return (
    <div className="my-1.5 grid grid-cols-[auto_1fr_auto] items-center gap-x-3.5 gap-y-1 rounded-[14px] border border-line bg-white px-4 py-3.5 self-stretch">
      <div className="grid h-7 w-7 place-items-center rounded-full bg-accent-soft font-mono text-[12px] text-accent">
        ☎
      </div>
      <div className="text-[13.5px] font-medium text-ink">
        {c.direction === "outbound" ? "Outbound call" : "Inbound call"} · {c.to_number}
      </div>
      <div className="font-mono text-[11px] tracking-wide text-muted">
        {fmtTime(c.started_at)} · {dur}
        {c.disconnection_reason ? ` · ${c.disconnection_reason}` : ""}
      </div>
      {c.summary ? (
        <div className="col-start-2 col-end-[-1] text-[13px] text-ink-2">{c.summary}</div>
      ) : null}
      {transcript && transcript.length ? (
        <div className="col-span-full mt-2 flex flex-col gap-1.5 border-t border-line-2 pt-2.5">
          {transcript.map((t, i) => (
            <div key={i} className="text-[13px]">
              <span className="mr-2 font-mono text-[10.5px] uppercase tracking-wider text-muted">
                {t.role}
              </span>
              {t.content ?? t.text}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
