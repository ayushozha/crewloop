"""Listing surface over the existing `jobs` table.

The dispatch + workflow code uses the term `job`; the chat-side intake flow
uses `event`. They're the same row in `jobs`. This route exists so the
front-end has a clean `/api/events` it can read without learning the older
`/jobs/{id}` shape.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db


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
