import type {
  BrowserImportResponse,
  BrowserSource,
  Call,
  Contractor,
  Conversation,
  Job,
  Message,
} from "./types";

const fallbackApiBaseUrl =
  typeof window !== "undefined" &&
  (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
    ? "http://127.0.0.1:8000"
    : "https://crewloop-api.ayushojha.com";

/**
 * Public API base URL. Read from NEXT_PUBLIC_API_BASE_URL first; when omitted,
 * local browser sessions talk to the local FastAPI server.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  fallbackApiBaseUrl;

export interface ChatActionChip {
  label: string;
  say: string;
}

export interface ChatEventPlan {
  source_event_id?: string | null;
  event_name: string;
  details: string;
  event_date: string;
  event_time: string;
  location?: string | null;
  staff_requirement: string;
  responsibilities: string;
  inventory_requirement: string;
  estimated_labor: string;
  invoice_amount: string;
  approval_question: string;
}

export interface ChatBulkOutreachRow {
  name: string;
  role: string;
  channel: string;
  phone_last4: string;
  status: string;
  response: string;
  live: boolean;
  delivery_status: string;
}

export interface ChatBulkOutreach {
  title: string;
  tag: string;
  status: string;
  summary: string;
  counts: {
    needed: number;
    filled: number;
    live_texts: number;
    live_calls: number;
    simulated_replies: number;
    declined: number;
  };
  rows: ChatBulkOutreachRow[];
  evidence: string[];
}

export interface ChatInvoiceLineItem {
  label: string;
  amount: string;
}

export interface ChatInvoiceInventoryItem {
  name: string;
  qty: string;
  amount: string;
}

export interface ChatInvoiceEmailReceipt {
  label: string;
  to: string;
  subject: string;
  status: string;
  provider: string;
  id?: string | null;
  detail: string;
}

export interface ChatSpongeWallet {
  name: string;
  role: string;
  arrival: string;
  shift: string;
  pay: string;
  wallet_id: string;
  status: string;
  release_rules: string[];
}

export interface ChatInvoiceEmail {
  title: string;
  tag: string;
  status: string;
  summary: string;
  event: {
    name: string;
    details: string;
    date: string;
    time: string;
    location: string;
    guests: string;
  };
  line_items: ChatInvoiceLineItem[];
  inventory_items: ChatInvoiceInventoryItem[];
  total: string;
  deposit: string;
  balance_due: string;
  emails: ChatInvoiceEmailReceipt[];
  wallets: ChatSpongeWallet[];
  cancellation_policy: string;
  evidence: string[];
}

export interface ChatScheduleRow {
  name: string;
  role: string;
  call_time: string;
  shift: string;
  station: string;
  pay: string;
  phone_last4: string;
  live: boolean;
}

export interface ChatSchedule {
  title: string;
  tag: string;
  status: string;
  summary: string;
  event: {
    date: string;
    time: string;
    location: string;
  };
  rows: ChatScheduleRow[];
  totals: {
    crew: number;
    labor: string;
    arrive_by: string;
    live_confirmed: number;
  };
  evidence: string[];
}

export interface ChatSupplyItem {
  name: string;
  qty: string;
  note: string;
  amount: string;
}

export interface ChatSupplies {
  title: string;
  tag: string;
  status: string;
  summary: string;
  event_id?: string | null;
  open_link: string;
  items: ChatSupplyItem[];
  total: string;
  vendors: string[];
  evidence: string[];
}

export interface ChatResponse {
  thread_id?: string | null;
  reply: string;
  intent?: string | null;
  event_plan?: ChatEventPlan | null;
  bulk_outreach?: ChatBulkOutreach | null;
  schedule?: ChatSchedule | null;
  supplies?: ChatSupplies | null;
  invoice_email?: ChatInvoiceEmail | null;
  action_chips?: ChatActionChip[];
}

export interface ChatThread {
  id: string;
  title: string;
  summary?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message?: string | null;
  last_role?: "user" | "agent" | string | null;
}

export interface ChatStoredMessage {
  id: string;
  thread_id: string;
  role: "user" | "agent";
  body: string;
  payload?: ChatResponse | Record<string, unknown>;
  attachments?: Array<{ mime_type: string; data: string; name?: string; preview_url?: string }>;
  created_at: string;
}

export interface ChatThreadDetail {
  thread: ChatThread;
  messages: ChatStoredMessage[];
}

export interface SupplyItem {
  id: string;
  event_id: string;
  inventory_item_id?: string | null;
  name: string;
  qty: number;
  unit: string;
  vendor: string | null;
  vendor_url: string | null;
  unit_price: number;
  total_price: number;
  status: "recommended" | "approved" | "ordered" | "delivered" | string;
  evidence_url?: string | null;
  evidence_eta?: string | null;
  evidence_note?: string | null;
  image_path?: string | null;
  notes?: string | null;
  approved_at?: string | null;
  // Live-browse (Browser Use Cloud)
  bu_session_id?: string | null;
  bu_live_url?: string | null;
  bu_status?: "running" | "idle" | "stopped" | "error" | "timed_out" | string | null;
  bu_step_count?: number | null;
  bu_cost_usd?: number | null;
  bu_output?: unknown;
  // Payment (Sponge wallet / Stripe MPP)
  payment_status?: "paid" | "pending" | "held" | "failed" | string | null;
  payment_method?: "sponge" | "stripe_mpp" | string | null;
  payment_ref?: string | null;
  paid_at?: string | null;
}

export interface SuppliesResponse {
  event: { id: string; role: string; start_time: string; description?: string | null };
  items: SupplyItem[];
  summary: { count: number; total: number; vendors: string[]; status: string };
}

export interface EventListItem {
  id: string;
  business_name: string;
  role: string;
  description: string | null;
  location: string;
  start_time: string;
  end_time: string;
  pay_amount: number;
  urgency: string;
  required_skills: string[];
  status: string;
  created_at: string;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { revalidate?: number } = {},
): Promise<T> {
  const { revalidate, ...rest } = init;
  const url = `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(rest.headers || {}),
    },
    // Next 16 caching: by default we want fresh data for dashboard polling,
    // but allow callers to opt into revalidation when the data is more static.
    ...(revalidate !== undefined
      ? { next: { revalidate } }
      : { cache: "no-store" }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listConversations: () =>
    request<{ items: Conversation[] }>("/api/conversations"),

  getConversation: (phone: string) =>
    request<{ conversation: Conversation; messages: Message[]; calls: Call[] }>(
      `/api/conversations/${encodeURIComponent(phone)}`,
    ),

  listCalls: () => request<{ items: Call[] }>("/api/calls"),

  sendSms: (payload: { to: string; body: string }) =>
    request<{ id: string; status: string }>("/api/sms/send", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  placeCall: (payload: {
    to: string;
    initial_greeting?: string;
    system_prompt?: string;
  }) =>
    request<Record<string, unknown>>("/api/calls/place", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  browserImport: (payload: { source_url?: string | null; force_local?: boolean }) =>
    request<BrowserImportResponse>("/api/browser/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getJob: (jobId: string) => request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`),

  getDispatch: (jobId: string) =>
    request<DispatchPayload>(`/api/dispatch/${encodeURIComponent(jobId)}`),

  listContractors: (params: { skill?: string; min_reliability?: number; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.skill) q.set("skill", params.skill);
    if (params.min_reliability != null) q.set("min_reliability", String(params.min_reliability));
    if (params.limit != null) q.set("limit", String(params.limit));
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return request<{ items: Contractor[] }>(`/api/contractors${suffix}`);
  },

  getContractor: (id: string) =>
    request<Contractor>(`/api/contractors/${encodeURIComponent(id)}`),

  chat: (payload: {
    turns: Array<{ role: "user" | "model" | "assistant"; text: string }>;
    attachments?: Array<{ mime_type: string; data: string; name?: string }>;
    thread_id?: string | null;
  }) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listChatThreads: (limit = 50) =>
    request<{ items: ChatThread[] }>(`/api/chat/threads?limit=${encodeURIComponent(String(limit))}`),

  createChatThread: (payload: { title?: string; initial_message?: string }) =>
    request<ChatThreadDetail>("/api/chat/threads", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getChatThread: (threadId: string) =>
    request<ChatThreadDetail>(`/api/chat/threads/${encodeURIComponent(threadId)}`),

  listEvents: (status?: string) =>
    request<{ items: EventListItem[]; count: number }>(
      `/api/events${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),

  getEvent: (eventId: string) =>
    request<EventListItem>(`/api/events/${encodeURIComponent(eventId)}`),

  recommendSupplies: (eventId: string, regenerate = false) =>
    request<SuppliesResponse>(
      `/api/events/${encodeURIComponent(eventId)}/supplies/recommend${regenerate ? "?regenerate=true" : ""}`,
      { method: "POST" },
    ),

  listSupplies: (eventId: string) =>
    request<SuppliesResponse>(`/api/events/${encodeURIComponent(eventId)}/supplies`),

  approveSupplies: (eventId: string) =>
    request<SuppliesResponse>(
      `/api/events/${encodeURIComponent(eventId)}/supplies/approve`,
      { method: "POST" },
    ),

  startLiveBrowse: (eventId: string) =>
    request<SuppliesResponse>(
      `/api/events/${encodeURIComponent(eventId)}/supplies/browse`,
      { method: "POST" },
    ),

  pollLiveBrowse: (eventId: string) =>
    request<SuppliesResponse>(
      `/api/events/${encodeURIComponent(eventId)}/supplies/browse`,
    ),

  paySupplies: (eventId: string, method: "sponge" | "stripe_mpp" = "sponge") =>
    request<SuppliesResponse & { payment: { method: string; count: number; total: number } }>(
      `/api/events/${encodeURIComponent(eventId)}/supplies/pay`,
      { method: "POST", body: JSON.stringify({ method }) },
    ),

  // Dispatch-room workflow actions (parallel-session backend routes).
  dispatchAction: (
    jobId: string,
    action: "outreach" | "accept" | "check-in" | "approve-release",
    body: Record<string, unknown> = {},
  ) =>
    request<Record<string, unknown>>(
      `/jobs/${encodeURIComponent(jobId)}/${action}`,
      { method: "POST", body: JSON.stringify(body) },
    ),
};

export interface DispatchContractor {
  initials: string;
  name: string;
  profile_image_url?: string;
  skills: string[];
  capabilities?: string[];
  can_do?: string;
  distance_miles: number;
  reliability_score: number;
  response_speed: string;
  memory_source?: string;
  status: "recommended" | "backup" | "ready" | "partial" | string;
  match_score: number;
}

export interface DispatchTimelineEvent {
  status: "complete" | "ready" | "pending" | "blocked" | string;
  label: string;
  detail: string;
  time: string;
}

export interface DispatchPayload {
  job: Job & { assigned_contractor_id?: string | null };
  contractors: DispatchContractor[];
  timeline: DispatchTimelineEvent[];
  payment: {
    status: string;
    amount: number;
    provider: string;
    release_conditions: Array<{ label: string; complete: boolean }>;
  };
  proof: {
    status: string;
    items: Array<{ type: string; status: string; detail: string }>;
  };
  owner_summary: {
    business_name: string;
    message: string;
    confirmed_contractor: string;
    eta: string;
    pay: number;
    proof: string;
    payment_status: string;
  };
  web_source: BrowserSource | null;
}
