from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from . import db


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STORE_PATH = DATA_DIR / "crewloop-store.json"
OLD_STORE_PATH = DATA_DIR / "browser-imports.json"
STORE_KEYS = [
    "jobs",
    "browser_sources",
    "events",
    "outreach",
    "schedules",
    "payments",
    "proofs",
    "notifications",
    "conversations",
    "messages",
    "chat_threads",
    "chat_messages",
    "calls",
]
USE_LOCAL_WORKFLOW_STORE = True


def _decode_jsonb(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _record_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("imported_fields", "browser_action_log", "transcript", "payload", "attachments"):
        if key in data:
            data[key] = _decode_jsonb(data[key])
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


def _load_browser_store() -> dict[str, list[dict[str, Any]]]:
    if not STORE_PATH.exists() and OLD_STORE_PATH.exists():
        with OLD_STORE_PATH.open("r", encoding="utf-8") as f:
            store = json.load(f)
        for key in STORE_KEYS:
            store.setdefault(key, [])
        _save_browser_store(store)
        return store
    if not STORE_PATH.exists():
        return {key: [] for key in STORE_KEYS}
    with STORE_PATH.open("r", encoding="utf-8") as f:
        store = json.load(f)
    for key in STORE_KEYS:
        store.setdefault(key, [])
    return store


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
        "source": imported_fields.get("source", "browser"),
        "missing_fields": imported_fields.get("missing_fields", []),
        "clarifying_question": imported_fields.get("clarifying_question"),
        "assigned_contractor_id": imported_fields.get("assigned_contractor_id"),
        "locked_at": imported_fields.get("locked_at"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
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


def _fallback_list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    store = _load_browser_store()
    return list(reversed(store["jobs"][-limit:]))


def _fallback_update_job(job_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
    store = _load_browser_store()
    wanted = str(job_id)
    for job in store["jobs"]:
        if job["id"] == wanted:
            job.update(updates)
            job["updated_at"] = _now_iso()
            _save_browser_store(store)
            return job
    return None


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


def _fallback_insert(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    store = _load_browser_store()
    item = {
        "id": str(uuid4()),
        "created_at": _now_iso(),
        **record,
    }
    store[kind].append(item)
    _save_browser_store(store)
    return item


def _fallback_list(kind: str, job_id: UUID | str | None = None) -> list[dict[str, Any]]:
    store = _load_browser_store()
    items = list(store[kind])
    if job_id is not None:
        wanted = str(job_id)
        items = [item for item in items if str(item.get("job_id")) == wanted]
    return items


def _fallback_update_first(
    kind: str,
    predicate: Any,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    store = _load_browser_store()
    for item in store[kind]:
        if predicate(item):
            item.update(updates)
            item["updated_at"] = _now_iso()
            _save_browser_store(store)
            return item
    return None


async def upsert_conversation(phone: str, display_name: str | None = None) -> UUID:
    if not db.available():
        store = _load_browser_store()
        existing = next((item for item in store["conversations"] if item["phone"] == phone), None)
        if existing:
            if display_name:
                existing["display_name"] = display_name
            existing["last_message_at"] = _now_iso()
            _save_browser_store(store)
            return UUID(existing["id"])
        conv = {
            "id": str(uuid4()),
            "phone": phone,
            "display_name": display_name,
            "last_message_at": _now_iso(),
            "created_at": _now_iso(),
        }
        store["conversations"].append(conv)
        _save_browser_store(store)
        return UUID(conv["id"])

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
    if not db.available():
        store = _load_browser_store()
        if agentphone_id and any(item.get("agentphone_id") == agentphone_id for item in store["messages"]):
            return None
        message = {
            "id": str(uuid4()),
            "conversation_id": str(conv_id),
            "agentphone_id": agentphone_id,
            "direction": direction,
            "body": body,
            "channel": channel,
            "from_number": from_number,
            "to_number": to_number,
            "created_at": _now_iso(),
        }
        store["messages"].append(message)
        for conv in store["conversations"]:
            if conv["id"] == str(conv_id):
                conv["last_message_at"] = message["created_at"]
        _save_browser_store(store)
        return UUID(message["id"])

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
    if not db.available():
        call = _fallback_insert(
            "calls",
            {
                "agentphone_call_id": agentphone_call_id,
                "conversation_id": str(conv_id),
                "to_number": to_number,
                "direction": "outbound",
                "started_at": started_at.isoformat() if started_at else _now_iso(),
            },
        )
        return UUID(call["id"])

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
    if not db.available():
        _fallback_update_first(
            "calls",
            lambda item: item.get("agentphone_call_id") == agentphone_call_id,
            {
                "duration_seconds": duration_seconds,
                "disconnection_reason": disconnection_reason,
                "summary": summary,
                "user_sentiment": user_sentiment,
                "transcript": transcript,
                "ended_at": _now_iso(),
            },
        )
        return

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
    if not db.available():
        store = _load_browser_store()
        messages = store["messages"]
        calls = store["calls"]
        rows = []
        for conv in reversed(store["conversations"][-limit:]):
            conv_messages = [item for item in messages if item["conversation_id"] == conv["id"]]
            conv_calls = [item for item in calls if item.get("conversation_id") == conv["id"]]
            last = conv_messages[-1] if conv_messages else {}
            rows.append(
                {
                    **conv,
                    "last_message": last.get("body"),
                    "last_direction": last.get("direction"),
                    "message_count": len(conv_messages),
                    "call_count": len(conv_calls),
                }
            )
        return rows

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
    if not db.available():
        store = _load_browser_store()
        return next((item for item in store["conversations"] if item["phone"] == phone), None)

    sql = "SELECT * FROM conversations WHERE phone = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, phone)
    return dict(row) if row else None


async def list_messages(conversation_id: UUID, limit: int = 500) -> list[dict[str, Any]]:
    if not db.available():
        store = _load_browser_store()
        wanted = str(conversation_id)
        return [item for item in store["messages"] if item["conversation_id"] == wanted][:limit]

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


async def create_chat_thread(*, title: str, summary: str | None = None) -> dict[str, Any]:
    if not db.available():
        store = _load_browser_store()
        now = _now_iso()
        thread = {
            "id": str(uuid4()),
            "title": title,
            "summary": summary,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        store["chat_threads"].append(thread)
        _save_browser_store(store)
        return thread

    sql = """
        INSERT INTO chat_threads (title, summary)
        VALUES ($1, $2)
        RETURNING id, title, summary, status, created_at, updated_at
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, title, summary)
    return dict(row)


async def get_chat_thread(thread_id: UUID | str) -> dict[str, Any] | None:
    wanted = str(thread_id)
    if not db.available():
        store = _load_browser_store()
        return next((item for item in store["chat_threads"] if item["id"] == wanted), None)

    sql = """
        SELECT id, title, summary, status, created_at, updated_at
        FROM chat_threads
        WHERE id = $1
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, UUID(wanted))
    return dict(row) if row else None


async def list_chat_threads(limit: int = 50) -> list[dict[str, Any]]:
    if not db.available():
        store = _load_browser_store()
        messages = store["chat_messages"]
        rows = []
        for thread in sorted(store["chat_threads"], key=lambda item: item.get("updated_at") or "", reverse=True)[:limit]:
            thread_messages = [m for m in messages if m["thread_id"] == thread["id"]]
            last = thread_messages[-1] if thread_messages else {}
            rows.append(
                {
                    **thread,
                    "message_count": len(thread_messages),
                    "last_message": last.get("body"),
                    "last_role": last.get("role"),
                }
            )
        return rows

    sql = """
        SELECT t.id, t.title, t.summary, t.status, t.created_at, t.updated_at,
          (SELECT count(*) FROM chat_messages m WHERE m.thread_id = t.id) AS message_count,
          (SELECT body FROM chat_messages m WHERE m.thread_id = t.id
            ORDER BY m.created_at DESC LIMIT 1) AS last_message,
          (SELECT role FROM chat_messages m WHERE m.thread_id = t.id
            ORDER BY m.created_at DESC LIMIT 1) AS last_role
        FROM chat_threads t
        ORDER BY t.updated_at DESC, t.created_at DESC
        LIMIT $1
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [dict(r) for r in rows]


async def list_chat_messages(thread_id: UUID | str, limit: int = 500) -> list[dict[str, Any]]:
    wanted = str(thread_id)
    if not db.available():
        store = _load_browser_store()
        return [
            _record_to_dict(item)
            for item in store["chat_messages"]
            if item["thread_id"] == wanted
        ][:limit]

    sql = """
        SELECT id, thread_id, role, body, payload, attachments, created_at
        FROM chat_messages
        WHERE thread_id = $1
        ORDER BY created_at ASC
        LIMIT $2
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, UUID(wanted), limit)
    return [_record_to_dict(r) for r in rows]


async def append_chat_message(
    *,
    thread_id: UUID | str,
    role: str,
    body: str,
    payload: dict[str, Any] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    wanted = str(thread_id)
    payload = payload or {}
    attachments = attachments or []
    if not db.available():
        store = _load_browser_store()
        message = {
            "id": str(uuid4()),
            "thread_id": wanted,
            "role": role,
            "body": body,
            "payload": payload,
            "attachments": attachments,
            "created_at": _now_iso(),
        }
        store["chat_messages"].append(message)
        for thread in store["chat_threads"]:
            if thread["id"] == wanted:
                thread["updated_at"] = message["created_at"]
                if not thread.get("summary"):
                    thread["summary"] = body[:140]
                break
        _save_browser_store(store)
        return message

    sql = """
        INSERT INTO chat_messages (thread_id, role, body, payload, attachments)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
        RETURNING id, thread_id, role, body, payload, attachments, created_at
    """
    update_thread = """
        UPDATE chat_threads
        SET updated_at = now(),
            summary = COALESCE(summary, NULLIF($2, ''))
        WHERE id = $1
    """
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                sql,
                UUID(wanted),
                role,
                body,
                json.dumps(payload),
                json.dumps(attachments),
            )
            await conn.execute(update_thread, UUID(wanted), body[:140])
    return _record_to_dict(row)


async def list_calls(limit: int = 100) -> list[dict[str, Any]]:
    if not db.available():
        return list(reversed(_load_browser_store()["calls"][-limit:]))

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
    if not db.available():
        wanted = str(conversation_id)
        return [item for item in _load_browser_store()["calls"] if item.get("conversation_id") == wanted]

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
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
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
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
        return _fallback_get_job(job_id)

    sql = "SELECT * FROM jobs WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, job_id)
    return _record_to_dict(row) if row else None


async def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
        return _fallback_list_jobs(limit=limit)

    sql = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT $1"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [_record_to_dict(r) for r in rows]


async def update_job(job_id: UUID | str, **updates: Any) -> dict[str, Any] | None:
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
        return _fallback_update_job(job_id, updates)

    allowed = {
        "business_name",
        "role",
        "description",
        "location",
        "start_time",
        "end_time",
        "pay_amount",
        "urgency",
        "required_skills",
        "status",
    }
    filtered = {key: value for key, value in updates.items() if key in allowed}
    if not filtered:
        return await get_job(UUID(str(job_id)))
    assignments = ", ".join(f"{key} = ${idx + 2}" for idx, key in enumerate(filtered))
    sql = f"UPDATE jobs SET {assignments} WHERE id = $1 RETURNING *"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, UUID(str(job_id)), *filtered.values())
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
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
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
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
        return _fallback_get_browser_source(source_id)

    sql = "SELECT * FROM browser_sources WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, source_id)
    return _record_to_dict(row) if row else None


async def list_browser_sources(limit: int = 50) -> list[dict[str, Any]]:
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
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
    if USE_LOCAL_WORKFLOW_STORE or not db.available():
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


async def create_event(
    *,
    job_id: UUID | str,
    type: str,
    content: str,
    status: str = "complete",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _fallback_insert(
        "events",
        {
            "job_id": str(job_id),
            "type": type,
            "content": content,
            "status": status,
            "metadata": metadata or {},
        },
    )


async def list_events(job_id: UUID | str) -> list[dict[str, Any]]:
    return _fallback_list("events", job_id)


async def create_outreach(
    *,
    job_id: UUID | str,
    contractor_id: str,
    channel: str,
    message: str,
    status: str,
    provider_id: str | None = None,
    response: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _fallback_insert(
        "outreach",
        {
            "job_id": str(job_id),
            "contractor_id": contractor_id,
            "channel": channel,
            "message": message,
            "status": status,
            "provider_id": provider_id,
            "response": response,
            "metadata": metadata or {},
        },
    )


async def list_outreach(job_id: UUID | str) -> list[dict[str, Any]]:
    return _fallback_list("outreach", job_id)


async def update_outreach_response(
    *,
    job_id: UUID | str,
    contractor_id: str,
    response: str,
    status: str,
) -> dict[str, Any] | None:
    return _fallback_update_first(
        "outreach",
        lambda item: str(item.get("job_id")) == str(job_id)
        and item.get("contractor_id") == contractor_id
        and item.get("channel") in {"sms", "call"},
        {"response": response, "status": status},
    )


async def create_schedule(
    *,
    job_id: UUID | str,
    contractor_id: str,
    start_time: str,
    end_time: str,
    status: str = "confirmed",
) -> dict[str, Any]:
    existing = _fallback_update_first(
        "schedules",
        lambda item: str(item.get("job_id")) == str(job_id),
        {
            "contractor_id": contractor_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
        },
    )
    if existing:
        return existing
    return _fallback_insert(
        "schedules",
        {
            "job_id": str(job_id),
            "contractor_id": contractor_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
        },
    )


async def list_schedules(job_id: UUID | str) -> list[dict[str, Any]]:
    return _fallback_list("schedules", job_id)


async def upsert_payment(
    *,
    job_id: UUID | str,
    contractor_id: str | None,
    amount: float,
    status: str,
    release_conditions: list[dict[str, Any]],
    provider_state: dict[str, Any] | None = None,
    receipt_url: str | None = None,
) -> dict[str, Any]:
    updates = {
        "contractor_id": contractor_id,
        "amount": amount,
        "status": status,
        "release_conditions": release_conditions,
        "provider_state": provider_state or {},
        "receipt_url": receipt_url,
    }
    existing = _fallback_update_first(
        "payments",
        lambda item: str(item.get("job_id")) == str(job_id),
        updates,
    )
    if existing:
        return existing
    return _fallback_insert("payments", {"job_id": str(job_id), **updates})


async def get_payment(job_id: UUID | str) -> dict[str, Any] | None:
    payments = _fallback_list("payments", job_id)
    return payments[-1] if payments else None


async def create_proof(
    *,
    job_id: UUID | str,
    contractor_id: str,
    type: str,
    content_url: str | None,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _fallback_insert(
        "proofs",
        {
            "job_id": str(job_id),
            "contractor_id": contractor_id,
            "type": type,
            "content_url": content_url,
            "status": status,
            "metadata": metadata or {},
        },
    )


async def list_proofs(job_id: UUID | str) -> list[dict[str, Any]]:
    return _fallback_list("proofs", job_id)


async def create_notification(
    *,
    job_id: UUID | str,
    channel: str,
    recipient: str,
    subject: str,
    body: str,
    status: str,
    provider_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _fallback_insert(
        "notifications",
        {
            "job_id": str(job_id),
            "channel": channel,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "status": status,
            "provider_id": provider_id,
            "metadata": metadata or {},
        },
    )


async def list_notifications(job_id: UUID | str) -> list[dict[str, Any]]:
    return _fallback_list("notifications", job_id)


async def update_browser_source_status(
    *,
    job_id: UUID | str,
    update_status: str,
) -> dict[str, Any] | None:
    return _fallback_update_first(
        "browser_sources",
        lambda item: str(item.get("job_id")) == str(job_id),
        {"update_status": update_status},
    )
