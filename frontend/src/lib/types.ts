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

export interface BrowserImportResponse {
  job: Job;
  browser_source: BrowserSource;
  used_browser_use: boolean;
}
