"""ElevenLabs TTS wrapper.

Used by the demo voice-call flow to synthesize the agent's spoken turns
("Hi this is Ayush, I'm calling on behalf of CrewLoop…") in the cloned
voice the user configured. Stays out of AgentPhone's pipeline — the
audio is served by FastAPI as a static asset and played in the browser
or fed to AgentPhone separately if needed.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings


logger = logging.getLogger("crewloop.elevenlabs")


async def synthesize(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str | None = None,
    stability: float = 0.45,
    similarity_boost: float = 0.85,
    style: float = 0.25,
    speaker_boost: bool = True,
    output_format: str = "mp3_44100_128",
) -> bytes | None:
    """Generate speech from text. Returns raw MP3 bytes or None on failure."""
    key = settings.elevenlabs_api_key
    if not key:
        logger.info("elevenlabs_api_key not set; skipping TTS")
        return None
    voice = voice_id or settings.elevenlabs_voice_id
    model = model_id or settings.elevenlabs_model_id
    url = f"{settings.elevenlabs_base_url}/text-to-speech/{voice}?output_format={output_format}"
    payload: dict[str, Any] = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": speaker_boost,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(url, json=payload, headers={"xi-api-key": key, "Content-Type": "application/json"})
        if r.status_code >= 400:
            logger.warning("elevenlabs %s: %s", r.status_code, r.text[:300])
            return None
        return r.content
    except httpx.HTTPError:
        logger.exception("elevenlabs synth failed")
        return None
