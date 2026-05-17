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
