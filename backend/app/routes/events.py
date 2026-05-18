"""Listing surface over the existing `jobs` table.

The dispatch + workflow code uses the term `job`; the chat-side intake flow
uses `event`. They're the same row in `jobs`. This route exists so the
front-end has a clean `/api/events` it can read without learning the older
`/jobs/{id}` shape.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db, supplies


router = APIRouter(prefix="/api/events", tags=["events"])


class CreateEventRequest(BaseModel):
    business_name: str = "Bay Events Co."
    role: str = Field(..., description="Primary role (bartender, server, event_captain, etc.)")
    description: str | None = None
    location: str
    start_time: str
    end_time: str
    pay_amount: float
    urgency: str = "standard"
    required_skills: list[str] = Field(default_factory=list)
    status: str = "drafting"


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if d.get("pay_amount") is not None:
        d["pay_amount"] = float(d["pay_amount"])
    return d


@router.get("")
async def list_events(status: str | None = None, limit: int = 100) -> dict[str, Any]:
    sql = """
        SELECT id, business_name, role, description, location, start_time, end_time,
               pay_amount, urgency, required_skills, status, created_at
        FROM jobs
        WHERE ($1::text IS NULL OR status = $1)
        ORDER BY created_at DESC
        LIMIT $2
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, status, limit)
    return {"items": [_row_to_dict(r) for r in rows], "count": len(rows)}


@router.post("")
async def create_event(payload: CreateEventRequest) -> dict[str, Any]:
    sql = """
        INSERT INTO jobs (business_name, role, description, location, start_time,
                          end_time, pay_amount, urgency, required_skills, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10)
        RETURNING id, business_name, role, description, location, start_time, end_time,
                  pay_amount, urgency, required_skills, status, created_at
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql,
            payload.business_name, payload.role, payload.description, payload.location,
            payload.start_time, payload.end_time, payload.pay_amount, payload.urgency,
            payload.required_skills, payload.status,
        )
    return _row_to_dict(row)


@router.get("/{event_id}")
async def get_event(event_id: str) -> dict[str, Any]:
    sql = "SELECT * FROM jobs WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, event_id)
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Supplies sub-resource (spec §3 steps 9-10).
# ---------------------------------------------------------------------------

async def _event_or_404(event_id: str) -> dict[str, Any]:
    sql = "SELECT * FROM jobs WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, event_id)
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    return _row_to_dict(row)


@router.post("/{event_id}/supplies/recommend")
async def recommend_event_supplies(event_id: str, regenerate: bool = False) -> dict[str, Any]:
    """Return 3-5 recommended supplies for this event. Persists them as
    'recommended' (replacing any prior recommendations) so the chat / panel
    can show the same set on reload. Pass `regenerate=true` to force a fresh
    Gemini call even when prior recommendations exist."""
    event = await _event_or_404(event_id)
    existing = await supplies.list_supplies(UUID(event_id))
    if existing and not regenerate:
        return {"event": event, "items": existing, "summary": supplies.supplies_summary(existing)}
    drafts = await supplies.recommend_supplies(event)
    saved = await supplies.persist_supplies(UUID(event_id), drafts)
    return {"event": event, "items": saved, "summary": supplies.supplies_summary(saved)}


@router.get("/{event_id}/supplies")
async def list_event_supplies(event_id: str) -> dict[str, Any]:
    event = await _event_or_404(event_id)
    items = await supplies.list_supplies(UUID(event_id))
    return {"event": event, "items": items, "summary": supplies.supplies_summary(items)}


@router.post("/{event_id}/supplies/approve")
async def approve_event_supplies(event_id: str) -> dict[str, Any]:
    """Owner approves the recommended supply list. Flips every 'recommended'
    row to 'approved' and attaches a Browser Use-style vendor evidence
    object (URL, ETA window, one-line note) so the UI can render proof."""
    event = await _event_or_404(event_id)
    items = await supplies.simulate_vendor_checkout(UUID(event_id))
    if not items:
        raise HTTPException(status_code=409, detail="no supplies to approve — recommend first")
    return {"event": event, "items": items, "summary": supplies.supplies_summary(items)}
