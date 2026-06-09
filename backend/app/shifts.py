"""The fill-a-shift loop: roster import, priority-batch outreach, reply
handling, T-48h/T-4h confirmation pings, at-risk flagging, and cascade.

This is the one loop the June 2026 plan makes real. Everything sends real SMS
through AgentPhone — there is no simulated path in this module.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from . import db, repo
from .agentphone import AgentPhoneError, get_client
from .config import settings
from .shift_logic import classify_reply, invite_message, is_at_risk, ping_message

logger = logging.getLogger("crewloop.shifts")

PING_LOOP_SECONDS = 300


# ---------------------------------------------------------------------------
# Roster import
# ---------------------------------------------------------------------------

async def import_roster(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert contractors by phone. New rows get sane defaults; existing rows
    keep their reliability data and only refresh the operator-supplied fields."""
    imported = 0
    updated = 0
    upsert_sql = """
        INSERT INTO contractors
          (name, phone, email, location, hourly_rate, reliability_score,
           response_speed, notes, priority)
        VALUES ($1, $2, $3, $4, $5, 80, 'unknown', $6, $7)
        ON CONFLICT (phone) DO UPDATE SET
          name = EXCLUDED.name,
          email = COALESCE(EXCLUDED.email, contractors.email),
          location = CASE WHEN EXCLUDED.location <> '' THEN EXCLUDED.location ELSE contractors.location END,
          hourly_rate = COALESCE(NULLIF(EXCLUDED.hourly_rate, 0), contractors.hourly_rate),
          notes = COALESCE(EXCLUDED.notes, contractors.notes),
          priority = EXCLUDED.priority
        RETURNING (xmax = 0) AS inserted, id
    """
    async with db.pool().acquire() as conn:
        for row in rows:
            record = await conn.fetchrow(
                upsert_sql,
                row["name"],
                row["phone"],
                row.get("email"),
                row.get("location") or "",
                row.get("hourly_rate") or 0,
                row.get("notes"),
                row.get("priority", 100),
            )
            if record["inserted"]:
                imported += 1
            else:
                updated += 1
            for skill in row.get("skills") or []:
                await conn.execute(
                    "INSERT INTO contractor_skills (contractor_id, skill) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    record["id"],
                    skill,
                )
    return {"imported": imported, "updated": updated}


# ---------------------------------------------------------------------------
# Shift create / list
# ---------------------------------------------------------------------------

async def create_shift(fields: dict[str, Any]) -> dict[str, Any]:
    sql = """
        INSERT INTO jobs
          (business_name, role, description, location, start_time, end_time,
           pay_amount, urgency, status, headcount, event_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open', $9, $10)
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql,
            fields.get("business_name") or "CrewLoop pilot",
            (fields.get("role") or "").lower(),
            fields.get("description"),
            fields.get("location") or "",
            fields.get("start_time") or "",
            fields.get("end_time") or "",
            fields.get("pay_amount") or 0,
            fields.get("urgency") or "normal",
            fields.get("headcount") or 1,
            fields.get("event_at"),
        )
    return _row(row)


async def list_shifts(limit: int = 25) -> list[dict[str, Any]]:
    sql = """
        SELECT j.*,
          (SELECT count(*) FROM shift_invites si WHERE si.job_id = j.id) AS invited_count,
          (SELECT count(*) FROM shift_invites si WHERE si.job_id = j.id AND si.status IN ('yes','confirmed')) AS yes_count
        FROM jobs j
        WHERE j.status IN ('open', 'outreach_sent')
        ORDER BY j.created_at DESC
        LIMIT $1
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Outreach + cascade
# ---------------------------------------------------------------------------

async def start_outreach(
    job_id: UUID, *, batch_size: int = 5, match_role: bool = True
) -> dict[str, Any]:
    """Invite the next batch of contractors in priority order over real SMS.
    Skips opted-out workers and anyone already invited for this shift."""
    async with db.pool().acquire() as conn:
        job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job_row:
            return {"error": "shift not found", "sent": []}
        job = _row(job_row)

        candidates_sql = """
            SELECT c.id, c.name, c.phone FROM contractors c
            WHERE NOT c.opted_out
              AND NOT EXISTS (SELECT 1 FROM shift_invites si WHERE si.job_id = $1 AND si.contractor_id = c.id)
              AND ($2::text IS NULL OR EXISTS (
                SELECT 1 FROM contractor_skills cs WHERE cs.contractor_id = c.id AND cs.skill = $2
              ))
            ORDER BY c.priority ASC, c.reliability_score DESC, c.name
            LIMIT $3
        """
        role_filter = job["role"].lower() if (match_role and job.get("role")) else None
        candidates = await conn.fetch(candidates_sql, job_id, role_filter, batch_size)
        batch = (await conn.fetchval(
            "SELECT COALESCE(MAX(batch), 0) + 1 FROM shift_invites WHERE job_id = $1", job_id
        ))

    body = invite_message(job)
    sent: list[dict[str, Any]] = []
    errors: list[str] = []
    for c in candidates:
        try:
            result = await get_client().send_message(to_number=c["phone"], body=body)
        except AgentPhoneError as exc:
            errors.append(f"{c['name']} ({c['phone']}): AgentPhone {exc.status}")
            continue
        except Exception as exc:  # network etc. — keep going down the list
            errors.append(f"{c['name']} ({c['phone']}): {exc}")
            continue
        async with db.pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO shift_invites (job_id, contractor_id, batch, status, last_outbound_at)
                VALUES ($1, $2, $3, 'invited', now())
                ON CONFLICT (job_id, contractor_id) DO NOTHING
                """,
                job_id, c["id"], batch,
            )
        try:
            await repo.record_message(
                phone=c["phone"], direction="outbound", body=body,
                agentphone_id=result.get("id"),
                from_number=result.get("from_number"),
                to_number=c["phone"],
            )
        except Exception:
            logger.exception("failed to persist invite SMS")
        sent.append({"contractor_id": str(c["id"]), "name": c["name"], "phone": c["phone"]})

    if sent:
        async with db.pool().acquire() as conn:
            await conn.execute("UPDATE jobs SET status = 'outreach_sent' WHERE id = $1", job_id)
    return {"batch": batch, "sent": sent, "errors": errors, "candidates": len(candidates)}


# ---------------------------------------------------------------------------
# Inbound replies (called from the AgentPhone webhook)
# ---------------------------------------------------------------------------

async def handle_inbound_sms(phone: str, body: str) -> dict[str, Any]:
    """STOP/START compliance plus shift-invite reply handling.

    Returns {handled: bool, ack: str | None}. handled=True means the webhook
    must send the ack (if any) and do nothing else — no AI auto-reply on top
    of compliance or status messages.
    """
    intent = classify_reply(body)
    async with db.pool().acquire() as conn:
        contractor = await conn.fetchrow("SELECT id, name, opted_out FROM contractors WHERE phone = $1", phone)

    if intent == "stop":
        # Compliance beats everything, including for numbers we don't know:
        # a STOP must never be answered by the AI auto-reply.
        if contractor is None:
            return {"handled": True, "ack": None}
        async with db.pool().acquire() as conn:
            await conn.execute("UPDATE contractors SET opted_out = true WHERE id = $1", contractor["id"])
            await conn.execute(
                "UPDATE shift_invites SET status = 'cancelled', last_reply_at = now(), last_reply_body = $2 "
                "WHERE contractor_id = $1 AND status IN ('invited','yes','maybe')",
                contractor["id"], body,
            )
        return {
            "handled": True,
            "ack": "You're opted out of CrewLoop messages and won't receive any more. Reply START to opt back in.",
        }

    if contractor is None:
        return {"handled": False, "ack": None}

    if intent == "start":
        async with db.pool().acquire() as conn:
            await conn.execute("UPDATE contractors SET opted_out = false WHERE id = $1", contractor["id"])
        return {"handled": True, "ack": "You're opted back in to CrewLoop shift messages."}

    async with db.pool().acquire() as conn:
        invite = await conn.fetchrow(
            """
            SELECT si.*, j.role, j.location, j.start_time, j.business_name
            FROM shift_invites si JOIN jobs j ON j.id = si.job_id
            WHERE si.contractor_id = $1 AND si.status IN ('invited','yes','maybe')
            ORDER BY si.created_at DESC LIMIT 1
            """,
            contractor["id"],
        )

    if invite is None:
        return {"handled": False, "ack": None}

    if intent == "yes":
        pinged = invite["ping_48_sent_at"] is not None or invite["ping_4_sent_at"] is not None
        new_status = "confirmed" if pinged else "yes"
        ack = (
            "Confirmed — see you there. Reply STOP anytime to opt out."
            if new_status == "confirmed"
            else "You're in. We'll text the details and a confirmation before the shift. Reply STOP anytime to opt out."
        )
    elif intent == "no":
        new_status = "no"
        ack = "No worries — thanks for the quick reply."
    elif intent == "maybe":
        new_status = "maybe"
        ack = "Got it, we'll check back. Reply YES here as soon as you know."
    else:
        # A question or free text: record it on the invite, let the AI
        # auto-reply (which has the thread context) handle the conversation.
        async with db.pool().acquire() as conn:
            await conn.execute(
                "UPDATE shift_invites SET last_reply_at = now(), last_reply_body = $2 WHERE id = $1",
                invite["id"], body,
            )
        return {"handled": False, "ack": None}

    async with db.pool().acquire() as conn:
        await conn.execute(
            "UPDATE shift_invites SET status = $2, last_reply_at = now(), last_reply_body = $3 WHERE id = $1",
            invite["id"], new_status, body,
        )
    return {"handled": True, "ack": ack}


# ---------------------------------------------------------------------------
# Fill board
# ---------------------------------------------------------------------------

async def board(job_id: UUID) -> dict[str, Any] | None:
    async with db.pool().acquire() as conn:
        job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job_row:
            return None
        invites = await conn.fetch(
            """
            SELECT si.*, c.name, c.phone, c.priority, c.reliability_score, c.opted_out
            FROM shift_invites si JOIN contractors c ON c.id = si.contractor_id
            WHERE si.job_id = $1
            ORDER BY si.batch, c.priority, c.name
            """,
            job_id,
        )

    now = datetime.now(UTC)
    items = []
    counts = {"invited": 0, "yes": 0, "maybe": 0, "no": 0, "confirmed": 0, "cancelled": 0, "at_risk": 0}
    for r in invites:
        d = _row(r)
        d["at_risk"] = is_at_risk(
            status=r["status"],
            ping_48_sent_at=r["ping_48_sent_at"],
            ping_4_sent_at=r["ping_4_sent_at"],
            last_reply_at=r["last_reply_at"],
            now=now,
        )
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if d["at_risk"]:
            counts["at_risk"] += 1
        items.append(d)

    job = _row(job_row)
    filled = counts["yes"] + counts["confirmed"]
    return {
        "job": job,
        "invites": items,
        "counts": {**counts, "needed": job.get("headcount") or 1, "filled": filled},
    }


# ---------------------------------------------------------------------------
# Confirmation pings (T-48h / T-4h)
# ---------------------------------------------------------------------------

async def run_due_pings() -> dict[str, int]:
    """Send due confirmation pings for upcoming shifts. Called by the
    background loop; safe to call repeatedly (each ping sends once)."""
    sql = """
        SELECT si.id AS invite_id, si.ping_48_sent_at, si.ping_4_sent_at,
               j.id AS job_id, j.event_at, j.role, j.location, j.start_time, j.business_name,
               c.phone, c.opted_out
        FROM shift_invites si
        JOIN jobs j ON j.id = si.job_id
        JOIN contractors c ON c.id = si.contractor_id
        WHERE si.status IN ('yes', 'confirmed')
          AND j.event_at IS NOT NULL AND j.event_at > now()
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql)

    sent_48 = sent_4 = 0
    now = datetime.now(UTC)
    for r in rows:
        if r["opted_out"]:
            continue
        hours_until = (r["event_at"] - now).total_seconds() / 3600
        column = None
        horizon = None
        if hours_until <= 4 and r["ping_4_sent_at"] is None:
            column, horizon = "ping_4_sent_at", "4 hours"
        elif hours_until <= 48 and r["ping_48_sent_at"] is None:
            column, horizon = "ping_48_sent_at", "48 hours"
        if column is None:
            continue
        body = ping_message(dict(r), horizon)
        try:
            result = await get_client().send_message(to_number=r["phone"], body=body)
        except Exception:
            logger.exception("confirmation ping failed for %s", r["phone"])
            continue
        # Explicit statements per column — never interpolate identifiers into SQL.
        if column == "ping_4_sent_at":
            mark_sql = "UPDATE shift_invites SET ping_4_sent_at = now() WHERE id = $1"
        else:
            mark_sql = "UPDATE shift_invites SET ping_48_sent_at = now() WHERE id = $1"
        async with db.pool().acquire() as conn:
            await conn.execute(mark_sql, r["invite_id"])
        try:
            await repo.record_message(
                phone=r["phone"], direction="outbound", body=body,
                agentphone_id=result.get("id"), to_number=r["phone"],
            )
        except Exception:
            logger.exception("failed to persist ping SMS")
        if column == "ping_4_sent_at":
            sent_4 += 1
        else:
            sent_48 += 1
    return {"sent_48": sent_48, "sent_4": sent_4}


async def ping_loop() -> None:
    """Background task started from the app lifespan."""
    while True:
        try:
            if db.available() and settings.agentphone_api_key:
                result = await run_due_pings()
                if result["sent_48"] or result["sent_4"]:
                    logger.info("confirmation pings sent: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ping loop iteration failed")
        await asyncio.sleep(PING_LOOP_SECONDS)


# ---------------------------------------------------------------------------
# Voice escalation: the "Call this worker" button
# ---------------------------------------------------------------------------

async def place_escalation_call(job_id: UUID, contractor_id: UUID) -> dict[str, Any]:
    async with db.pool().acquire() as conn:
        job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        c_row = await conn.fetchrow("SELECT * FROM contractors WHERE id = $1", contractor_id)
    if not job_row or not c_row:
        return {"error": "shift or contractor not found"}
    if c_row["opted_out"]:
        return {"error": "contractor has opted out of CrewLoop contact"}
    job = _row(job_row)
    first = (c_row["name"] or "").split()[0] or "there"
    greeting = (
        f"Hi {first}, this is CrewLoop calling for {job.get('business_name') or 'an event'} about the "
        f"{job.get('role', '')} shift {job.get('start_time', '')} at {job.get('location', '')}. "
        "Can you take it?"
    )
    system_prompt = (
        "You are CrewLoop's dispatcher confirming whether the worker can take the "
        f"{job.get('role', '')} shift from {job.get('start_time', '')} to {job.get('end_time', '')} "
        f"for ${float(job.get('pay_amount') or 0):g}. Be brief and human. If they accept, tell them "
        "they'll get a confirmation text. If they decline, thank them and end the call."
    )
    result = await get_client().place_call(
        to_number=c_row["phone"], initial_greeting=greeting, system_prompt=system_prompt
    )
    try:
        await repo.record_call(to_number=c_row["phone"], agentphone_call_id=result.get("id") or result.get("callId"))
    except Exception:
        logger.exception("failed to persist escalation call")
    return {"status": "placed", "call_id": result.get("id") or result.get("callId"), "to": c_row["phone"]}


def _row(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if isinstance(v, UUID):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, Decimal):
            d[k] = float(v)
    return d
