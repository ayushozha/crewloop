from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agentphone import AgentPhoneError, get_client


router = APIRouter(prefix="/api/sms", tags=["sms"])


class SendSmsRequest(BaseModel):
    to: str = Field(..., description="Recipient phone in E.164, e.g. +14155551234")
    body: str = Field(..., min_length=1, max_length=1600)


@router.post("/send")
async def send_sms(payload: SendSmsRequest) -> dict:
    try:
        result = await get_client().send_message(to_number=payload.to, body=payload.body)
    except AgentPhoneError as e:
        raise HTTPException(status_code=502, detail={"agentphone_status": e.status, "body": e.body})
    return result
