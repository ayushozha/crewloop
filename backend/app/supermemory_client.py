"""Optional Supermemory integration for owner chat memory.

CrewLoop remains fully functional without Supermemory configured. When
SUPERMEMORY_API_KEY is present, saved chat threads are mirrored to
Supermemory's conversation ingestion API so later agents can recall owner
preferences and operation history across sessions.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings


logger = logging.getLogger("crewloop.supermemory")


def enabled() -> bool:
    return bool(settings.supermemory_api_key)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.supermemory_api_key}",
        "Content-Type": "application/json",
    }


def _role(role: str) -> str:
    return "assistant" if role == "agent" else "user"


async def ingest_chat_thread(
    *,
    thread_id: str,
    title: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not enabled() or not messages:
        return None

    body = {
        "conversationId": f"crewloop-chat:{thread_id}",
        "messages": [
            {
                "role": _role(str(message.get("role") or "user")),
                "content": str(message.get("body") or ""),
                "name": "CrewLoop" if message.get("role") == "agent" else "Ayush",
            }
            for message in messages
            if str(message.get("body") or "").strip()
        ],
        "containerTags": [
            settings.supermemory_container_tag,
            "crewloop",
            "crewloop:chat",
            f"crewloop:thread:{thread_id}",
        ],
        "metadata": {
            "app": "CrewLoop",
            "kind": "owner_chat_thread",
            "thread_id": thread_id,
            "title": title,
        },
    }
    if not body["messages"]:
        return None

    url = f"{settings.supermemory_base_url.rstrip('/')}/v4/conversations"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, headers=_headers(), json=body)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.warning("Supermemory chat ingest failed for thread %s: %s", thread_id, exc)
        return None
