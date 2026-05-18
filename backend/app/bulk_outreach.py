"""Bulk outreach demo flow for the owner chat.

This is intentionally narrow: one live call target, three live text attempts,
then deterministic simulated replies so the demo can finish with a full roster.
"""
from __future__ import annotations

import asyncio
import copy
from typing import Any

from . import repo
from .agentphone import get_client
from .config import settings
from .sponsors import place_agentphone_call


_EXECUTED_RESULT: dict[str, Any] | None = None


LIVE_TEXT_TARGETS = [
    {
        "id": "emma-carter",
        "name": "Emma Carter",
        "role": "Event lead",
        "phone": "+16692209008",
        "channel": "iMessage + AgentPhone call",
        "body": (
            "CrewLoop for Bay Events: corporate dinner this Saturday in SoMa, "
            "6-11 PM. Role: event lead. Pay: $175. Reply YES to confirm."
        ),
        "response": "YES - confirmed for event lead.",
        "call": True,
    },
    {
        "id": "madison-reed",
        "name": "Madison Reed",
        "role": "Bartender",
        "phone": "+13142990513",
        "channel": "iMessage",
        "body": (
            "CrewLoop for Bay Events: corporate dinner this Saturday in SoMa, "
            "6-11 PM. Role: bartender. Pay: $175. Reply YES to confirm."
        ),
        "response": "YES - confirmed for bartender.",
        "call": False,
    },
    {
        "id": "ashley-brooks",
        "name": "Ashley Brooks",
        "role": "Server",
        "phone": "+19518019702",
        "channel": "iMessage",
        "body": (
            "CrewLoop for Bay Events: corporate dinner this Saturday in SoMa, "
            "6-11 PM. Role: server. Pay: $125. Reply YES to confirm."
        ),
        "response": "YES - confirmed for server.",
        "call": False,
    },
]


SIMULATED_REPLIES = [
    ("Olivia Parker", "Bartender", "confirmed", "YES - can cover bar two."),
    ("Claire Walsh", "Server", "confirmed", "Confirmed for service."),
    ("Harper Lane", "Server", "confirmed", "Yes, available 6-11 PM."),
    ("Brooke Miller", "Server", "confirmed", "Confirmed."),
    ("Luis Romero", "Setup crew", "confirmed", "Can handle load-in and setup."),
    ("Noah Bennett", "Setup crew", "declined", "Sorry, I am booked."),
    ("Natalie Cole", "Cleanup lead", "confirmed", "Confirmed for cleanup lead."),
    ("Taylor Adams", "Setup crew backup", "backup_confirmed", "Backup accepted and filled setup crew."),
]


def is_shortlist_request(text: str) -> bool:
    lower = text.lower()
    return "shortlist" in lower and ("crew" in lower or "contractor" in lower or "event" in lower)


def is_bulk_outreach_start(text: str) -> bool:
    lower = text.lower()
    return (
        ("start" in lower or "send" in lower or "run" in lower)
        and "outreach" in lower
    ) or "text and call the shortlist" in lower


def build_bulk_outreach_plan() -> dict[str, Any]:
    rows = []
    for target in LIVE_TEXT_TARGETS:
        rows.append(
            {
                "name": target["name"],
                "role": target["role"],
                "channel": target["channel"],
                "phone_last4": _last4(target["phone"]),
                "status": "ready",
                "response": "Waiting to contact.",
                "live": True,
                "delivery_status": "ready",
            }
        )
    for name, role, _status, response in SIMULATED_REPLIES:
        rows.append(
            {
                "name": name,
                "role": role,
                "channel": "Simulated reply",
                "phone_last4": "",
                "status": "queued",
                "response": response,
                "live": False,
                "delivery_status": "simulated",
            }
        )

    return {
        "title": "Bulk outreach shortlist",
        "tag": "3 live texts + 1 live call",
        "status": "ready",
        "summary": (
            "Ready to contact 3 live contractors, call the event lead, and simulate "
            "the remaining replies so the roster can close inside the demo."
        ),
        "counts": {
            "needed": 10,
            "filled": 0,
            "live_texts": 3,
            "live_calls": 1,
            "simulated_replies": 8,
            "declined": 0,
        },
        "rows": rows,
        "evidence": [
            "Uses iMessage for the three live text attempts.",
            "Uses AgentPhone for the live event-lead call.",
            "Simulates other contractor replies to keep the demo under 2 minutes.",
        ],
    }


async def execute_bulk_outreach(*, send_real: bool = True) -> dict[str, Any]:
    global _EXECUTED_RESULT
    if _EXECUTED_RESULT is not None:
        result = copy.deepcopy(_EXECUTED_RESULT)
        result["tag"] = "already sent"
        result["summary"] = (
            "Bulk outreach already ran in this server session. Showing the finalized roster "
            "without sending duplicate calls or messages."
        )
        return result

    rows: list[dict[str, Any]] = []
    evidence: list[str] = [
        f"Voice intelligence: Google DeepMind {settings.gemini_model_pro} via AgentPhone webhook.",
    ]
    voice_config = await _configure_google_deepmind_voice(send_real=send_real)
    evidence.append(f"AgentPhone voice mode: {voice_config['status']}.")

    for index, target in enumerate(LIVE_TEXT_TARGETS, start=1):
        text_result = await send_imessage(
            target["phone"],
            target["body"],
            send_real=send_real,
        )
        await _record_message_safe(
            phone=target["phone"],
            direction="outbound",
            body=target["body"],
            channel="imessage",
            to_number=target["phone"],
        )

        call_status = ""
        if target["call"]:
            call_result = await _place_key_role_call(target, send_real=send_real)
            call_status = call_result["status"]
            if call_result.get("id"):
                await _record_call_safe(target["phone"], call_result.get("id"))
            evidence.append(
                f"AgentPhone call to {target['name']} ({_last4(target['phone'])}): {call_status}."
            )

        await _record_message_safe(
            phone=target["phone"],
            direction="inbound",
            body=target["response"],
            channel="simulated_reply",
            from_number=target["phone"],
        )

        delivery_status = text_result["status"]
        if call_status:
            delivery_status = f"{delivery_status}; call {call_status}"
        evidence.append(
            f"iMessage to {target['name']} ({_last4(target['phone'])}): {text_result['status']}."
        )
        rows.append(
            {
                "name": target["name"],
                "role": target["role"],
                "channel": target["channel"],
                "phone_last4": _last4(target["phone"]),
                "status": "confirmed",
                "response": f"{index} confirmed - {target['response']}",
                "live": True,
                "delivery_status": delivery_status,
            }
        )

    for name, role, status, response in SIMULATED_REPLIES:
        rows.append(
            {
                "name": name,
                "role": role,
                "channel": "Simulated reply",
                "phone_last4": "",
                "status": status,
                "response": response,
                "live": False,
                "delivery_status": "simulated",
            }
        )

    result = {
        "title": "Bulk outreach complete",
        "tag": "roster filled",
        "status": "complete",
        "summary": (
            "1 confirmed, 2 confirmed, 3 confirmed. One simulated setup decline "
            "was covered by backup, so the final roster is 10/10 filled."
        ),
        "counts": {
            "needed": 10,
            "filled": 10,
            "live_texts": 3,
            "live_calls": 1,
            "simulated_replies": 8,
            "declined": 1,
        },
        "rows": rows,
        "evidence": evidence
        + [
            "Noah declined in simulation.",
            "Taylor accepted as backup setup crew.",
            "Final roster locked at 10 confirmed contractors.",
        ],
    }
    _EXECUTED_RESULT = copy.deepcopy(result)
    return result


async def send_imessage(to_number: str, body: str, *, send_real: bool) -> dict[str, Any]:
    if not send_real:
        return {"status": "simulated", "provider": "imessage"}

    script = """
on run argv
  set targetPhone to item 1 of argv
  set targetMessage to item 2 of argv
  tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy targetPhone of targetService
    send targetMessage to targetBuddy
  end tell
end run
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            to_number,
            body,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
    except Exception as exc:
        return {"status": "failed", "provider": "imessage", "error": str(exc)}

    if proc.returncode != 0:
        return {
            "status": "failed",
            "provider": "imessage",
            "error": (stderr or stdout).decode("utf-8", errors="replace")[:400],
        }
    return {"status": "sent", "provider": "imessage"}


async def _place_key_role_call(target: dict[str, Any], *, send_real: bool) -> dict[str, Any]:
    greeting = (
        f"Hi {target['name'].split()[0]}, this is CrewLoop calling for Bay Events Co. "
        "about this Saturday's corporate dinner in SoMa. We need an event lead from "
        "6 to 11 PM, pay is 175 dollars. Can you confirm?"
    )
    # Leave system_prompt empty so AgentPhone uses webhook mode. The webhook
    # responds through ai.generate_voice_reply(), which uses settings.gemini_model_pro.
    system_prompt = ""
    try:
        return await place_agentphone_call(
            to_number=target["phone"],
            initial_greeting=greeting,
            system_prompt=system_prompt,
            send_real=send_real,
        )
    except Exception as exc:
        return {"status": "failed", "provider": "agentphone", "error": str(exc)}


async def _configure_google_deepmind_voice(*, send_real: bool) -> dict[str, Any]:
    if not send_real:
        return {"status": "simulated_webhook_mode", "provider": "agentphone"}
    try:
        result = await get_client().update_agent(
            voice_mode="webhook",
            begin_message=(
                "Hi, this is CrewLoop calling for Bay Events Co. about a quick event lead shift."
            ),
        )
        return {
            "status": "webhook_mode_enabled",
            "provider": "agentphone",
            "id": result.get("id"),
            "model": settings.gemini_model_pro,
        }
    except Exception as exc:
        return {
            "status": "webhook_mode_failed",
            "provider": "agentphone",
            "error": str(exc),
            "model": settings.gemini_model_pro,
        }


async def _record_message_safe(**kwargs: Any) -> None:
    try:
        await repo.record_message(**kwargs)
    except Exception:
        pass


async def _record_call_safe(to_number: str, call_id: str | None) -> None:
    try:
        await repo.record_call(to_number=to_number, agentphone_call_id=call_id)
    except Exception:
        pass


def _last4(phone: str) -> str:
    return phone[-4:]
