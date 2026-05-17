import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .. import ai, repo
from ..agentphone import get_client
from ..config import settings
from ..signature import verify_webhook
from ..workflow import handle_contractor_message


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
        return await _handle_sms(data)

    if event == "agent.message" and channel == "voice":
        return await _handle_voice_turn(data)

    if event == "agent.call_ended":
        return await _handle_call_ended(data)

    logger.warning("unhandled webhook event=%s channel=%s", event, channel)
    return {}


@router.post("/agentmail")
async def agentmail_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    event = payload.get("event") or payload.get("type") or "agentmail.event"
    data = payload.get("data") or payload
    job_id = data.get("job_id") or data.get("metadata", {}).get("job_id")
    if job_id:
        await repo.create_event(
            job_id=job_id,
            type="email_sent" if "sent" in event else "email_event",
            content=f"AgentMail webhook received: {event}",
            metadata={"payload": payload},
        )
    return {"ok": True}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    event = payload.get("type") or "stripe.event"
    data = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
    job_id = data.get("metadata", {}).get("job_id") or payload.get("job_id")
    if job_id:
        await repo.create_event(
            job_id=job_id,
            type="stripe_event",
            content=f"Stripe webhook received: {event}",
            metadata={"payload": payload},
        )
    return {"ok": True}


@router.post("/sponge")
async def sponge_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    event = payload.get("event") or payload.get("type") or "sponge.event"
    job_id = payload.get("job_id") or payload.get("metadata", {}).get("job_id")
    if job_id:
        await repo.create_event(
            job_id=job_id,
            type="sponge_event",
            content=f"Sponge webhook received: {event}",
            metadata={"payload": payload},
        )
    return {"ok": True}


async def _handle_sms(data: dict) -> dict[str, Any]:
    direction = data.get("direction") or "inbound"
    msg_from = data.get("from") or ""
    msg_to = data.get("to") or ""
    body = data.get("message") or data.get("body") or ""
    # The contractor's phone is the OTHER party in the thread, not our agent number.
    contractor_phone = msg_from if direction == "inbound" else msg_to
    agentphone_id = data.get("id") or data.get("messageId")

    logger.info(
        "SMS %s from=%s to=%s body=%r",
        direction, msg_from, msg_to, body[:120],
    )

    new_row_id = None
    try:
        new_row_id = await repo.record_message(
            phone=contractor_phone,
            direction=direction,
            body=body,
            agentphone_id=agentphone_id,
            from_number=msg_from,
            to_number=msg_to,
        )
    except Exception:
        logger.exception("failed to persist SMS")

    # Only auto-reply on a fresh inbound (skips webhook retries and our own outbound echoes).
    if direction == "inbound" and new_row_id is not None and contractor_phone:
        try:
            workflow_result = await handle_contractor_message(contractor_phone, body)
        except Exception:
            logger.exception("failed to apply contractor SMS to workflow")
            workflow_result = None
        if workflow_result and workflow_result.get("intent") in {"accept", "decline", "check_in"}:
            return {}

        try:
            reply = await ai.generate_sms_reply(contractor_phone)
        except Exception:
            logger.exception("failed to generate SMS auto-reply")
            reply = None
        if reply:
            try:
                result = await get_client().send_message(to_number=contractor_phone, body=reply)
            except Exception:
                logger.exception("failed to send SMS auto-reply")
                result = None
            if result:
                try:
                    await repo.record_message(
                        phone=contractor_phone,
                        direction="outbound",
                        body=reply,
                        agentphone_id=result.get("id"),
                        from_number=result.get("from_number"),
                        to_number=result.get("to_number") or contractor_phone,
                    )
                except Exception:
                    logger.exception("failed to persist outbound SMS auto-reply")

    return {}


async def _handle_voice_turn(data: dict) -> dict[str, Any]:
    """One user utterance during a live call. Response is what the agent speaks next."""
    transcript_field = data.get("transcript")
    turns: list[dict] = []
    if isinstance(transcript_field, list):
        # Full multi-turn transcript shape per the docs.
        turns = [{"role": t.get("role"), "text": t.get("content") or t.get("text") or ""}
                 for t in transcript_field]
    elif isinstance(transcript_field, str):
        # Single-utterance shape: treat as the latest user turn.
        turns = [{"role": "user", "text": transcript_field}]

    reply = None
    try:
        reply = await ai.generate_voice_reply(turns)
    except Exception:
        logger.exception("failed to generate voice reply")

    return {"text": reply or "One moment."}


async def _handle_call_ended(data: dict) -> dict[str, Any]:
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
