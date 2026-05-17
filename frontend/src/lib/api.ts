import type {
  BrowserImportResponse,
  BrowserSource,
  Call,
  Conversation,
  Job,
  Message,
} from "./types";

/**
 * Public API base URL. Read from NEXT_PUBLIC_API_BASE_URL at build/run time so
 * a single Next build can target prod or local without recompiling.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "https://crewloop-api.ayushojha.com";

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
  skills: string[];
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
