from datetime import datetime
from decimal import Decimal
import json
from typing import Any
from uuid import UUID

from . import db


def _decode_jsonb(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _record_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("imported_fields", "browser_action_log", "transcript"):
        if key in data:
            data[key] = _decode_jsonb(data[key])
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


async def upsert_conversation(phone: str, display_name: str | None = None) -> UUID:
    sql = """
        INSERT INTO conversations (phone, display_name)
        VALUES ($1, $2)
        ON CONFLICT (phone) DO UPDATE
          SET display_name = COALESCE(EXCLUDED.display_name, conversations.display_name)
        RETURNING id
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, phone, display_name)
    return row["id"]


async def record_message(
    *,
    phone: str,
    direction: str,
    body: str,
    agentphone_id: str | None = None,
    from_number: str | None = None,
    to_number: str | None = None,
    channel: str = "sms",
) -> UUID:
    conv_id = await upsert_conversation(phone)
    sql = """
        INSERT INTO messages
          (conversation_id, agentphone_id, direction, body, channel, from_number, to_number)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (agentphone_id) DO NOTHING
        RETURNING id
    """
    update_conv = """
        UPDATE conversations SET last_message_at = now() WHERE id = $1
    """
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                sql, conv_id, agentphone_id, direction, body, channel, from_number, to_number,
            )
            await conn.execute(update_conv, conv_id)
    return row["id"] if row else conv_id


async def record_call(
    *,
    to_number: str,
    agentphone_call_id: str | None,
    started_at: datetime | None = None,
) -> UUID:
    conv_id = await upsert_conversation(to_number)
    sql = """
        INSERT INTO calls (agentphone_call_id, conversation_id, to_number, direction, started_at)
        VALUES ($1, $2, $3, 'outbound', COALESCE($4, now()))
        ON CONFLICT (agentphone_call_id) DO UPDATE
          SET conversation_id = EXCLUDED.conversation_id
        RETURNING id
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, agentphone_call_id, conv_id, to_number, started_at)
    return row["id"]


async def finalize_call(
    *,
    agentphone_call_id: str,
    duration_seconds: int | None,
    disconnection_reason: str | None,
    summary: str | None,
    user_sentiment: str | None,
    transcript: list[dict[str, Any]] | None,
) -> None:
    import json
    sql = """
        UPDATE calls SET
          duration_seconds     = $2,
          disconnection_reason = $3,
          summary              = $4,
          user_sentiment       = $5,
          transcript           = $6::jsonb,
          ended_at             = now()
        WHERE agentphone_call_id = $1
    """
    async with db.pool().acquire() as conn:
        await conn.execute(
            sql,
            agentphone_call_id,
            duration_seconds,
            disconnection_reason,
            summary,
            user_sentiment,
            json.dumps(transcript) if transcript is not None else None,
        )


async def list_conversations(limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT c.id, c.phone, c.display_name, c.last_message_at, c.created_at,
          (SELECT body FROM messages m WHERE m.conversation_id = c.id
            ORDER BY m.created_at DESC LIMIT 1) AS last_message,
          (SELECT direction FROM messages m WHERE m.conversation_id = c.id
            ORDER BY m.created_at DESC LIMIT 1) AS last_direction,
          (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
          (SELECT count(*) FROM calls k WHERE k.conversation_id = c.id) AS call_count
        FROM conversations c
        ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC
        LIMIT $1
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [dict(r) for r in rows]


async def get_conversation_by_phone(phone: str) -> dict[str, Any] | None:
    sql = "SELECT * FROM conversations WHERE phone = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, phone)
    return dict(row) if row else None


async def list_messages(conversation_id: UUID, limit: int = 500) -> list[dict[str, Any]]:
    sql = """
        SELECT id, agentphone_id, direction, body, channel, from_number, to_number, created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        LIMIT $2
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, conversation_id, limit)
    return [dict(r) for r in rows]


async def list_calls(limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT id, agentphone_call_id, conversation_id, to_number, direction,
               duration_seconds, disconnection_reason, summary, user_sentiment,
               started_at, ended_at
        FROM calls
        ORDER BY started_at DESC
        LIMIT $1
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [dict(r) for r in rows]


async def list_calls_for_conversation(conversation_id: UUID) -> list[dict[str, Any]]:
    sql = """
        SELECT id, agentphone_call_id, to_number, direction, duration_seconds,
               disconnection_reason, summary, user_sentiment, transcript,
               started_at, ended_at
        FROM calls
        WHERE conversation_id = $1
        ORDER BY started_at ASC
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, conversation_id)
    out = []
    for r in rows:
        d = _record_to_dict(r)
        # asyncpg returns jsonb as str; surface as parsed JSON for the API.
        out.append(d)
    return out


async def create_job_from_import(imported_fields: dict[str, Any]) -> dict[str, Any]:
    sql = """
        INSERT INTO jobs (
          business_name, role, description, location, start_time, end_time,
          pay_amount, urgency, required_skills, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'imported')
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql,
            imported_fields["business_name"],
            imported_fields["role"],
            imported_fields.get("description"),
            imported_fields["location"],
            imported_fields["start_time"],
            imported_fields["end_time"],
            imported_fields["pay_amount"],
            imported_fields["urgency"],
            imported_fields["required_skills"],
        )
    return _record_to_dict(row)


async def get_job(job_id: UUID) -> dict[str, Any] | None:
    sql = "SELECT * FROM jobs WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, job_id)
    return _record_to_dict(row) if row else None


async def create_browser_source(
    *,
    job_id: UUID,
    source_url: str,
    source_type: str,
    imported_fields: dict[str, Any],
    screenshot_url: str | None,
    source_html_url: str | None,
    extraction_confidence: float,
    update_status: str,
    browser_action_log: list[dict[str, Any]],
) -> dict[str, Any]:
    sql = """
        INSERT INTO browser_sources (
          job_id, source_url, source_type, imported_fields, screenshot_url,
          source_html_url, extraction_confidence, update_status, browser_action_log
        )
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9::jsonb)
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql,
            job_id,
            source_url,
            source_type,
            json.dumps(imported_fields),
            screenshot_url,
            source_html_url,
            extraction_confidence,
            update_status,
            json.dumps(browser_action_log),
        )
    return _record_to_dict(row)


async def get_browser_source(source_id: UUID) -> dict[str, Any] | None:
    sql = "SELECT * FROM browser_sources WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, source_id)
    return _record_to_dict(row) if row else None


async def list_browser_sources(limit: int = 50) -> list[dict[str, Any]]:
    sql = """
        SELECT bs.*, j.business_name, j.role, j.location, j.start_time, j.end_time
        FROM browser_sources bs
        JOIN jobs j ON j.id = bs.job_id
        ORDER BY bs.created_at DESC
        LIMIT $1
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [_record_to_dict(r) for r in rows]
