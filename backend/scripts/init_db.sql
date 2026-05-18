CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS conversations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phone           text NOT NULL UNIQUE,
  display_name    text,
  last_message_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_last_message_at_idx
  ON conversations (last_message_at DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  agentphone_id   text UNIQUE,
  direction       text NOT NULL CHECK (direction IN ('inbound','outbound')),
  body            text NOT NULL,
  channel         text NOT NULL DEFAULT 'sms',
  from_number     text,
  to_number       text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_conversation_created_idx
  ON messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS calls (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agentphone_call_id   text UNIQUE,
  conversation_id      uuid REFERENCES conversations(id) ON DELETE SET NULL,
  to_number            text NOT NULL,
  direction            text NOT NULL DEFAULT 'outbound',
  duration_seconds     integer,
  disconnection_reason text,
  summary              text,
  user_sentiment       text,
  transcript           jsonb,
  started_at           timestamptz NOT NULL DEFAULT now(),
  ended_at             timestamptz
);

CREATE INDEX IF NOT EXISTS calls_started_at_idx ON calls (started_at DESC);
CREATE INDEX IF NOT EXISTS calls_conversation_idx ON calls (conversation_id);

CREATE TABLE IF NOT EXISTS contractors (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL,
  phone             text NOT NULL UNIQUE,
  email             text,
  age               integer,
  location          text NOT NULL,
  distance_miles    numeric(4,1),
  hourly_rate       numeric(6,2) NOT NULL,
  reliability_score integer NOT NULL CHECK (reliability_score BETWEEN 0 AND 100),
  response_speed    text NOT NULL,
  languages         text[] NOT NULL DEFAULT '{}',
  certifications    text[] NOT NULL DEFAULT '{}',
  notes             text,
  avatar_path       text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS contractors_reliability_idx ON contractors (reliability_score DESC);

CREATE TABLE IF NOT EXISTS contractor_skills (
  contractor_id uuid REFERENCES contractors(id) ON DELETE CASCADE,
  skill         text NOT NULL,
  PRIMARY KEY (contractor_id, skill)
);

CREATE INDEX IF NOT EXISTS contractor_skills_skill_idx ON contractor_skills (skill);

CREATE TABLE IF NOT EXISTS inventory_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sku           text NOT NULL UNIQUE,
  name          text NOT NULL,
  category      text NOT NULL,
  unit          text NOT NULL,
  par_level     numeric(10,2) NOT NULL,
  on_hand       numeric(10,2) NOT NULL,
  reorder_point numeric(10,2) NOT NULL,
  unit_cost     numeric(10,2) NOT NULL,
  supplier      text,
  location      text,
  description   text,
  image_path    text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inventory_items_category_idx ON inventory_items (category);
CREATE INDEX IF NOT EXISTS inventory_items_on_hand_idx ON inventory_items (on_hand);

CREATE TABLE IF NOT EXISTS event_supplies (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id          uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  inventory_item_id uuid REFERENCES inventory_items(id) ON DELETE SET NULL,
  name              text NOT NULL,
  qty               numeric(8,2) NOT NULL DEFAULT 1,
  unit              text NOT NULL DEFAULT 'each',
  vendor            text,
  vendor_url        text,
  unit_price        numeric(10,2) NOT NULL DEFAULT 0,
  total_price       numeric(10,2) NOT NULL DEFAULT 0,
  status            text NOT NULL DEFAULT 'recommended',
  evidence_url      text,
  evidence_eta      text,
  evidence_note     text,
  image_path        text,
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  approved_at       timestamptz
);

CREATE INDEX IF NOT EXISTS event_supplies_event_idx ON event_supplies (event_id);
CREATE INDEX IF NOT EXISTS event_supplies_status_idx ON event_supplies (status);

CREATE TABLE IF NOT EXISTS jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  business_name   text NOT NULL,
  role            text NOT NULL,
  description     text,
  location        text NOT NULL,
  start_time      text NOT NULL,
  end_time        text NOT NULL,
  pay_amount      numeric(10,2) NOT NULL,
  urgency         text NOT NULL,
  required_skills text[] NOT NULL DEFAULT '{}',
  status          text NOT NULL DEFAULT 'imported',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs (created_at DESC);

CREATE TABLE IF NOT EXISTS browser_sources (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id                uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  source_url            text NOT NULL,
  source_type           text NOT NULL,
  imported_fields       jsonb NOT NULL,
  screenshot_url        text,
  source_html_url       text,
  extraction_confidence numeric(4,3) NOT NULL DEFAULT 0,
  update_status         text NOT NULL DEFAULT 'pending',
  browser_action_log    jsonb NOT NULL DEFAULT '[]',
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS browser_sources_job_idx ON browser_sources (job_id);
CREATE INDEX IF NOT EXISTS browser_sources_created_at_idx ON browser_sources (created_at DESC);
