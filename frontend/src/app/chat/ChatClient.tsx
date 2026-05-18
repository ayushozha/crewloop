"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/Brand";
import { api, type ChatBulkOutreach, type ChatEventPlan, type ChatInvoiceEmail } from "@/lib/api";

/* ============================== types =============================== */

type Role = "user" | "agent";

interface Attachment {
  name: string;
  mime_type: string;
  data: string; // base64 (no data: prefix)
  preview_url?: string; // for image render
}

interface ChatMessage {
  id: string;
  role: Role;
  text?: string;
  attachments?: Attachment[];
  ts: string; // formatted time
  voice?: { duration: string };
  suggestions?: Array<{ label: string; say: string }>;
  card?: AgentCard;
}

type AgentCard =
  | ({
      kind: "event_plan";
      actions: Array<{ label: string; say: string; variant?: "primary" | "ghost" }>;
    } & ChatEventPlan)
  | ({
      kind: "bulk_outreach";
      actions: Array<{ label: string; say: string; variant?: "primary" | "ghost" }>;
    } & ChatBulkOutreach)
  | ({
      kind: "invoice_email";
      actions: Array<{ label: string; say: string; variant?: "primary" | "ghost" }>;
    } & ChatInvoiceEmail)
  | {
      kind: "matches";
      title: string;
      tag: string;
      rows: Array<{ initial: string; name: string; meta: string; pill: string; pillVariant: "green" | "dim"; top?: boolean; tint?: "maya" }>;
      actions: Array<{ label: string; say?: string; variant?: "primary" | "ghost" }>;
    }
  | {
      kind: "outreach";
      title: string;
      tag: string;
      body: string;
      chips: Array<{ label: string; variant?: "default" | "dim" }>;
    }
  | {
      kind: "call";
      title: string;
      subtitle: string;
      duration: string;
    }
  | {
      kind: "payment";
      title: string;
      tag: string;
      amount: string;
      unit: string;
      label: string;
      rules: Array<{ text: string; time: string; done: boolean }>;
      actions: Array<{ label: string; say?: string; variant?: "primary" | "ghost" }>;
    };

/* ============================== seed thread =============================== */

const SEED_MESSAGES: ChatMessage[] = [
  {
    id: "u-1",
    role: "user",
    text: "We have a corporate dinner this Saturday for 80 guests in SoMa. Need a 10-person crew, supplies, and an invoice.",
    ts: "5:42 PM",
  },
  {
    id: "a-1",
    role: "agent",
    ts: "5:42 PM",
    card: {
      kind: "event_plan",
      event_name: "Corporate dinner",
      details: "80-guest corporate dinner in SoMa, San Francisco.",
      event_date: "This Saturday",
      event_time: "6:00 PM - 11:00 PM",
      location: "SoMa, San Francisco",
      staff_requirement: "10 staff: 2 bartenders, 4 servers, 2 setup crew, 1 event lead, 1 cleanup lead.",
      responsibilities: "Setup, food service, bartending, cleanup, and event lead oversight.",
      inventory_requirement: "100 compostable cups, 100 napkins, 4 bags of ice, 2 tablecloths, bartender tool kit rental.",
      estimated_labor: "$1,450",
      invoice_amount: "$1,756",
      approval_question: "Approve this plan so I can shortlist the crew and start the next steps?",
      actions: [
        { label: "Approve plan", say: "Approve this event plan", variant: "primary" },
        { label: "Edit staff", say: "Change the staff requirement", variant: "ghost" },
        { label: "Change budget", say: "Change the invoice amount", variant: "ghost" },
      ],
    },
  },
];

const THREADS = [
  { id: "corp-dinner", title: "Corporate dinner", sub: "Plan ready · approval needed", time: "now", badge: "1", active: true },
  { id: "fri-catering", title: "Friday catering", sub: "Crew shortlist drafted", time: "2h" },
  { id: "vendor-order", title: "Vendor supplies", sub: "Browser Use found pickup", time: "Mon" },
  { id: "roster", title: "Roster memory", sub: "Reliability scores refreshed", time: "May 9" },
];

/* ============================== utils =============================== */

const nowStr = () => {
  const d = new Date();
  let h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, "0");
  const ampm = h >= 12 ? "PM" : "AM";
  h = ((h + 11) % 12) + 1;
  return `${h}:${m} ${ampm}`;
};

/** Render **bold** segments without dangerouslySetInnerHTML. */
function richText(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <b key={i} className="font-medium text-ink">
        {p.slice(2, -2)}
      </b>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

async function fileToBase64(file: File): Promise<{ data: string; preview_url: string }> {
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const data = btoa(bin);
  const preview_url = file.type.startsWith("image/") ? `data:${file.type};base64,${data}` : "";
  return { data, preview_url };
}

function cardFromEventPlan(plan: ChatEventPlan, actions: Array<{ label: string; say: string }> = []): AgentCard {
  return {
    kind: "event_plan",
    ...plan,
    actions: actions.length
      ? actions.map((action, index) => ({ ...action, variant: index === 0 ? "primary" : "ghost" }))
      : [{ label: "Approve plan", say: "Approve this event plan", variant: "primary" }],
  };
}

function cardFromBulkOutreach(snapshot: ChatBulkOutreach, actions: Array<{ label: string; say: string }> = []): AgentCard {
  return {
    kind: "bulk_outreach",
    ...snapshot,
    actions: actions.map((action, index) => ({ ...action, variant: index === 0 ? "primary" : "ghost" })),
  };
}

function cardFromInvoiceEmail(snapshot: ChatInvoiceEmail, actions: Array<{ label: string; say: string }> = []): AgentCard {
  return {
    kind: "invoice_email",
    ...snapshot,
    actions: actions.map((action, index) => ({ ...action, variant: index === 0 ? "primary" : "ghost" })),
  };
}

/* ============================== component =============================== */

export function ChatClient() {
  const [messages, setMessages] = useState<ChatMessage[]>(SEED_MESSAGES);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Attachment[]>([]);
  const [sending, setSending] = useState(false);
  const [inCall, setInCall] = useState(false);
  const [callTime, setCallTime] = useState("00:02");
  const streamRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [messages, sending]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(160, ta.scrollHeight) + "px";
  }, [draft]);

  // Fake in-call timer
  useEffect(() => {
    if (!inCall) {
      const id = window.setTimeout(() => setCallTime("00:02"), 0);
      return () => window.clearTimeout(id);
    }
    const start = Date.now();
    const id = window.setInterval(() => {
      const s = Math.floor((Date.now() - start) / 1000) + 2;
      const mm = Math.floor(s / 60).toString().padStart(2, "0");
      const ss = (s % 60).toString().padStart(2, "0");
      setCallTime(`${mm}:${ss}`);
    }, 1000);
    return () => window.clearInterval(id);
  }, [inCall]);

  const submitMessage = useCallback(async (rawText: string, attachments: Attachment[] = []) => {
    if (sending) return;
    const text = rawText.trim();
    if (!text && attachments.length === 0) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text,
      ts: nowStr(),
      attachments: attachments.length ? attachments : undefined,
    };
    const optimistic = [...messages, userMsg];
    setMessages(optimistic);
    setDraft("");
    setPending([]);
    setSending(true);

    try {
      const turns = optimistic
        .filter((m) => m.text || (m.attachments && m.attachments.length))
        .map((m) => ({
          role: m.role === "user" ? ("user" as const) : ("model" as const),
          text: m.text ?? (m.attachments?.length ? `[${m.attachments.length} attachment${m.attachments.length === 1 ? "" : "s"}]` : ""),
        }));
      const apiAttachments = attachments
        .filter((a) => a.data) // real uploads only; demo seed images have empty data
        .map((a) => ({ mime_type: a.mime_type, data: a.data, name: a.name }));
      const response = await api.chat({ turns, attachments: apiAttachments });
      const card = response.event_plan
        ? cardFromEventPlan(response.event_plan, response.action_chips ?? [])
        : response.bulk_outreach
          ? cardFromBulkOutreach(response.bulk_outreach, response.action_chips ?? [])
          : response.invoice_email
            ? cardFromInvoiceEmail(response.invoice_email, response.action_chips ?? [])
            : undefined;
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "agent",
          text: card ? undefined : response.reply,
          card,
          suggestions: card ? undefined : response.action_chips,
          ts: nowStr(),
        },
      ]);
    } catch (e) {
      const detail = e instanceof Error ? e.message : "Loop is offline";
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: "agent", text: `Loop hit a snag: ${detail.slice(0, 200)}`, ts: nowStr() },
      ]);
    } finally {
      setSending(false);
    }
  }, [messages, sending]);

  const send = useCallback(async () => {
    await submitMessage(draft, pending);
  }, [draft, pending, submitMessage]);

  const sendCardAction = useCallback((text: string) => {
    void submitMessage(text);
  }, [submitMessage]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;
    const added: Attachment[] = [];
    for (const file of Array.from(files)) {
      const { data, preview_url } = await fileToBase64(file);
      added.push({
        name: file.name,
        mime_type: file.type || "application/octet-stream",
        data,
        preview_url,
      });
    }
    setPending((prev) => [...prev, ...added]);
  };

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden md:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px]">
      <Sidebar />
      <ChatColumn
        messages={messages}
        draft={draft}
        setDraft={setDraft}
        pending={pending}
        setPending={setPending}
        sending={sending}
        send={send}
        onKeyDown={onKeyDown}
        streamRef={streamRef}
        textareaRef={textareaRef}
        fileInputRef={fileInputRef}
        imageInputRef={imageInputRef}
        handleFiles={handleFiles}
        inCall={inCall}
        setInCall={setInCall}
        callTime={callTime}
        onCardAction={sendCardAction}
      />
      <ContextPanel />
    </div>
  );
}

/* ============================== sidebar =============================== */

function Sidebar() {
  return (
    <aside className="hidden flex-col gap-5 overflow-y-auto border-r border-line p-6 md:flex">
      <Link href="/" className="flex items-center gap-2.5">
        <BrandMark />
        <b className="text-base font-medium tracking-tight">CrewLoop</b>
      </Link>

      <SideSection label="Workspace">
        <SideLink href="/dashboard" icon={<DashboardIcon />}>Dashboard</SideLink>
        <SideLink href="/chat" icon={<ChatIcon />} active>
          Chat with Loop <span className="ml-auto font-mono text-[11px] text-[#C9C5B6]">●</span>
        </SideLink>
        <SideLink href="/browser-import" icon={<DispatchIcon />}>
          Dispatch <span className="ml-auto font-mono text-[11px] text-muted">3</span>
        </SideLink>
        <SideLink href="/contractors" icon={<RosterIcon />}>
          Contractors <span className="ml-auto font-mono text-[11px] text-muted">42</span>
        </SideLink>
        <SideLink href="#" icon={<PaymentIcon />}>Payments</SideLink>
      </SideSection>

      <div className="flex flex-col gap-0.5">
        <div className="flex items-center justify-between px-2.5 pb-1.5">
          <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">Threads</span>
          <button className="grid h-6 w-6 place-items-center rounded-md text-ink-2 hover:bg-[#F1EEE5] hover:text-ink">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M6.5 2.5v8M2.5 6.5h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        {THREADS.map((t) => (
          <button
            key={t.id}
            className={`grid w-full grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-lg p-2 text-left transition ${
              t.active ? "bg-ink text-panel" : "text-ink hover:bg-[#F1EEE5]"
            }`}
          >
            <span
              className={`grid h-7 w-7 place-items-center rounded-lg text-[11px] font-semibold ${
                t.active ? "bg-panel text-ink" : "bg-ink text-panel"
              }`}
            >
              L
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-[13px] font-medium">
                <span className="truncate">{t.title}</span>
                {t.badge && (
                  <span className="rounded-full bg-urgent px-1.5 py-0 font-mono text-[10px] text-panel">{t.badge}</span>
                )}
              </span>
              <span className={`block max-w-[130px] truncate text-[11.5px] ${t.active ? "text-[#C9C5B6]" : "text-muted"}`}>
                {t.sub}
              </span>
            </span>
            <span className={`font-mono text-[10.5px] ${t.active ? "text-[#C9C5B6]" : "text-muted"}`}>{t.time}</span>
          </button>
        ))}
      </div>

      <div className="mt-auto flex items-center gap-2.5 rounded-[10px] border border-line bg-panel p-2.5">
        <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-[#D7E5D8] text-xs font-semibold text-[#2C5638]">
          BE
        </span>
        <span className="flex flex-col leading-tight">
          <b className="text-[13px] font-medium">Bay Events Co.</b>
          <small className="text-[11.5px] text-muted">SF · admin</small>
        </span>
      </div>
    </aside>
  );
}

function SideSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="px-2.5 pb-2 pt-1 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">{label}</span>
      {children}
    </div>
  );
}

function SideLink({
  href,
  icon,
  active = false,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] transition ${
        active ? "bg-ink text-panel" : "text-ink-2 hover:bg-[#F1EEE5] hover:text-ink"
      }`}
    >
      <span className="inline-grid h-3.5 w-3.5 place-items-center">{icon}</span>
      {children}
    </Link>
  );
}

/* ============================== chat column =============================== */

interface ChatColumnProps {
  messages: ChatMessage[];
  draft: string;
  setDraft: (v: string) => void;
  pending: Attachment[];
  setPending: React.Dispatch<React.SetStateAction<Attachment[]>>;
  sending: boolean;
  send: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  streamRef: React.RefObject<HTMLDivElement | null>;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  imageInputRef: React.RefObject<HTMLInputElement | null>;
  handleFiles: (files: FileList | null) => void;
  inCall: boolean;
  setInCall: (b: boolean) => void;
  callTime: string;
  onCardAction: (s: string) => void;
}

function ChatColumn({
  messages,
  draft,
  setDraft,
  pending,
  setPending,
  sending,
  send,
  onKeyDown,
  streamRef,
  textareaRef,
  fileInputRef,
  imageInputRef,
  handleFiles,
  inCall,
  setInCall,
  callTime,
  onCardAction,
}: ChatColumnProps) {
  return (
    <section className="flex min-w-0 flex-col bg-bg">
      <ChatHeader inCall={inCall} setInCall={setInCall} callTime={callTime} />

      <div ref={streamRef} className="flex-1 overflow-y-auto px-5 pb-6 pt-8 md:px-9">
        <div className="mx-auto flex max-w-[780px] flex-col gap-[18px]">
          <Daybreak>Today · 5:42 PM PT</Daybreak>
          {messages.map((m) => (
            <MessageBubble key={m.id} msg={m} onSuggestion={(s) => setDraft(s)} onCardAction={onCardAction} />
          ))}
          {sending && <TypingIndicator />}
        </div>
      </div>

      <Composer
        draft={draft}
        setDraft={setDraft}
        pending={pending}
        setPending={setPending}
        send={send}
        sending={sending}
        onKeyDown={onKeyDown}
        textareaRef={textareaRef}
        fileInputRef={fileInputRef}
        imageInputRef={imageInputRef}
        handleFiles={handleFiles}
      />
    </section>
  );
}

function ChatHeader({ inCall, setInCall, callTime }: { inCall: boolean; setInCall: (b: boolean) => void; callTime: string }) {
  return (
    <header
      className="z-[2] flex items-center gap-3.5 border-b border-line px-6 py-3.5 backdrop-blur-md"
      style={{ background: "color-mix(in oklab, var(--color-bg) 85%, transparent)" }}
    >
      <div className="relative grid h-9 w-9 place-items-center rounded-[10px] bg-ink text-panel">
        <span className="dot-pulse pointer-events-none absolute -inset-1 rounded-[13px] border-[1.5px] border-accent" />
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M3 9a6 6 0 1 1 10.2 4.2" stroke="#FBFAF6" strokeWidth="1.6" strokeLinecap="round" />
          <path d="M13.2 9.5V13H9.7" stroke="#FBFAF6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="flex min-w-0 flex-1 flex-col leading-tight">
        <b className="text-[15px] font-medium">Loop · CrewLoop agent</b>
        <small className="flex items-center gap-1.5 text-[12px] text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_0_3px_rgba(62,124,78,0.18)]" />
          Online · responds in under 2s · dispatching for Bay Events Co.
        </small>
      </div>
      <div className="flex items-center gap-1.5">
        <IconBtn title="Search this thread">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <circle cx="6.5" cy="6.5" r="4" stroke="currentColor" strokeWidth="1.4" />
            <path d="M9.5 9.5l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </IconBtn>
        <IconBtn title="Mute notifications">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M4 6a3.5 3.5 0 0 1 7 0v2l1.2 1.6H2.8L4 8V6z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            <path d="M6.2 11.5a1.3 1.3 0 0 0 2.6 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </IconBtn>
        <button
          onClick={() => setInCall(!inCall)}
          className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[13px] font-medium text-panel transition hover:-translate-y-px ${
            inCall ? "bg-urgent hover:bg-[#a13d28]" : "bg-accent hover:bg-[#2F6740]"
          }`}
        >
          {inCall ? (
            <>
              <span className="dot-pulse h-2 w-2 rounded-full bg-panel" />
              In call · {callTime}
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M2.5 8.5L8.5 2.5M2.5 2.5l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path
                  d="M2.5 2.5h2l1 2.5L4 6c.8 1.5 2 2.7 3.5 3.5L9 8l2.5 1v2h-1A8 8 0 0 1 2.5 3.5v-1z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinejoin="round"
                />
              </svg>
              Start call
            </>
          )}
        </button>
      </div>
    </header>
  );
}

function IconBtn({ children, title, onClick }: { children: React.ReactNode; title: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="grid h-[34px] w-[34px] place-items-center rounded-lg border border-transparent text-ink-2 transition hover:border-line hover:bg-panel hover:text-ink"
    >
      {children}
    </button>
  );
}

function Daybreak({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-2 flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-wider text-muted">
      <span className="h-px flex-1 bg-line-2" />
      <span>{children}</span>
      <span className="h-px flex-1 bg-line-2" />
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex max-w-[78%] gap-3 items-end">
      <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-lg bg-ink text-[11px] font-semibold text-panel">L</span>
      <div className="inline-flex gap-1 rounded-2xl rounded-bl-md border border-line bg-white px-3.5 py-3">
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" />
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" style={{ animationDelay: "0.15s" }} />
        <span className="typing-dot inline-block h-[5px] w-[5px] rounded-full bg-[#9A9384]" style={{ animationDelay: "0.3s" }} />
      </div>
    </div>
  );
}

/* ============================== message =============================== */

function MessageBubble({
  msg,
  onSuggestion,
  onCardAction,
}: {
  msg: ChatMessage;
  onSuggestion: (s: string) => void;
  onCardAction: (s: string) => void;
}) {
  if (msg.suggestions && !msg.text && !msg.card) {
    return (
      <div className="flex max-w-[78%] gap-3">
        <span className="h-7 w-7 flex-shrink-0" />
        <SuggestionButtons suggestions={msg.suggestions} onSelect={onSuggestion} />
      </div>
    );
  }

  const isUser = msg.role === "user";
  return (
    <div className={`flex max-w-[78%] items-end gap-3 ${isUser ? "ml-auto flex-row-reverse" : ""}`}>
      <Avatar role={msg.role} />
      <div className={`flex flex-col gap-2 ${isUser ? "items-end" : "items-start"} min-w-0`}>
        {msg.voice ? (
          <VoiceBubble duration={msg.voice.duration} isUser={isUser} />
        ) : msg.text || msg.attachments?.length ? (
          <div
            className={`max-w-full whitespace-pre-wrap break-words rounded-[18px] px-4 py-3 text-[14.5px] leading-relaxed ${
              isUser
                ? "rounded-br-md bg-ink text-panel"
                : "rounded-bl-md border border-line bg-white text-ink"
            }`}
          >
            {msg.text && <div>{richText(msg.text)}</div>}
            {msg.attachments && msg.attachments.length > 0 && (
              <div className={`mt-2 flex flex-wrap gap-2 ${isUser ? "" : ""}`}>
                {msg.attachments.map((a, i) => (
                  <AttachmentChip key={i} attachment={a} isUser={isUser} />
                ))}
              </div>
            )}
          </div>
        ) : null}

        {msg.card && <Card card={msg.card} onAction={onCardAction} />}

        {msg.suggestions && msg.suggestions.length > 0 && (
          <SuggestionButtons suggestions={msg.suggestions} onSelect={onCardAction} />
        )}

        <MetaRow ts={msg.ts} isUser={isUser} transcribed={!!msg.voice} />
      </div>
    </div>
  );
}

function SuggestionButtons({
  suggestions,
  onSelect,
}: {
  suggestions: Array<{ label: string; say: string }>;
  onSelect: (s: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {suggestions.map((s) => (
        <button
          key={`${s.label}-${s.say}`}
          type="button"
          onClick={() => onSelect(s.say)}
          className="rounded-full border border-line bg-white px-3 py-1.5 text-[12.5px] text-ink-2 transition hover:border-ink hover:text-ink"
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

function Avatar({ role }: { role: Role }) {
  if (role === "user") {
    return (
      <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-full bg-[#D7E5D8] text-[11px] font-semibold text-[#2C5638]">
        JK
      </span>
    );
  }
  return (
    <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-lg bg-ink text-[11px] font-semibold text-panel">
      L
    </span>
  );
}

function MetaRow({ ts, isUser, transcribed = false }: { ts: string; isUser: boolean; transcribed?: boolean }) {
  return (
    <div className={`mt-1 flex items-center gap-2 font-mono text-[11px] tracking-wide text-muted ${isUser ? "justify-end" : "ml-1"}`}>
      <span>{ts}</span>
      {transcribed && <span className="opacity-70">· transcribed</span>}
      {isUser && <span className="inline-flex gap-px text-accent">✓✓</span>}
    </div>
  );
}

function AttachmentChip({ attachment, isUser }: { attachment: Attachment; isUser: boolean }) {
  const isImage = attachment.mime_type.startsWith("image/") && attachment.preview_url;
  if (isImage) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={attachment.preview_url}
        alt={attachment.name}
        className="block h-[100px] w-[140px] rounded-[10px] object-cover"
      />
    );
  }
  const ext = (attachment.name.split(".").pop() ?? attachment.mime_type.split("/").pop() ?? "FILE")
    .slice(0, 3)
    .toUpperCase();
  return (
    <div
      className={`flex min-w-[180px] items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-[12.5px] ${
        isUser ? "border-white/10 bg-white/8" : "border-line bg-bg"
      }`}
    >
      <span className="grid h-[34px] w-7 place-items-center rounded-[5px] border border-line bg-panel font-mono text-[9px] font-semibold text-ink">
        {ext}
      </span>
      <span className="flex min-w-0 flex-1 flex-col leading-tight">
        <b className={`max-w-[140px] truncate font-medium text-[12.5px] ${isUser ? "text-panel" : "text-ink"}`}>
          {attachment.name}
        </b>
        <small className={`font-mono text-[10.5px] ${isUser ? "text-[#C9C5B6]" : "text-muted"}`}>
          {attachment.mime_type}
        </small>
      </span>
    </div>
  );
}

function VoiceBubble({ duration, isUser }: { duration: string; isUser: boolean }) {
  // 25 bars: first 7 "played", rest unplayed
  const heights = [6, 10, 14, 18, 12, 20, 8, 16, 22, 10, 14, 18, 8, 12, 6, 10, 14, 8, 16, 6, 10, 14, 18, 8, 12];
  return (
    <div
      className={`flex min-w-[240px] max-w-[320px] items-center gap-2.5 rounded-[18px] border px-3.5 py-2.5 ${
        isUser ? "border-ink bg-ink text-panel" : "border-line bg-white text-ink"
      }`}
    >
      <span className={`grid h-7 w-7 place-items-center rounded-full ${isUser ? "bg-panel text-ink" : "bg-ink text-panel"}`}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <path d="M2 1.5l6 3.5-6 3.5V1.5z" />
        </svg>
      </span>
      <span className="flex h-6 flex-1 items-center gap-px">
        {heights.map((h, i) => (
          <span
            key={i}
            className="inline-block w-[2px] rounded-[2px]"
            style={{
              height: h,
              background: isUser ? "#FBFAF6" : "#161410",
              opacity: i < 7 ? 1 : isUser ? 0.5 : 0.55,
            }}
          />
        ))}
      </span>
      <span className={`font-mono text-[11px] ${isUser ? "text-[#C9C5B6]" : "text-muted"}`}>{duration}</span>
    </div>
  );
}

/* ============================== cards =============================== */

function Card({ card, onAction }: { card: AgentCard; onAction?: (say: string) => void }) {
  if (card.kind === "event_plan") {
    return (
      <div className="w-full max-w-[580px] overflow-hidden rounded-[18px] border border-[rgba(62,124,78,0.22)] bg-white shadow-[0_1px_0_rgba(22,20,16,0.02),0_14px_34px_-24px_rgba(22,20,16,0.2)]">
        <div className="border-b border-line-2 bg-accent-soft px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="m-0 font-mono text-[10.5px] uppercase tracking-[0.12em] text-accent">Event plan</p>
              <h4 className="m-0 mt-1 text-[18px] font-semibold leading-tight text-ink">{card.event_name}</h4>
              <p className="m-0 mt-1 text-[12.5px] leading-snug text-ink-2">{card.details}</p>
            </div>
            <Pill variant="green">Ready for approval</Pill>
          </div>
        </div>

        <div className="grid gap-2.5 p-3.5 text-[12.5px] text-ink-2 sm:grid-cols-2">
          <PlanField label="Date" value={card.event_date} />
          <PlanField label="Time" value={card.event_time} />
          <PlanField label="Location" value={card.location ?? "TBD"} />
          <PlanField label="Estimated labor" value={card.estimated_labor} />
          <PlanField label="Staff requirement" value={card.staff_requirement} wide />
          <PlanField label="Responsibilities" value={card.responsibilities} wide />
          <PlanField label="Inventory requirement" value={card.inventory_requirement} wide />
          <PlanField label="Invoice amount" value={card.invoice_amount} />
        </div>

        <div className="border-t border-line-2 px-4 py-2.5">
          <p className="m-0 text-[12.5px] leading-snug text-ink">{card.approval_question}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {card.actions.map((a) => (
              <CardBtn key={a.label} variant={a.variant ?? "ghost"} onClick={() => onAction?.(a.say)}>
                {a.label}
              </CardBtn>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (card.kind === "bulk_outreach") {
    return (
      <div className="w-full max-w-[620px] overflow-hidden rounded-[18px] border border-line bg-white shadow-[0_1px_0_rgba(22,20,16,0.02),0_14px_34px_-24px_rgba(22,20,16,0.2)]">
        <div className="border-b border-line-2 bg-[#F7F4EA] px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="m-0 font-mono text-[10.5px] uppercase tracking-[0.12em] text-accent">Bulk outreach</p>
              <h4 className="m-0 mt-1 text-[18px] font-semibold leading-tight text-ink">{card.title}</h4>
              <p className="m-0 mt-1 max-w-[52ch] text-[12.5px] leading-snug text-ink-2">{card.summary}</p>
            </div>
            <Pill variant={card.status === "complete" ? "green" : "default"}>{card.tag}</Pill>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
            <MiniStat label="Needed" value={card.counts.needed} />
            <MiniStat label="Filled" value={card.counts.filled} />
            <MiniStat label="Texts" value={card.counts.live_texts} />
            <MiniStat label="Calls" value={card.counts.live_calls} />
            <MiniStat label="Sim" value={card.counts.simulated_replies} />
            <MiniStat label="Declined" value={card.counts.declined} />
          </div>
        </div>

        <div className="max-h-[360px] overflow-y-auto px-3.5 py-3">
          <div className="flex flex-col gap-1.5">
            {card.rows.map((row) => (
              <div
                key={`${row.name}-${row.role}`}
                className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-[12.5px] sm:grid-cols-[minmax(0,1fr)_92px_96px]"
              >
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                    <b className="truncate text-[13px] font-medium text-ink">{row.name}</b>
                    {row.live && <span className="font-mono text-[10px] uppercase tracking-wider text-accent">live</span>}
                    {row.phone_last4 && <span className="font-mono text-[10px] text-muted">*{row.phone_last4}</span>}
                  </div>
                  <p className="m-0 mt-0.5 line-clamp-2 text-[12px] leading-snug text-ink-2">{row.role} - {row.response}</p>
                  <p className="m-0 mt-0.5 truncate font-mono text-[10px] uppercase tracking-wider text-muted">{row.delivery_status}</p>
                </div>
                <span className="hidden self-start truncate font-mono text-[10px] uppercase tracking-wider text-muted sm:block">
                  {row.channel}
                </span>
                <OutreachStatusPill status={row.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-line-2 px-4 py-2.5">
          {card.evidence.length > 0 && (
            <p className="m-0 mb-2 line-clamp-2 text-[12px] leading-snug text-muted">{card.evidence.join(" ")}</p>
          )}
          <div className="flex flex-wrap gap-2">
            {card.actions.map((a) => (
              <CardBtn key={a.label} variant={a.variant ?? "ghost"} onClick={() => onAction?.(a.say)}>
                {a.label}
              </CardBtn>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (card.kind === "invoice_email") {
    return (
      <div className="w-full max-w-[620px] overflow-hidden rounded-[18px] border border-line bg-white shadow-[0_1px_0_rgba(22,20,16,0.02),0_14px_34px_-24px_rgba(22,20,16,0.2)]">
        <div className="border-b border-line-2 bg-[#F6F2E8] px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="m-0 font-mono text-[10.5px] uppercase tracking-[0.12em] text-accent">Invoice + AgentMail</p>
              <h4 className="m-0 mt-1 text-[18px] font-semibold leading-tight text-ink">{card.title}</h4>
              <p className="m-0 mt-1 max-w-[54ch] text-[12.5px] leading-snug text-ink-2">{card.summary}</p>
            </div>
            <Pill variant={card.status === "sent" ? "green" : "default"}>{card.tag}</Pill>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <MoneyStat label="Total" value={card.total} />
            <MoneyStat label="Deposit" value={card.deposit} />
            <MoneyStat label="Balance" value={card.balance_due} />
          </div>
        </div>

        <div className="grid gap-2.5 px-3.5 py-3 text-[12.5px] text-ink-2 sm:grid-cols-2">
          <PlanField label="Event" value={card.event.details} wide />
          <PlanField label="Date" value={card.event.date} />
          <PlanField label="Time" value={card.event.time} />
          <PlanField label="Location" value={card.event.location} />
          <PlanField label="Guests" value={card.event.guests} />
        </div>

        <div className="border-t border-line-2 px-3.5 py-3">
          <small className="mb-2 block font-mono text-[9.5px] uppercase tracking-wider text-muted">Invoice lines</small>
          <div className="grid gap-1.5 sm:grid-cols-3">
            {card.line_items.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-2 rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-[12.5px]">
                <span className="truncate text-ink-2">{item.label}</span>
                <b className="font-semibold text-ink">{item.amount}</b>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-line-2 px-3.5 py-3">
          <small className="mb-2 block font-mono text-[9.5px] uppercase tracking-wider text-muted">AgentMail packets</small>
          <div className="flex flex-col gap-1.5">
            {card.emails.map((email) => (
              <div
                key={email.label}
                className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-[12.5px]"
              >
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                    <b className="truncate text-[13px] font-medium text-ink">{email.label}</b>
                    <span className="truncate font-mono text-[10px] text-muted">{email.to}</span>
                  </div>
                  <p className="m-0 mt-0.5 truncate text-[12px] text-ink-2">{email.subject}</p>
                  <p className="m-0 mt-0.5 line-clamp-1 font-mono text-[10px] uppercase tracking-wider text-muted">{email.detail}</p>
                </div>
                <EmailStatusPill status={email.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-line-2 px-3.5 py-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <small className="font-mono text-[9.5px] uppercase tracking-wider text-muted">Sponge contractor wallets</small>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">{card.wallets.length} prepared</span>
          </div>
          <div className="max-h-[230px] overflow-y-auto">
            <div className="flex flex-col gap-1.5">
              {card.wallets.map((wallet) => (
                <div key={wallet.wallet_id} className="grid grid-cols-[minmax(0,1fr)_74px] gap-2 rounded-[10px] border border-line-2 bg-white px-3 py-2 text-[12.5px]">
                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                      <b className="truncate text-[13px] font-medium text-ink">{wallet.name}</b>
                      <span className="truncate text-[12px] text-ink-2">{wallet.role}</span>
                    </div>
                    <p className="m-0 mt-0.5 truncate font-mono text-[10px] text-muted">{wallet.shift} · {wallet.wallet_id}</p>
                  </div>
                  <b className="self-start justify-self-end text-[13px] font-semibold text-ink">{wallet.pay}</b>
                </div>
              ))}
            </div>
          </div>
          <p className="m-0 mt-2 line-clamp-2 text-[12px] leading-snug text-muted">{card.cancellation_policy}</p>
        </div>

        <div className="border-t border-line-2 px-4 py-2.5">
          {card.evidence.length > 0 && (
            <p className="m-0 mb-2 line-clamp-2 text-[12px] leading-snug text-muted">{card.evidence.join(" ")}</p>
          )}
          <div className="flex flex-wrap gap-2">
            {card.actions.map((a) => (
              <CardBtn key={a.label} variant={a.variant ?? "ghost"} onClick={() => onAction?.(a.say)}>
                {a.label}
              </CardBtn>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (card.kind === "matches") {
    return (
      <div className="w-full max-w-[520px] rounded-[14px] border border-line bg-white p-3.5 shadow-[0_1px_0_rgba(22,20,16,0.02),0_8px_22px_-18px_rgba(22,20,16,0.16)]">
        <div className="mb-2.5 flex items-center justify-between border-b border-line-2 pb-2.5">
          <h4 className="m-0 flex items-center gap-2 text-[13px] font-medium">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <circle cx="6.5" cy="6.5" r="4.8" stroke="currentColor" strokeWidth="1.3" />
              <path d="M4.5 6.5l1.3 1.3 2.7-2.7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {card.title}
          </h4>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">{card.tag}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          {card.rows.map((r) => (
            <div
              key={r.name}
              className={`grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-lg p-2 text-[13px] ${
                r.top ? "border border-[rgba(62,124,78,0.22)] bg-accent-soft p-2.5" : ""
              }`}
            >
              <span className={`grid h-7 w-7 place-items-center rounded-full text-[11px] font-semibold ${
                r.tint === "maya" ? "bg-[#D7E5D8] text-[#2C5638]" : "bg-[#E5E0D2] text-[#5B5648]"
              }`}>
                {r.initial}
              </span>
              <span className="flex min-w-0 flex-col leading-tight">
                <b className="text-[13px] font-medium">{r.name}</b>
                <small className="font-mono text-[11px] text-muted">{r.meta}</small>
              </span>
              <Pill variant={r.pillVariant}>{r.pill}</Pill>
            </div>
          ))}
        </div>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {card.actions.map((a) => (
            <CardBtn key={a.label} variant={a.variant ?? "primary"} onClick={a.say ? () => onAction?.(a.say ?? "") : undefined}>{a.label}</CardBtn>
          ))}
        </div>
      </div>
    );
  }

  if (card.kind === "outreach") {
    return (
      <div className="w-full max-w-[520px] rounded-[14px] border border-line bg-white p-3.5 shadow-[0_1px_0_rgba(22,20,16,0.02),0_8px_22px_-18px_rgba(22,20,16,0.16)]">
        <div className="mb-2.5 flex items-center justify-between border-b border-line-2 pb-2.5">
          <h4 className="m-0 flex items-center gap-2 text-[13px] font-medium">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M2.2 3h8.6v5.4H5.5l-2.4 1.8V8.4h-1V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
            {card.title}
          </h4>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">{card.tag}</span>
        </div>
        <p className="m-0 px-1 pt-1 text-[13px] leading-relaxed text-ink-2">{richText(card.body)}</p>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {card.chips.map((c) => (
            <Pill key={c.label} variant={c.variant === "dim" ? "dim" : "default"}>{c.label}</Pill>
          ))}
        </div>
      </div>
    );
  }

  if (card.kind === "call") {
    return (
      <div className="flex w-full max-w-[520px] items-center gap-3.5 rounded-[14px] border border-[rgba(62,124,78,0.25)] bg-accent-soft p-3.5">
        <span className="grid h-[38px] w-[38px] place-items-center rounded-[10px] bg-accent text-panel">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M3 3h2.5l1.2 3-1.7 1.6c.9 1.8 2.4 3.3 4.2 4.2L11 10.3l3 1.2V14h-1A10 10 0 0 1 3 4V3z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <div className="flex flex-1 flex-col leading-tight">
          <b className="text-[13.5px] font-medium text-ink">{card.title}</b>
          <small className="text-[12px] text-ink-2">{card.subtitle}</small>
        </div>
        <span className="font-mono text-[12px] text-accent">{card.duration}</span>
      </div>
    );
  }

  // payment
  return (
    <div className="w-full max-w-[520px] rounded-[14px] border border-line bg-white p-3.5 shadow-[0_1px_0_rgba(22,20,16,0.02),0_8px_22px_-18px_rgba(22,20,16,0.16)]">
      <div className="mb-2.5 flex items-center justify-between border-b border-line-2 pb-2.5">
        <h4 className="m-0 flex items-center gap-2 text-[13px] font-medium">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <rect x="1.5" y="3.5" width="10" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.3" />
            <path d="M1.5 6h10" stroke="currentColor" strokeWidth="1.3" />
          </svg>
          {card.title}
        </h4>
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted">{card.tag}</span>
      </div>
      <div className="mb-2.5 flex items-baseline justify-between gap-3 border-b border-line-2 pb-2.5">
        <span className="font-display text-[36px] leading-none tracking-tight">
          {card.amount}
          <span className="ml-2 text-[0.32em] tracking-wide text-muted">{card.unit}</span>
        </span>
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{card.label}</span>
      </div>
      <div className="flex flex-col gap-2">
        {card.rules.map((r) => (
          <div key={r.text} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-2.5 text-[13px] text-ink-2">
            <span
              className={`grid h-4 w-4 place-items-center rounded-[5px] ${
                r.done ? "bg-accent" : "border-[1.5px] border-line bg-transparent"
              }`}
            >
              {r.done && (
                <span
                  className="block h-[3px] w-[6px]"
                  style={{
                    borderLeft: "1.5px solid #fff",
                    borderBottom: "1.5px solid #fff",
                    transform: "rotate(-45deg) translate(0,-1px)",
                  }}
                />
              )}
            </span>
            <span>{r.text}</span>
            <small className="font-mono text-[11px] text-muted">{r.time}</small>
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {card.actions.map((a) => (
          <CardBtn key={a.label} variant={a.variant ?? "ghost"} onClick={a.say ? () => onAction?.(a.say ?? "") : undefined}>{a.label}</CardBtn>
        ))}
      </div>
    </div>
  );
}

function PlanField({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <small className="mb-1 block font-mono text-[9.5px] uppercase tracking-wider text-muted">{label}</small>
      <span className="block rounded-[9px] border border-line-2 bg-bg px-2.5 py-1.5 leading-snug text-ink">{value}</span>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[9px] border border-line-2 bg-white px-2 py-1.5">
      <small className="block font-mono text-[9px] uppercase tracking-wider text-muted">{label}</small>
      <b className="text-[14px] font-semibold text-ink">{value}</b>
    </div>
  );
}

function MoneyStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[9px] border border-line-2 bg-white px-2 py-1.5">
      <small className="block font-mono text-[9px] uppercase tracking-wider text-muted">{label}</small>
      <b className="text-[14px] font-semibold text-ink">{value}</b>
    </div>
  );
}

function OutreachStatusPill({ status }: { status: string }) {
  const cls =
    status === "confirmed" || status === "backup_confirmed"
      ? "bg-accent-soft text-accent"
      : status === "declined"
        ? "bg-urgent-soft text-urgent"
        : status === "ready"
          ? "bg-[#E1EBF1] text-[#315B7A]"
          : "bg-[#F0EDE3] text-muted";
  return (
    <span className={`self-start justify-self-end whitespace-nowrap rounded-full px-2 py-1 font-mono text-[10px] uppercase tracking-wider ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function EmailStatusPill({ status }: { status: string }) {
  const cls =
    status === "sent"
      ? "bg-accent-soft text-accent"
      : status === "failed"
        ? "bg-urgent-soft text-urgent"
        : status === "ready"
          ? "bg-[#E1EBF1] text-[#315B7A]"
          : "bg-[#F0EDE3] text-muted";
  return (
    <span className={`self-start justify-self-end whitespace-nowrap rounded-full px-2 py-1 font-mono text-[10px] uppercase tracking-wider ${cls}`}>
      {status}
    </span>
  );
}

function CardBtn({
  children,
  variant = "primary",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition hover:-translate-y-px ${
        variant === "ghost"
          ? "border border-line bg-transparent text-ink-2 hover:border-ink hover:text-ink"
          : "bg-ink text-panel"
      }`}
    >
      {children}
    </button>
  );
}

function Pill({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "green" | "dim" }) {
  const cls =
    variant === "green"
      ? "bg-accent text-panel"
      : variant === "dim"
        ? "bg-[#F0EDE3] text-muted"
        : "bg-[#F0EDE3] text-ink-2";
  return (
    <span className={`whitespace-nowrap rounded-full px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider ${cls}`}>
      {children}
    </span>
  );
}

/* ============================== composer =============================== */

interface ComposerProps {
  draft: string;
  setDraft: (v: string) => void;
  pending: Attachment[];
  setPending: React.Dispatch<React.SetStateAction<Attachment[]>>;
  send: () => void;
  sending: boolean;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  imageInputRef: React.RefObject<HTMLInputElement | null>;
  handleFiles: (files: FileList | null) => void;
}

function Composer({
  draft,
  setDraft,
  pending,
  setPending,
  send,
  sending,
  onKeyDown,
  textareaRef,
  fileInputRef,
  imageInputRef,
  handleFiles,
}: ComposerProps) {
  const canSend = !sending && (draft.trim().length > 0 || pending.length > 0);
  return (
    <div className="px-5 pb-6 pt-3 md:px-9" style={{ background: "linear-gradient(to top, var(--color-bg) 60%, transparent)" }}>
      <div className="mx-auto mb-2 flex max-w-[780px] items-center gap-2.5 font-mono text-[11.5px] uppercase tracking-wider text-muted">
        <span className="h-[5px] w-[5px] rounded-full bg-accent" />
        Loop can plan, shortlist, text, call, buy supplies, invoice, and hold payments · owner approves actions
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSend) send();
        }}
        className="mx-auto max-w-[780px] rounded-[18px] border border-line bg-white px-3 pb-2 pt-2.5 shadow-[0_1px_0_rgba(22,20,16,0.02),0_18px_40px_-28px_rgba(22,20,16,0.25)] focus-within:border-[rgba(22,20,16,0.35)]"
      >
        {pending.length > 0 && (
          <div className="mb-1.5 flex flex-wrap gap-2 border-b border-line-2 px-1.5 pb-2 pt-1.5">
            {pending.map((a, i) => {
              const ext = (a.name.split(".").pop() ?? a.mime_type.split("/").pop() ?? "FILE")
                .slice(0, 3)
                .toUpperCase();
              return (
                <div key={i} className="relative flex items-center gap-2 rounded-[10px] border border-line bg-bg px-2 py-1.5 text-[12.5px]">
                  <span className="grid h-7 w-7 place-items-center rounded-md bg-ink font-mono text-[10px] text-panel">{ext}</span>
                  <span className="max-w-[180px] truncate">{a.name}</span>
                  <button
                    type="button"
                    onClick={() => setPending((prev) => prev.filter((_, j) => j !== i))}
                    className="cursor-pointer px-0.5 text-muted transition hover:text-urgent"
                    title="Remove"
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder='Tell Loop the event — "corporate dinner Saturday, 80 guests, 10 staff, supplies and invoice"…'
          className="block min-h-[28px] w-full resize-none border-0 bg-transparent px-1.5 py-2 text-[15px] leading-snug text-ink outline-none placeholder:text-muted"
          style={{ maxHeight: 160 }}
        />

        <div className="flex items-center gap-1 pt-1">
          <CompBtn title="Attach image" onClick={() => imageInputRef.current?.click()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="3" width="12" height="10" rx="1.6" stroke="currentColor" strokeWidth="1.4" />
              <circle cx="6" cy="6.5" r="1.2" stroke="currentColor" strokeWidth="1.4" />
              <path d="M2.5 11l3.5-3 3 2.5 2-1.5 2.5 2" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </CompBtn>
          <CompBtn title="Attach file" onClick={() => fileInputRef.current?.click()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M10.5 6.5l-4 4a1.8 1.8 0 1 0 2.5 2.5l4.5-4.5a3 3 0 1 0-4.2-4.3L4 9.5a4.5 4.5 0 1 0 6.4 6.3"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </CompBtn>
          <CompBtn title="Record voice">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="6" y="2" width="4" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.4" />
              <path d="M4 7v1a4 4 0 0 0 8 0V7M8 12.5V14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </CompBtn>
          <CompBtn title="Record video">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="4" width="9" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
              <path d="M11 7l3-2v6l-3-2V7z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </CompBtn>
          <CompBtn title="Use a template">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 3h10v3H3V3zM3 8h6v5H3V8zM11 8h2v5h-2V8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </CompBtn>
          <CompBtn title="Mark urgent" danger>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2v7M8 12v1.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </CompBtn>

          <span className="flex-1" />

          <CompBtn title="Call Loop">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M3 3h2.5l1.2 3-1.7 1.6c.9 1.8 2.4 3.3 4.2 4.2L11 10.3l3 1.2V14h-1A10 10 0 0 1 3 4V3z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
            </svg>
          </CompBtn>
          <button
            type="submit"
            disabled={!canSend}
            title={canSend ? "Send" : "Type or attach first"}
            className="grid h-9 w-9 place-items-center rounded-[10px] bg-ink text-panel transition hover:-translate-y-px hover:bg-black disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-[#C8C3B4]"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 8l12-5-5 12-2-5-5-2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*,video/*"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </form>
    </div>
  );
}

function CompBtn({
  children,
  title,
  onClick,
  danger = false,
}: {
  children: React.ReactNode;
  title: string;
  onClick?: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`grid h-[34px] w-[34px] place-items-center rounded-lg border border-transparent text-ink-2 transition hover:border-line hover:bg-bg hover:text-ink ${
        danger ? "hover:border-urgent-soft hover:bg-urgent-soft hover:text-urgent" : ""
      }`}
    >
      {children}
    </button>
  );
}

/* ============================== context panel =============================== */

function ContextPanel() {
  return (
    <aside className="hidden flex-col overflow-y-auto border-l border-line bg-panel xl:flex">
      <div className="flex items-center justify-between border-b border-line px-[18px] py-3.5">
        <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-muted">Active context</span>
        <span className="inline-flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-wider text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_0_3px_rgba(62,124,78,0.18)]" />
          Live
        </span>
      </div>

      <CtxSection title="Current job">
        <div className="flex flex-col gap-2 rounded-[12px] border border-line bg-white p-3.5">
          <div className="flex items-center justify-between">
            <span className="font-display text-[24px] leading-none tracking-tight">Corporate dinner</span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-accent">
              ● Plan
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-3.5 gap-y-2 text-[12.5px] text-ink-2">
            <CtxField label="Date" value="This Saturday" />
            <CtxField label="Time" value="6–11 PM" />
            <CtxField label="Location" value="SoMa, SF" />
            <CtxField label="Invoice" value="$1,756" />
          </div>
          <div className="flex flex-wrap gap-2 border-t border-line-2 pt-2">
            <Pill variant="green">10 crew</Pill>
            <Pill>Supplies $86</Pill>
            <Pill>Labor $1,450</Pill>
          </div>
        </div>
      </CtxSection>

      <CtxSection title="Live timeline">
        <div className="flex flex-col">
          {[
            { state: "done", label: "Request parsed", time: "5:42" },
            { state: "done", label: "Plan inferred", time: "5:42" },
            { state: "live", label: "Awaiting owner approval", time: "now" },
            { state: "pending", label: "Shortlist crew", time: "—" },
            { state: "pending", label: "Text/call contractors", time: "—" },
            { state: "pending", label: "Prepare supplies", time: "—" },
            { state: "pending", label: "Draft invoice", time: "—" },
            { state: "pending", label: "Create payment holds", time: "—" },
          ].map((row, i, arr) => (
            <div key={row.label} className="relative grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-2.5 py-1.5 text-[12.5px]">
              {i < arr.length - 1 && <span className="absolute left-[8px] top-[18px] bottom-[-7px] w-[1.5px] bg-line" />}
              <TLDot state={row.state as "done" | "live" | "pending"} />
              <span className={row.state === "pending" ? "text-muted" : "text-ink-2"}>
                <b className="font-medium text-ink">{row.label}</b>
              </span>
              <span className="font-mono text-[10.5px] text-muted">{row.time}</span>
            </div>
          ))}
        </div>
      </CtxSection>

      <CtxSection title="Tools Loop is using">
        <div className="flex flex-col gap-1.5">
          <ToolRow label="Browser Use · supplies" detail="ready" />
          <ToolRow label="AgentPhone · SMS & calls" detail="pending" />
          <ToolRow label="AgentMail · invoice email" detail="draft" />
          <ToolRow label="Sponge · payment holds" detail="pending" />
          <ToolRow label="Moss · roster memory" detail="42 records" />
        </div>
      </CtxSection>

      <CtxSection title="Files in this thread" last>
        <div className="flex flex-col gap-1.5">
          <ToolRow label="event-request.txt" detail="parsed" badge="TXT" />
          <ToolRow label="supplies-plan.json" detail="draft" badge="JS" />
          <ToolRow label="client-invoice.pdf" detail="preview" badge="PDF" />
        </div>
      </CtxSection>
    </aside>
  );
}

function CtxSection({ title, children, last = false }: { title: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div className={`px-[18px] py-4 ${last ? "" : "border-b border-line-2"}`}>
      <h5 className="m-0 mb-2.5 font-mono text-[12px] font-medium uppercase tracking-wider text-muted">{title}</h5>
      {children}
    </div>
  );
}

function CtxField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <small className="block font-mono text-[10px] uppercase tracking-wider text-muted">{label}</small>
      {value}
    </div>
  );
}

function TLDot({ state }: { state: "done" | "live" | "pending" }) {
  if (state === "done") {
    return <span className="relative z-10 h-3.5 w-3.5 rounded-full border-[1.5px] border-accent bg-accent" />;
  }
  if (state === "live") {
    return <span className="tl-pulse relative z-10 h-3.5 w-3.5 rounded-full border-[1.5px] border-accent bg-white" />;
  }
  return <span className="relative z-10 h-3.5 w-3.5 rounded-full border-[1.5px] border-line bg-white" />;
}

function ToolRow({ label, detail, badge }: { label: string; detail: string; badge?: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-line-2 bg-white px-2 py-1.5 text-[12.5px] text-ink-2">
      <span
        className={`grid h-[22px] w-[22px] place-items-center rounded-md font-mono text-[9px] ${
          badge ? "bg-ink text-panel" : "bg-bg text-ink"
        }`}
      >
        {badge ?? <DotIcon />}
      </span>
      {label}
      <small className="ml-auto font-mono text-[10.5px] text-muted">{detail}</small>
    </div>
  );
}

function DotIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <circle cx="6" cy="6" r="2" fill="currentColor" />
    </svg>
  );
}

/* ============================== icons =============================== */

function DashboardIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 8l5-4 5 4v4H2V8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function ChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2.5 3.5h9v6h-5L3.5 11.5v-2h-1v-6z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function DispatchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="2" y="3" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2 6h10" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
function RosterIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="5" cy="5" r="2.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2 11.5c0-1.7 1.4-3 3-3s3 1.3 3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="10" cy="6" r="1.8" stroke="currentColor" strokeWidth="1.4" />
      <path d="M9 11.5c0-1.1.9-2 2-2s1 .4 1 .8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
function PaymentIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 11V5l4-3 4 3v6" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx="7" cy="7.5" r="1.4" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
