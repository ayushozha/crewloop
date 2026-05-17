import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from ..config import settings
from ..signature import verify_webhook


logger = logging.getLogger("crewloop.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/agentphone")
async def agentphone_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    x_webhook_timestamp: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    secret = settings.agentphone_webhook_secret
    if secret and not verify_webhook(secret, body, x_webhook_signature):
        raise HTTPException(status_code=401, detail="bad webhook signature")

    payload = await request.json()
    event = payload.get("event")
    channel = payload.get("channel")
    data = payload.get("data", {})

    if event == "agent.message" and channel == "sms":
        logger.info(
            "inbound SMS from %s to %s: %s",
            data.get("from"), data.get("to"), data.get("message"),
        )
        # Contractor reply parsing + dispatch state update will hang off here.
        return {}

    if event == "agent.message" and channel == "voice":
        # Voice-turn webhook: only fires for voiceMode="webhook" agents.
        # Our agent uses hosted mode, so this is a no-op fallback.
        transcript = data.get("transcript", "")
        logger.info("voice turn: %s", transcript)
        return {"text": "One moment."}

    if event == "agent.call_ended":
        logger.info(
            "call_ended id=%s duration=%ss reason=%s",
            data.get("callId"), data.get("durationSeconds"), data.get("disconnectionReason"),
        )
        return {}

    logger.warning("unhandled webhook event=%s channel=%s", event, channel)
    return {}
