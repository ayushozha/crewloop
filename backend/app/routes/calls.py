import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import repo
from ..agentphone import AgentPhoneError, get_client


logger = logging.getLogger("crewloop.calls")
router = APIRouter(prefix="/api/calls", tags=["calls"])


class PlaceCallRequest(BaseModel):
    to: str = Field(..., description="Recipient phone in E.164")
    initial_greeting: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=4000)


@router.post("/place")
async def place_call(payload: PlaceCallRequest) -> dict:
    try:
        result = await get_client().place_call(
            to_number=payload.to,
            initial_greeting=payload.initial_greeting,
            system_prompt=payload.system_prompt,
        )
    except AgentPhoneError as e:
        raise HTTPException(status_code=502, detail={"agentphone_status": e.status, "body": e.body})

    try:
        await repo.record_call(
            to_number=payload.to,
            agentphone_call_id=result.get("id") or result.get("callId"),
        )
    except Exception:
        logger.exception("failed to persist placed call")

    return result
