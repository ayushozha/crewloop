"""Spec §6 fulfillment helpers: event plan inference, schedule, client
invoice, worker payment holds, proofs.

These functions back the §10 endpoints exposed in routes/jobs.py:

  POST /jobs/{id}/infer-event-plan   → infer_event_plan / persist_event_plan
  POST /jobs/{id}/schedule            → create_schedule
  POST /jobs/{id}/invoice             → generate_invoice
  POST /jobs/{id}/send-invoice        → send_invoice
  POST /jobs/{id}/payment-holds       → create_payment_holds
  POST /jobs/{id}/release-payments    → release_payments
  POST /jobs/{id}/proofs              → record_proof

Sponge and Stripe MPP are demo-controlled per the spec — we generate a
plausible ref id and call it done. AgentMail similarly: we record a
fake message id so the UI has something to render.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from . import ai, db
from .config import settings


logger = logging.getLogger("crewloop.fulfillment")


# ---------------------------------------------------------------------------
# Event plan (spec §6.2)
# ---------------------------------------------------------------------------

EVENT_PLAN_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "responsibilities": {"type": "STRING"},
        "roles": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "role": {"type": "STRING"},
                    "count": {"type": "INTEGER"},
                    "hours": {"type": "NUMBER"},
                    "hourly_rate": {"type": "NUMBER"},
                    "notes": {"type": "STRING"},
                },
                "required": ["role", "count", "hours", "hourly_rate"],
            },
        },
    },
    "required": ["roles"],
}

EVENT_PLAN_PROMPT = """You are CrewLoop's event-planning agent.

Given an event brief, return a tight crew plan. Aim for a TOTAL CREW SIZE
that fits the guest count (a useful rule of thumb: 1 staff per 8-10 guests
for a sit-down dinner, 1 per 15 for cocktail-only).

Rules:
- Pick from these roles: bartender, server, event_captain, line_cook,
  prep_cook, setup_crew, cleanup_crew, security, host, runner.
- Include 1 event_captain whenever total crew >= 4.
- For corporate dinners or weddings, include at least 1 setup_crew and
  1 cleanup_crew.
- hourly_rate is a realistic SF event rate by role (bartender 28-35,
  server 22-28, event_captain 35-45, line_cook 28-35, setup/cleanup 20-25,
  security 28-32).
- hours = event window length, rounded up to a half hour, plus 30 min
  setup for setup_crew or 30 min teardown for cleanup_crew.
- One concise top-level responsibilities paragraph (3-5 sentences).
- Never invent roles outside the list. Never go above 14 total crew.
"""


async def infer_event_plan_for_job(job: dict[str, Any]) -> dict[str, Any]:
    """Returns the plan body (roles + responsibilities + estimated cost)
    but does NOT persist. Caller persists with persist_event_plan()."""
    brief = _job_brief(job)
    raw = await ai._call_gemini_json(
        model=settings.gemini_model_pro,
        system_prompt=EVENT_PLAN_PROMPT,
        contents=[{"role": "user", "parts": [{"text": brief}]}],
        response_schema=EVENT_PLAN_SCHEMA,
        max_output_tokens=1600,
        temperature=0.4,
    )
    if not raw:
        return _fallback_event_plan(job)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _fallback_event_plan(job)
    roles = [r for r in (parsed.get("roles") or []) if isinstance(r, dict)]
    if not roles:
        return _fallback_event_plan(job)
    return {
        "responsibilities": parsed.get("responsibilities") or "",
        "roles": roles,
        "required_count_by_role": {r["role"]: int(r.get("count") or 0) for r in roles},
        "total_crew": sum(int(r.get("count") or 0) for r in roles),
        "estimated_labor_cost": round(
            sum((r.get("count") or 0) * (r.get("hours") or 0) * (r.get("hourly_rate") or 0) for r in roles), 2
        ),
    }


def _fallback_event_plan(job: dict[str, Any]) -> dict[str, Any]:
    # Deterministic 10-person crew from the demo script.
    roles = [
        {"role": "bartender",     "count": 2, "hours": 5, "hourly_rate": 32},
        {"role": "server",        "count": 4, "hours": 5, "hourly_rate": 26},
        {"role": "setup_crew",    "count": 2, "hours": 2.5, "hourly_rate": 22},
        {"role": "event_captain", "count": 1, "hours": 5.5, "hourly_rate": 40},
        {"role": "cleanup_crew",  "count": 1, "hours": 2.5, "hourly_rate": 22},
    ]
    cost = round(sum(r["count"] * r["hours"] * r["hourly_rate"] for r in roles), 2)
    return {
        "responsibilities": (
            "Run the event end-to-end: setup, cocktail reception service, "
            "plated dinner service, and teardown. Event captain owns the floor."
        ),
        "roles": roles,
        "required_count_by_role": {r["role"]: r["count"] for r in roles},
        "total_crew": sum(r["count"] for r in roles),
        "estimated_labor_cost": cost,
    }


def _job_brief(job: dict[str, Any]) -> str:
    pieces = [
        f"Business: {job.get('business_name')}",
        f"Role label: {job.get('role')}",
        f"Description: {job.get('description') or '—'}",
        f"Window: {job.get('start_time')} → {job.get('end_time')}",
        f"Location: {job.get('location')}",
        f"Urgency: {job.get('urgency')}",
        f"Required skills: {', '.join(job.get('required_skills') or [])}",
    ]
    return "\n".join(pieces)


async def persist_event_plan(job_id: UUID, plan: dict[str, Any]) -> dict[str, Any]:
    """Replace the draft event_plan for this job with the new one."""
    delete_sql = "DELETE FROM event_plans WHERE job_id = $1 AND approval_status = 'draft'"
    insert_sql = """
        INSERT INTO event_plans
          (job_id, roles, required_count_by_role, responsibilities,
           estimated_labor_cost, total_crew, approval_status)
        VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6, 'draft')
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(delete_sql, job_id)
            row = await conn.fetchrow(
                insert_sql,
                job_id,
                json.dumps(plan["roles"]),
                json.dumps(plan["required_count_by_role"]),
                plan.get("responsibilities") or "",
                float(plan["estimated_labor_cost"]),
                int(plan["total_crew"]),
            )
    return _decode(row)


async def list_event_plans(job_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT * FROM event_plans WHERE job_id = $1 ORDER BY created_at DESC"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_decode(r) for r in rows]


async def approve_event_plan(plan_id: UUID) -> dict[str, Any] | None:
    sql = "UPDATE event_plans SET approval_status='approved', approved_at=now() WHERE id=$1 RETURNING *"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, plan_id)
    return _decode(row) if row else None


# ---------------------------------------------------------------------------
# Schedule (spec §6.5)
# ---------------------------------------------------------------------------

async def create_schedule(
    job_id: UUID,
    job: dict[str, Any],
    assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """assignments = [{contractor_id?, contractor_name, role, start_time?,
    end_time?, status?}, …]. Replaces any existing schedule for this job."""
    delete_sql = "DELETE FROM schedules WHERE job_id = $1"
    insert_sql = """
        INSERT INTO schedules
          (job_id, contractor_id, contractor_name, role, start_time, end_time, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
    """
    out: list[dict[str, Any]] = []
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(delete_sql, job_id)
            for a in assignments:
                cid = a.get("contractor_id")
                row = await conn.fetchrow(
                    insert_sql,
                    job_id,
                    UUID(cid) if isinstance(cid, str) else cid,
                    a.get("contractor_name"),
                    a.get("role") or job.get("role"),
                    a.get("start_time") or job.get("start_time"),
                    a.get("end_time") or job.get("end_time"),
                    a.get("status") or "scheduled",
                )
                out.append(_decode(row))
    return out


async def list_schedule(job_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT * FROM schedules WHERE job_id = $1 ORDER BY created_at"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_decode(r) for r in rows]


# ---------------------------------------------------------------------------
# Client invoice (spec §6.6)
# ---------------------------------------------------------------------------

async def generate_invoice(
    job_id: UUID,
    job: dict[str, Any],
    *,
    client_email: str | None = None,
    service_fee_rate: float = 0.10,
    deposit_rate: float = 0.50,
) -> dict[str, Any]:
    """Compute labor + supplies + fee from the existing event_plan and
    event_supplies rows for this job, persist as draft, return the row."""
    # Labor from approved event plan (fall back to crew × pay if no plan)
    plans = await list_event_plans(job_id)
    approved = next((p for p in plans if p["approval_status"] == "approved"), plans[0] if plans else None)
    labor = float(approved["estimated_labor_cost"]) if approved else float(job.get("pay_amount") or 0) * 5
    # Supplies from event_supplies
    sup_sql = "SELECT COALESCE(SUM(total_price), 0) AS s FROM event_supplies WHERE event_id = $1"
    async with db.pool().acquire() as conn:
        sup_row = await conn.fetchrow(sup_sql, job_id)
    supplies_amount = float(sup_row["s"] or 0)
    fee = round((labor + supplies_amount) * service_fee_rate, 2)
    total = round(labor + supplies_amount + fee, 2)
    deposit = round(total * deposit_rate, 2)

    delete_sql = "DELETE FROM client_invoices WHERE job_id = $1 AND status = 'draft'"
    insert_sql = """
        INSERT INTO client_invoices
          (job_id, client_email, labor_amount, supplies_amount, service_fee,
           deposit_amount, total_amount, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft')
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(delete_sql, job_id)
            row = await conn.fetchrow(
                insert_sql, job_id, client_email or "client.team@bayevents.co",
                round(labor, 2), round(supplies_amount, 2), fee, deposit, total,
            )
    return _decode(row)


async def send_invoice(job_id: UUID) -> dict[str, Any] | None:
    """Flip the latest draft invoice to 'sent' and attach a fake AgentMail
    message_id. The real AgentMail send is spec-marked demo-controlled."""
    sql_find = """
        SELECT * FROM client_invoices
        WHERE job_id = $1 AND status = 'draft'
        ORDER BY created_at DESC LIMIT 1
    """
    update_sql = """
        UPDATE client_invoices SET
          status = 'sent',
          agentmail_id = $2,
          provider_state = $3::jsonb,
          sent_at = now()
        WHERE id = $1
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        existing = await conn.fetchrow(sql_find, job_id)
        if not existing:
            return None
        msg_id = f"am_{secrets.token_hex(10)}"
        provider = json.dumps({
            "provider": "AgentMail",
            "inbox": settings.agentmail_inbox_name,
            "subject": f"Invoice · {existing['client_email']}",
            "status": "delivered",
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        })
        row = await conn.fetchrow(update_sql, existing["id"], msg_id, provider)
    return _decode(row)


async def list_invoices(job_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT * FROM client_invoices WHERE job_id = $1 ORDER BY created_at DESC"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_decode(r) for r in rows]


# ---------------------------------------------------------------------------
# Worker payment holds (spec §6.8)
# ---------------------------------------------------------------------------

DEFAULT_RELEASE_CONDITIONS = [
    {"label": "Accepted shift",   "complete": True},
    {"label": "Checked in",       "complete": False},
    {"label": "Proof submitted",  "complete": False},
    {"label": "Owner approved",   "complete": False},
]


async def create_payment_holds(job_id: UUID, job: dict[str, Any]) -> list[dict[str, Any]]:
    """One Sponge wallet hold per scheduled contractor for this job. If no
    schedule exists yet we infer from the event_plan (one hold per role-slot).
    Replaces any existing 'held' holds for the job."""
    schedule = await list_schedule(job_id)
    plans = await list_event_plans(job_id)
    approved = next((p for p in plans if p["approval_status"] == "approved"), plans[0] if plans else None)

    holds_to_create: list[dict[str, Any]] = []
    if schedule:
        per_role_rate = _per_role_rate(approved)
        for s in schedule:
            rate = per_role_rate.get(s["role"], float(job.get("pay_amount") or 0))
            holds_to_create.append({
                "contractor_id": s.get("contractor_id"),
                "contractor_name": s.get("contractor_name") or "Unassigned",
                "schedule_id": s["id"],
                "role": s["role"],
                "amount": round(rate, 2),
            })
    elif approved:
        # Pre-schedule: one hold per role-slot.
        for r in approved["roles"]:
            for _ in range(int(r.get("count") or 0)):
                holds_to_create.append({
                    "contractor_id": None,
                    "contractor_name": None,
                    "schedule_id": None,
                    "role": r.get("role"),
                    "amount": round(float(r.get("hours") or 0) * float(r.get("hourly_rate") or 0), 2),
                })
    else:
        # Last fallback: a single hold for the headline pay.
        holds_to_create.append({
            "contractor_id": None,
            "contractor_name": None,
            "schedule_id": None,
            "role": job.get("role"),
            "amount": float(job.get("pay_amount") or 0),
        })

    delete_sql = "DELETE FROM worker_payments WHERE job_id = $1 AND status IN ('held', 'pending')"
    insert_sql = """
        INSERT INTO worker_payments
          (job_id, contractor_id, contractor_name, schedule_id, amount,
           status, release_conditions, provider_ref, held_at)
        VALUES ($1, $2, $3, $4, $5, 'held', $6::jsonb, $7, now())
        RETURNING *
    """
    out: list[dict[str, Any]] = []
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(delete_sql, job_id)
            for h in holds_to_create:
                cid = h.get("contractor_id")
                sid = h.get("schedule_id")
                row = await conn.fetchrow(
                    insert_sql, job_id,
                    UUID(cid) if isinstance(cid, str) else cid,
                    h.get("contractor_name"),
                    UUID(sid) if isinstance(sid, str) else sid,
                    h["amount"],
                    json.dumps(DEFAULT_RELEASE_CONDITIONS),
                    f"spg_{secrets.token_hex(8)}",
                )
                out.append(_decode(row))
    return out


def _per_role_rate(plan: dict[str, Any] | None) -> dict[str, float]:
    if not plan:
        return {}
    out: dict[str, float] = {}
    for r in plan.get("roles") or []:
        rate = float(r.get("hours") or 0) * float(r.get("hourly_rate") or 0)
        out[r.get("role")] = rate
    return out


async def list_worker_payments(job_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT * FROM worker_payments WHERE job_id = $1 ORDER BY created_at"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_decode(r) for r in rows]


async def release_payments(job_id: UUID) -> list[dict[str, Any]]:
    """Flip every 'held' payment to 'released' and stamp a receipt url."""
    sql = """
        UPDATE worker_payments SET
          status = 'released',
          released_at = now(),
          receipt_url = COALESCE(receipt_url, $2),
          release_conditions = $3::jsonb
        WHERE job_id = $1 AND status = 'held'
        RETURNING *
    """
    released_conditions = [{"label": c["label"], "complete": True} for c in DEFAULT_RELEASE_CONDITIONS]
    receipt_stub = f"https://crewloop-api.ayushojha.com/receipts/wp_{secrets.token_hex(6)}.pdf"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id, receipt_stub, json.dumps(released_conditions))
    return [_decode(r) for r in rows]


# ---------------------------------------------------------------------------
# Proofs (spec §6.7)
# ---------------------------------------------------------------------------

async def record_proof(
    job_id: UUID,
    *,
    proof_type: str,
    detail: str | None,
    contractor_id: UUID | str | None = None,
    content_url: str | None = None,
    status: str = "received",
) -> dict[str, Any]:
    sql = """
        INSERT INTO proofs
          (job_id, contractor_id, type, content_url, detail, status, received_at)
        VALUES ($1, $2, $3, $4, $5, $6, CASE WHEN $6 = 'received' THEN now() END)
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql, job_id,
            UUID(contractor_id) if isinstance(contractor_id, str) else contractor_id,
            proof_type, content_url, detail, status,
        )
    return _decode(row)


async def list_proofs(job_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT * FROM proofs WHERE job_id = $1 ORDER BY created_at"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, job_id)
    return [_decode(r) for r in rows]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _decode(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    for k in ("estimated_labor_cost", "labor_amount", "supplies_amount",
              "service_fee", "deposit_amount", "total_amount", "amount"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    for k in ("id", "job_id", "contractor_id", "schedule_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("roles", "required_count_by_role", "release_conditions", "provider_state"):
        if isinstance(d.get(k), str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d
