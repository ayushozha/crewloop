export interface Conversation {
  id: string;
  phone: string;
  display_name: string | null;
  last_message_at: string | null;
  created_at: string;
  last_message?: string | null;
  last_direction?: "inbound" | "outbound" | null;
  message_count?: number;
  call_count?: number;
}

export interface Message {
  id: string;
  agentphone_id: string | null;
  direction: "inbound" | "outbound";
  body: string;
  channel: string;
  from_number: string | null;
  to_number: string | null;
  created_at: string;
}

export interface Call {
  id: string;
  agentphone_call_id: string | null;
  conversation_id: string | null;
  to_number: string;
  direction: "outbound" | "inbound";
  duration_seconds: number | null;
  disconnection_reason: string | null;
  summary: string | null;
  user_sentiment: string | null;
  transcript: Array<{ role: string; content?: string; text?: string }> | string | null;
  started_at: string;
  ended_at: string | null;
}

export interface Job {
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
  source?: string;
  missing_fields?: string[];
  clarifying_question?: string | null;
  assigned_contractor_id?: string | null;
  locked_at?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface BrowserSource {
  id: string;
  job_id: string;
  source_url: string;
  source_type: string;
  imported_fields: Record<string, unknown> & {
    business_name?: string;
    role?: string;
    location?: string;
    start_time?: string;
    end_time?: string;
    pay_amount?: number;
    urgency?: string;
    required_skills?: string[];
  };
  screenshot_url: string | null;
  source_html_url: string | null;
  extraction_confidence: number;
  update_status: string;
  browser_action_log: Array<{ step: string; status: string; url?: string }>;
  created_at: string;
  business_name?: string;
  role?: string;
  location?: string;
  start_time?: string;
  end_time?: string;
}

export interface Contractor {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  age: number | null;
  location: string;
  distance_miles: number | null;
  hourly_rate: number;
  reliability_score: number;
  response_speed: string;
  languages: string[];
  certifications: string[];
  notes: string | null;
  avatar_path: string | null;
  skills: string[];
  created_at: string;
}

export interface BrowserImportResponse {
  job: Job;
  browser_source: BrowserSource;
  used_browser_use: boolean;
}

/* ----------------------- fill-a-shift loop ----------------------- */

export type InviteStatus =
  | "invited"
  | "yes"
  | "maybe"
  | "no"
  | "confirmed"
  | "cancelled";

export interface Shift {
  id: string;
  business_name: string;
  role: string;
  description?: string | null;
  location: string;
  start_time: string;
  end_time: string;
  pay_amount: number;
  headcount: number;
  status: string;
  event_at: string | null;
  invited_count: number;
  yes_count: number;
  created_at: string;
}

export interface CreateShiftPayload {
  business_name: string;
  role: string;
  description?: string;
  location: string;
  start_time: string;
  end_time: string;
  pay_amount: number;
  headcount: number;
  urgency?: string;
  /** ISO datetime; drives the T-48h/T-4h confirmation texts. */
  event_at?: string;
}

export interface ShiftInvite {
  id: string;
  contractor_id: string;
  name: string;
  phone: string;
  batch: number;
  status: InviteStatus;
  at_risk: boolean;
  last_reply_body: string | null;
  last_reply_at: string | null;
  last_outbound_at: string | null;
  ping_48_sent_at: string | null;
  ping_4_sent_at: string | null;
  priority: number;
  reliability_score: number;
}

export interface ShiftBoardCounts {
  needed: number;
  filled: number;
  invited: number;
  yes: number;
  maybe: number;
  no: number;
  confirmed: number;
  cancelled: number;
  at_risk: number;
}

export interface ShiftBoard {
  job: Shift;
  invites: ShiftInvite[];
  counts: ShiftBoardCounts;
}

export interface OutreachResult {
  batch: number;
  sent: Array<{ contractor_id: string; name: string; phone: string }>;
  errors: string[];
  candidates: number;
}

export interface ContractorImportResult {
  imported: number;
  updated: number;
  errors: string[];
  total_rows: number;
}
