from typing import Optional
import logging

import asyncpg

from .config import settings


_pool: Optional[asyncpg.Pool] = None
_connect_error: Exception | None = None
logger = logging.getLogger("crewloop.db")
INIT_SQL = """
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
"""


async def connect() -> None:
    global _pool, _connect_error
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=8,
                command_timeout=30,
            )
            await ensure_schema()
            _connect_error = None
        except Exception as exc:
            _connect_error = exc
            _pool = None
            logger.warning("Postgres unavailable; browser import will use local JSON storage: %s", exc)


async def ensure_schema() -> None:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    async with _pool.acquire() as conn:
        await conn.execute(INIT_SQL)


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized; lifespan did not run")
    return _pool


def available() -> bool:
    return _pool is not None


def connect_error() -> Exception | None:
    return _connect_error
