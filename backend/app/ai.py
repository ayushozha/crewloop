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

import logging
from typing import Iterable

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
