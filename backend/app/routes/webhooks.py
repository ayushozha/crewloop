import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .. import repo
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
    data = payload.get("data", {}) or {}

    if event == "agent.message" and channel == "sms":
        from_n = data.get("from") or ""
        to_n = data.get("to") or ""
        message = data.get("message") or ""
        logger.info("inbound SMS from %s to %s: %s", from_n, to_n, message)
        try:
            await repo.record_message(
                phone=from_n,
                direction="inbound",
                body=message,
                agentphone_id=data.get("id") or data.get("messageId"),
                from_number=from_n,
                to_number=to_n,
            )
        except Exception:
            logger.exception("failed to persist inbound SMS")
        return {}

    if event == "agent.message" and channel == "voice":
        # Hosted-mode agents don't use this webhook for voice turns. Kept as a fallback.
        transcript = data.get("transcript", "")
        logger.info("voice turn: %s", transcript)
        return {"text": "One moment."}

    if event == "agent.call_ended":
        call_id = data.get("callId") or data.get("id") or ""
        logger.info(
            "call_ended id=%s duration=%ss reason=%s",
            call_id, data.get("durationSeconds"), data.get("disconnectionReason"),
        )
        try:
            await repo.finalize_call(
                agentphone_call_id=call_id,
                duration_seconds=data.get("durationSeconds"),
                disconnection_reason=data.get("disconnectionReason"),
                summary=data.get("summary"),
                user_sentiment=data.get("userSentiment"),
                transcript=data.get("transcript"),
            )
        except Exception:
            logger.exception("failed to persist call_ended")
        return {}

    logger.warning("unhandled webhook event=%s channel=%s", event, channel)
    return {}
