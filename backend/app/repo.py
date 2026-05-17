from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from . import db


STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "browser-imports.json"


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


def _load_browser_store() -> dict[str, list[dict[str, Any]]]:
    if not STORE_PATH.exists():
        return {"jobs": [], "browser_sources": []}
    with STORE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_browser_store(store: dict[str, list[dict[str, Any]]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STORE_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    tmp_path.replace(STORE_PATH)


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _fallback_create_job(imported_fields: dict[str, Any]) -> dict[str, Any]:
    store = _load_browser_store()
    job = {
        "id": str(uuid4()),
        "business_name": imported_fields["business_name"],
        "role": imported_fields["role"],
        "description": imported_fields.get("description"),
        "location": imported_fields["location"],
        "start_time": imported_fields["start_time"],
        "end_time": imported_fields["end_time"],
        "pay_amount": float(imported_fields["pay_amount"]),
        "urgency": imported_fields["urgency"],
        "required_skills": imported_fields["required_skills"],
        "status": "imported",
        "created_at": _now_iso(),
    }
    store["jobs"].append(job)
    _save_browser_store(store)
    return job


def _fallback_create_browser_source(
    *,
    job_id: UUID | str,
    source_url: str,
    source_type: str,
    imported_fields: dict[str, Any],
    screenshot_url: str | None,
    source_html_url: str | None,
    extraction_confidence: float,
    update_status: str,
    browser_action_log: list[dict[str, Any]],
) -> dict[str, Any]:
    store = _load_browser_store()
    source = {
        "id": str(uuid4()),
        "job_id": str(job_id),
        "source_url": source_url,
        "source_type": source_type,
        "imported_fields": imported_fields,
        "screenshot_url": screenshot_url,
        "source_html_url": source_html_url,
        "extraction_confidence": float(extraction_confidence),
        "update_status": update_status,
        "browser_action_log": browser_action_log,
        "created_at": _now_iso(),
    }
    store["browser_sources"].append(source)
    _save_browser_store(store)
    return source


def _fallback_get_job(job_id: UUID | str) -> dict[str, Any] | None:
    store = _load_browser_store()
    wanted = str(job_id)
    return next((job for job in store["jobs"] if job["id"] == wanted), None)


def _fallback_get_browser_source(source_id: UUID | str) -> dict[str, Any] | None:
    store = _load_browser_store()
    wanted = str(source_id)
    return next((source for source in store["browser_sources"] if source["id"] == wanted), None)


def _fallback_list_browser_sources(limit: int = 50) -> list[dict[str, Any]]:
    store = _load_browser_store()
    jobs = {job["id"]: job for job in store["jobs"]}
    rows: list[dict[str, Any]] = []
    for source in reversed(store["browser_sources"][-limit:]):
        job = jobs.get(source["job_id"], {})
        rows.append(
            {
                **source,
                "business_name": job.get("business_name"),
                "role": job.get("role"),
                "location": job.get("location"),
                "start_time": job.get("start_time"),
                "end_time": job.get("end_time"),
            }
        )
    return rows


def _fallback_list_browser_sources_for_job(job_id: UUID | str) -> list[dict[str, Any]]:
    wanted = str(job_id)
    return [
        source
        for source in _fallback_list_browser_sources(limit=500)
        if str(source["job_id"]) == wanted
    ]


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
) -> UUID | None:
    """Insert a message; returns the new row id, or None if the row already
    existed (ON CONFLICT on agentphone_id). Callers can gate side effects (like
    auto-reply) on a fresh insert so retries don't double-send."""
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
    return row["id"] if row else None


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
    if not db.available():
        return _fallback_create_job(imported_fields)

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
    if not db.available():
        return _fallback_get_job(job_id)

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
    if not db.available():
        return _fallback_create_browser_source(
            job_id=job_id,
            source_url=source_url,
            source_type=source_type,
            imported_fields=imported_fields,
            screenshot_url=screenshot_url,
            source_html_url=source_html_url,
            extraction_confidence=extraction_confidence,
            update_status=update_status,
            browser_action_log=browser_action_log,
        )

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
    if not db.available():
        return _fallback_get_browser_source(source_id)

    sql = "SELECT * FROM browser_sources WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, source_id)
    return _record_to_dict(row) if row else None


async def list_browser_sources(limit: int = 50) -> list[dict[str, Any]]:
    if not db.available():
        return _fallback_list_browser_sources(limit=limit)

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


async def list_browser_sources_for_job(job_id: UUID | str) -> list[dict[str, Any]]:
    if not db.available():
        return _fallback_list_browser_sources_for_job(job_id)

    sql = """
        SELECT *
        FROM browser_sources
        WHERE job_id = $1
        ORDER BY created_at DESC
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_record_to_dict(r) for r in rows]
