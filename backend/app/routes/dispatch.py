from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import repo
from ..dispatch_room import build_dispatch_payload


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
router = APIRouter(tags=["dispatch"])


@router.get("/dispatch/{job_id}", include_in_schema=False)
async def dispatch_room_page(job_id: UUID) -> FileResponse:
    return FileResponse(STATIC_DIR / "dispatch-room.html")


@router.get("/api/dispatch/{job_id}")
async def get_dispatch_room(job_id: UUID) -> dict[str, Any]:
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    sources = await repo.list_browser_sources_for_job(job_id)
    return build_dispatch_payload(
        job,
        sources,
        events=await repo.list_events(job_id),
        outreach=await repo.list_outreach(job_id),
        schedules=await repo.list_schedules(job_id),
        payment=await repo.get_payment(job_id),
        proofs=await repo.list_proofs(job_id),
        notifications=await repo.list_notifications(job_id),
    )
