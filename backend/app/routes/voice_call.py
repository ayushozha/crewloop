"""Voice call demo routes — Ayush calls a contractor with ElevenLabs voice."""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db, voice_call


router = APIRouter(prefix="/api/voice-call", tags=["voice-call"])


class DemoCallRequest(BaseModel):
    job_id: str | None = Field(default=None, description="Job/event UUID to call about.")
    contractor_id: str | None = Field(default=None, description="Contractor UUID to call.")
    contractor_name: str | None = Field(default=None, description="Override the contractor name.")


@router.post("/demo")
async def trigger_demo(payload: DemoCallRequest = DemoCallRequest()) -> dict[str, Any]:
    """Run a full scripted shift-offer conversation. Generates ElevenLabs
    audio for every Ayush line and stores it as static MP3s. Returns the
    call id + transcript with audio paths the frontend can play."""
    job_id = UUID(payload.job_id) if payload.job_id else None
    contractor_id = UUID(payload.contractor_id) if payload.contractor_id else None

    job: dict[str, Any] | None = None
    contractor: dict[str, Any] | None = None
    async with db.pool().acquire() as conn:
        if job_id is None:
            job_row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE role = 'bartender' AND start_time LIKE 'Saturday%' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if not job_row:
                job_row = await conn.fetchrow("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1")
            if job_row:
                job_id = job_row["id"]
                job = {k: (str(v) if k == "id" else v) for k, v in dict(job_row).items()}
                if job.get("pay_amount") is not None:
                    job["pay_amount"] = float(job["pay_amount"])
        else:
            job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
            if job_row:
                job = {k: (str(v) if k == "id" else v) for k, v in dict(job_row).items()}
                if job.get("pay_amount") is not None:
                    job["pay_amount"] = float(job["pay_amount"])

        if contractor_id is None:
            c_row = await conn.fetchrow(
                """
                SELECT c.* FROM contractors c
                JOIN contractor_skills s ON s.contractor_id = c.id
                WHERE s.skill = 'bartender'
                ORDER BY c.reliability_score DESC LIMIT 1
                """
            )
            if c_row:
                contractor_id = c_row["id"]
                contractor = dict(c_row)
        else:
            c_row = await conn.fetchrow("SELECT * FROM contractors WHERE id = $1", contractor_id)
            if c_row:
                contractor = dict(c_row)

    if not job:
        raise HTTPException(status_code=409, detail="no job available to call about")
    contractor_name = (
        payload.contractor_name
        or (contractor["name"] if contractor else None)
        or "Emma"
    )

    result = await voice_call.run_demo_call(
        job=job,
        contractor_name=contractor_name,
        contractor_id=contractor_id,
    )
    return result


@router.get("/{call_id}")
async def get_voice_call(call_id: str) -> dict[str, Any]:
    data = await voice_call.list_call(call_id)
    if not data:
        raise HTTPException(status_code=404, detail="voice call not found")
    return data


@router.get("")
async def list_voice_calls(limit: int = 20) -> dict[str, Any]:
    return {"items": await voice_call.list_calls(limit=limit)}
