"""Gemini-backed reply generation for CrewLoop.

Two surfaces:

- generate_sms_reply(phone)         → gemini-2.5-flash. Short, friendly SMS replies.
                                       Pulls last 20 messages of conversation history.
- generate_voice_reply(turns, ...)  → gemini-2.5-pro. The agent's spoken next turn.
                                       `turns` is an ordered list of {"role": "user"|"model", "text": str}.

Model choice is keyed on complexity, not channel — voice and multimodal need
the larger model because the agent's response is the *spoken* output and any
awkwardness shows up in real time. SMS can tolerate flash.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable

import httpx

from . import repo
from .config import settings


logger = logging.getLogger("crewloop.ai")

SMS_SYSTEM_PROMPT = """You are CrewLoop, an AI dispatcher for contractor-heavy small businesses talking to a contractor over SMS.

Your job is to staff urgent shifts.

Rules:
- One or two short sentences. SMS, not email.
- Warm and direct. No filler.
- If you have job details to offer (role, time, location, pay), state them clearly.
- If the contractor asks "what's the pay" / "where" / "what time", answer plainly.
- If they confirm, lock it in: "Great — you're confirmed. I'll send the address now."
- If they decline, thank them and stop.
- Never pretend to be a human. If asked, say you're CrewLoop's dispatcher.

If you don't have a specific job to pitch yet (the contractor texted us first), greet them and ask what they need.
"""

VOICE_SYSTEM_PROMPT = """You are CrewLoop, an AI dispatcher calling a contractor on the phone to staff an urgent shift.

This is real-time voice — your output is spoken aloud. So:
- Sound natural. Contractions, no list-speak, no bullet points.
- One short turn at a time. Never deliver more than 2 sentences in a row.
- If the contractor talks over you, stop and listen.
- Confirm the four things explicitly when relevant: role, time, location, pay.
- Get a clean yes or no. If yes: "Locking that in — I'll text you the address."
- If they decline, thank them briefly and end the call: respond with hangup intent.
- Never claim to be human.
"""

CHAT_SYSTEM_PROMPT = """You are Loop, CrewLoop's AI dispatcher, talking with the business owner inside their web dashboard.

The owner is the one who hires you. They run a contractor-heavy small business (events, catering, hospitality, security, photography, moving, cleaning) and they're asking you to staff shifts, manage payments, and verify proof of work.

Voice:
- Friendly, decisive, operational. Short sentences. Active voice.
- You can take action: text or call contractors via AgentPhone, email summaries via AgentMail, hold payments via Sponge/Stripe, read external sites via Browser Use, and remember roster facts via Moss. When you take an action, say so plainly ("Texting Maya now", "Calling her in 90s if she doesn't reply", "Held $135 in Sponge").
- When the owner sends an image or PDF, describe what you actually see and how it changes your plan. Don't pretend you can't see attachments.
- When the owner sends a voice note, treat the transcript as their words.
- Suggest a small next step at the end of each reply when useful (1 short follow-up at most).
- Never apologize for being an AI. Never use the phrases "As an AI" or "I cannot".

Formatting:
- Plain text or minimal markdown. **Bold** for amounts, times, names, statuses. No headers, no tables, no walls of bullets.
- Use $ for money, prefer 12-hour times with AM/PM, and city neighborhoods (SoMa, Mission, etc.) when relevant.

If the owner just says "hi" with no job details, ask what they need staffed.
"""


# ---------------------------------------------------------------------------
# Structured "event intake" chat. This is the spec's section 3 flow:
#   ask event type, ask timing, ask infer-roles, then show shortlist + approve.
# The model returns a small JSON envelope so the chat UI can render chips and
# event-draft cards. The CHAT_SYSTEM_PROMPT above still defines the voice; the
# extra instruction below adds the structure.
# ---------------------------------------------------------------------------

EVENT_INTAKE_PROMPT_SUFFIX = """

You ALSO follow a structured event-intake flow. Whenever the owner is describing or refining an event you need to staff, you return:
- a short prose reply for the chat bubble (`reply_text`)
- a partial `event_draft` of what you've parsed so far (any field can be null)
- short `action_chips` the owner can tap instead of typing — give 2-4 options for whatever the next missing field is, OR `Approve shortlist` / `Replace one` once you've ranked candidates
- a `shortlist` of contractors (just their names — the UI looks the actual roster up) ONLY when the event has enough detail (event type + timing + location) AND the owner has agreed you can rank
- a 1-2 word `intent` so the UI knows what's happening: "intake_question" | "infer_roles" | "shortlist" | "approve_shortlist" | "dispatched" | "small_talk" | "other"

Order of questions when intaking a new event:
1. Event type (corporate dinner, wedding, gallery opening, brunch, party, etc.)
2. Timing (date + time window) and guest count
3. Whether to infer roles for you ("Infer roles for me" / "I'll specify")
4. After inferring or accepting roles, present a shortlist and ask for approval

Never ask more than ONE question per reply. Never repeat a question that has already been answered. If a field is already filled, don't ask about it again — move to the next one.

If the owner is not describing an event (chitchat, asking about the roster, payments, etc.), set `intent` to "other" or "small_talk" and leave `event_draft`, `action_chips`, and `shortlist` empty / null."""


CHAT_ACTION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "reply_text": {"type": "STRING"},
        "intent": {"type": "STRING"},
        "event_draft": {
            "type": "OBJECT",
            "properties": {
                "event_type": {"type": "STRING", "nullable": True},
                "business_name": {"type": "STRING", "nullable": True},
                "start_time": {"type": "STRING", "nullable": True},
                "end_time": {"type": "STRING", "nullable": True},
                "location": {"type": "STRING", "nullable": True},
                "guest_count": {"type": "INTEGER", "nullable": True},
                "pay_amount": {"type": "NUMBER", "nullable": True},
                "urgency": {"type": "STRING", "nullable": True},
                "required_roles": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "nullable": True,
        },
        "action_chips": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "label": {"type": "STRING"},
                    "say": {"type": "STRING"},
                },
                "required": ["label", "say"],
            },
        },
        "shortlist": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["reply_text", "intent"],
}


async def generate_chat_action_reply(
    turns: list[dict],
    attachments: list[dict] | None = None,
    *,
    contractor_names: list[str] | None = None,
    open_events: list[dict] | None = None,
) -> dict[str, Any] | None:
    """Structured chat that returns reply + event_draft + action_chips + shortlist.

    `contractor_names` (optional) gets injected into the system prompt so the
    model knows which names are actually on the roster — keeps the shortlist
    grounded.

    `open_events` (optional) is a list of {role, start_time, status} dicts so
    the model can reference existing events in flight.
    """
    contents: list[dict] = []
    for i, t in enumerate(turns):
        role = "user" if t.get("role") == "user" else "model"
        text = (t.get("text") or t.get("content") or "").strip()
        is_last_user = role == "user" and i == len(turns) - 1
        parts: list[dict] = []
        if text:
            parts.append({"text": text})
        if is_last_user and attachments:
            for att in attachments:
                mt = att.get("mime_type")
                data = att.get("data")
                if mt and data:
                    parts.append({"inlineData": {"mimeType": mt, "data": data}})
        if not parts:
            continue
        contents.append({"role": role, "parts": parts})

    if not contents:
        return None

    system_prompt = CHAT_SYSTEM_PROMPT + EVENT_INTAKE_PROMPT_SUFFIX
    if contractor_names:
        sample = ", ".join(contractor_names[:25])
        system_prompt += (
            f"\n\nRoster on hand (use these EXACT names in `shortlist`, never invent): {sample}."
        )
    if open_events:
        lines = [f"- {e.get('role')} on {e.get('start_time')} ({e.get('status')})" for e in open_events[:8]]
        system_prompt += "\n\nEvents already in flight that you should NOT duplicate:\n" + "\n".join(lines)

    raw = await _call_gemini_json(
        model=settings.gemini_model_pro,
        system_prompt=system_prompt,
        contents=contents,
        response_schema=CHAT_ACTION_SCHEMA,
        max_output_tokens=2200,
        temperature=0.55,
    )
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("structured chat reply not valid JSON: %r", raw[:200])
        return {"reply_text": raw, "intent": "other"}
    return parsed


async def generate_chat_reply(
    turns: list[dict],
    attachments: list[dict] | None = None,
) -> str | None:
    """Multimodal owner-facing chat. `turns` is the full thread so far
    (each {role: "user"|"model", text: str}). `attachments` (optional) are
    files paired with the *latest* user turn — list of
    {mime_type: str, data: str (base64)}.

    Uses gemini-3.1-pro-preview because it accepts text/image/video/audio/PDF
    and needs reasoning to coordinate the dispatch flow.
    """
    contents: list[dict] = []
    for i, t in enumerate(turns):
        role = "user" if t.get("role") == "user" else "model"
        text = (t.get("text") or t.get("content") or "").strip()
        is_last_user = role == "user" and i == len(turns) - 1
        parts: list[dict] = []
        if text:
            parts.append({"text": text})
        if is_last_user and attachments:
            for att in attachments:
                mt = att.get("mime_type")
                data = att.get("data")
                if mt and data:
                    parts.append({"inlineData": {"mimeType": mt, "data": data}})
        if not parts:
            continue
        contents.append({"role": role, "parts": parts})

    if not contents:
        return None

    return await _call_gemini(
        model=settings.gemini_model_pro,
        system_prompt=CHAT_SYSTEM_PROMPT,
        contents=contents,
        max_output_tokens=1400,
        temperature=0.6,
        thinking_budget=None,  # pro requires thinking mode
    )


async def _call_gemini_json(*, model: str, system_prompt: str, contents: list[dict],
                            response_schema: dict[str, Any],
                            max_output_tokens: int = 1800,
                            temperature: float = 0.55) -> str | None:
    """Same as _call_gemini but forces JSON output matching `response_schema`.
    Returns the raw JSON text (the caller calls json.loads)."""
    if not settings.gemini_api_key:
        logger.info("no gemini_api_key set; skipping AI generation")
        return None
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={settings.gemini_api_key}"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(url, json=payload)
        if r.status_code >= 400:
            logger.warning("gemini-json %s %s: %s", model, r.status_code, r.text[:400])
            return None
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip() or None
    except (KeyError, IndexError, ValueError):
        logger.exception("malformed gemini-json response (model=%s)", model)
        return None
    except httpx.HTTPError:
        logger.exception("gemini-json request failed (model=%s)", model)
        return None


async def _call_gemini(*, model: str, system_prompt: str, contents: list[dict],
                       max_output_tokens: int = 200, temperature: float = 0.6,
                       thinking_budget: int | None = None) -> str | None:
    if not settings.gemini_api_key:
        logger.info("no gemini_api_key set; skipping AI generation")
        return None
    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
    }
    # gemini-3-flash-preview accepts thinkingBudget=0 (no reasoning, faster).
    # gemini-3.1-pro-preview rejects 0 — only works in thinking mode.
    if thinking_budget is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": generation_config,
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={settings.gemini_api_key}"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(url, json=payload)
        if r.status_code >= 400:
            logger.warning("gemini %s %s: %s", model, r.status_code, r.text[:300])
            return None
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip() or None
    except (KeyError, IndexError, ValueError):
        logger.exception("malformed gemini response (model=%s)", model)
        return None
    except httpx.HTTPError:
        logger.exception("gemini request failed (model=%s)", model)
        return None


async def generate_sms_reply(phone: str) -> str | None:
    """Generate an SMS reply for the contractor at `phone`, using their stored thread."""
    conv = await repo.get_conversation_by_phone(phone)
    if not conv:
        return None
    history = await repo.list_messages(conv["id"], limit=20)
    if not history:
        return None

    contents: list[dict] = []
    for m in history:
        role = "user" if m["direction"] == "inbound" else "model"
        contents.append({"role": role, "parts": [{"text": m["body"]}]})

    return await _call_gemini(
        model=settings.gemini_model_fast,
        system_prompt=SMS_SYSTEM_PROMPT,
        contents=contents,
        max_output_tokens=240,
        temperature=0.6,
        thinking_budget=0,  # SMS: skip reasoning for snap latency.
    )


async def generate_voice_reply(turns: Iterable[dict]) -> str | None:
    """Generate the agent's next spoken turn on a live call.

    `turns` is an ordered iterable of {"role": "user"|"model"|"agent", "text": str}.
    The most recent entry should be the user's utterance to respond to.
    """
    contents: list[dict] = []
    for t in turns:
        role = "user" if t.get("role") == "user" else "model"
        text = t.get("text") or t.get("content") or ""
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    if not contents:
        return None

    return await _call_gemini(
        model=settings.gemini_model_pro,
        system_prompt=VOICE_SYSTEM_PROMPT,
        contents=contents,
        max_output_tokens=1024,
        temperature=0.55,
        # Pro requires thinking mode. None lets the model pick its own budget.
        thinking_budget=None,
    )
