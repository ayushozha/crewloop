"""Fill-a-shift API: the one loop the pilot runs on. All sends are real."""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import shifts

router = APIRouter(prefix="/api/shifts", tags=["shifts"])


class CreateShiftRequest(BaseModel):
    business_name: str = "CrewLoop pilot"
    role: str = Field(..., min_length=1)
    description: str | None = None
    location: str = Field(..., min_length=1)
    start_time: str = Field(..., min_length=1, description="Human-readable, e.g. 'Saturday 6:00 PM'")
    end_time: str = ""
    pay_amount: float = Field(..., ge=0)
    headcount: int = Field(default=1, ge=1, le=200)
    urgency: str = "normal"
    event_at: datetime | None = Field(
        default=None, description="ISO timestamp of the shift start; drives T-48h/T-4h confirmation pings."
    )


class OutreachRequest(BaseModel):
    batch_size: int = Field(default=5, ge=1, le=50)
    match_role: bool = True


@router.post("")
async def create_shift(payload: CreateShiftRequest) -> dict[str, Any]:
    shift = await shifts.create_shift(payload.model_dump())
    return {"shift": shift}


@router.get("")
async def list_shifts(limit: int = 25) -> dict[str, Any]:
    return {"items": await shifts.list_shifts(limit=limit)}


@router.get("/{job_id}/board")
async def get_board(job_id: UUID) -> dict[str, Any]:
    result = await shifts.board(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="shift not found")
    return result


@router.post("/{job_id}/outreach")
async def outreach(job_id: UUID, payload: OutreachRequest = OutreachRequest()) -> dict[str, Any]:
    result = await shifts.start_outreach(job_id, batch_size=payload.batch_size, match_role=payload.match_role)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{job_id}/cascade")
async def cascade(job_id: UUID, payload: OutreachRequest = OutreachRequest(batch_size=3)) -> dict[str, Any]:
    """One-click backfill: invite the next batch down the priority list."""
    result = await shifts.start_outreach(job_id, batch_size=payload.batch_size, match_role=payload.match_role)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{job_id}/call/{contractor_id}")
async def call_worker(job_id: UUID, contractor_id: UUID) -> dict[str, Any]:
    """Voice escalation button: places a real outbound call to this worker."""
    result = await shifts.place_escalation_call(job_id, contractor_id)
    if result.get("error"):
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.post("/pings/run")
async def run_pings_now() -> dict[str, Any]:
    """Manual trigger for the confirmation-ping sweep (also runs every 5 min)."""
    return await shifts.run_due_pings()
