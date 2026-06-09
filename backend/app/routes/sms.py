import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db, repo
from ..agentphone import AgentPhoneError, get_client

logger = logging.getLogger("crewloop.sms")
router = APIRouter(prefix="/api/sms", tags=["sms"])


class SendSmsRequest(BaseModel):
    to: str = Field(..., description="Recipient phone in E.164, e.g. +14155551234")
    body: str = Field(..., min_length=1, max_length=1600)


@router.post("/send")
async def send_sms(payload: SendSmsRequest) -> dict:
    # TCPA: a STOP must block every send path, including manual ones.
    try:
        async with db.pool().acquire() as conn:
            row = await conn.fetchrow("SELECT opted_out FROM contractors WHERE phone = $1", payload.to)
        if row and row["opted_out"]:
            raise HTTPException(status_code=403, detail="recipient has opted out of CrewLoop SMS (replied STOP)")
    except HTTPException:
        raise
    except Exception:
        logger.exception("opt-out check failed; refusing to send without it")
        raise HTTPException(status_code=503, detail="could not verify opt-out status; send refused")

    try:
        result = await get_client().send_message(to_number=payload.to, body=payload.body)
    except AgentPhoneError as e:
        raise HTTPException(status_code=502, detail={"agentphone_status": e.status, "body": e.body})

    try:
        await repo.record_message(
            phone=payload.to,
            direction="outbound",
            body=payload.body,
            agentphone_id=result.get("id"),
            from_number=result.get("from_number"),
            to_number=result.get("to_number") or payload.to,
        )
    except Exception:
        logger.exception("failed to persist outbound SMS")

    return result
