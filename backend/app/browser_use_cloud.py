"""Thin async wrapper around the Browser Use Cloud API.

POST /api/v3/sessions  → start a task (returns id + live_url)
GET  /api/v3/sessions/{id} → status + live_url + step_count + cost_usd + output

We use it for the supplies panel: one parallel session per recommended item
that browses Amazon / Walmart / K&L / WebstaurantStore / etc., searches for
the product, and reports the price.

Falls back to a deterministic "demo" session (no real call, fake live_url that
points at a stub iframe) when BROWSER_USE_API_KEY is missing or the cloud API
errors. The fallback is identifiable because session_id starts with `sim_`.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import settings


logger = logging.getLogger("crewloop.browseruse")

DEFAULT_MODEL = "claude-sonnet-4.6"


async def start_session(
    *,
    task: str,
    allowed_domains: list[str] | None = None,
    recording: bool = True,
    max_steps: int = 25,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Start a Browser Use Cloud session. Returns the raw response or a
    simulated stub if the API isn't reachable."""
    key = settings.browser_use_api_key
    base = settings.browser_use_base_url.rstrip("/")
    if not key:
        return _simulated(task)

    payload: dict[str, Any] = {
        "task": task,
        "model": model,
        "recording": recording,
        "max_steps": max_steps,
    }
    if allowed_domains:
        payload["allowed_domains"] = allowed_domains

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(
                f"{base}/sessions",
                json=payload,
                headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
            )
        if r.status_code >= 400:
            logger.warning("browser-use %s: %s", r.status_code, r.text[:300])
            return _simulated(task)
        data = r.json()
        return {
            "id": data.get("id") or data.get("session_id"),
            "live_url": data.get("live_url"),
            "status": data.get("status") or "running",
            "step_count": data.get("step_count") or 0,
            "cost_usd": data.get("cost_usd") or 0,
            "output": data.get("output"),
            "simulated": False,
        }
    except httpx.HTTPError:
        logger.exception("browser-use start_session failed")
        return _simulated(task)


async def get_session(session_id: str) -> dict[str, Any]:
    """Fetch current session state. Falls back gracefully if unreachable."""
    if not session_id or session_id.startswith("sim_"):
        return _simulated_status(session_id or "sim_unknown")
    key = settings.browser_use_api_key
    base = settings.browser_use_base_url.rstrip("/")
    if not key:
        return _simulated_status(session_id)
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(
                f"{base}/sessions/{session_id}",
                headers={"X-Browser-Use-API-Key": key},
            )
        if r.status_code >= 400:
            return _simulated_status(session_id)
        d = r.json()
        return {
            "id": d.get("id") or session_id,
            "status": d.get("status") or "running",
            "live_url": d.get("live_url"),
            "step_count": d.get("step_count") or 0,
            "cost_usd": d.get("cost_usd") or 0,
            "output": d.get("output"),
            "simulated": False,
        }
    except httpx.HTTPError:
        logger.exception("browser-use get_session failed")
        return _simulated_status(session_id)


# ---------------------------------------------------------------------------
# Simulation fallback
# ---------------------------------------------------------------------------

# Tiny embeddable stub URL. The frontend recognises sim_ session IDs and shows
# a fake browser chrome with a typed-out URL bar + stepping screenshots. We
# still hand the iframe a real-looking URL so it loads as a "vendor preview".
SIM_LIVE_BASE = "https://www.google.com/search"


def _simulated(task: str) -> dict[str, Any]:
    sid = "sim_" + hashlib.sha256(task.encode("utf-8")).hexdigest()[:16]
    q = task[:80]
    url = SIM_LIVE_BASE + "?" + urlencode({"q": q, "igu": "1"})  # igu=1 disables Google's frame-busting
    return {
        "id": sid,
        "status": "running",
        "live_url": url,
        "step_count": 0,
        "cost_usd": 0,
        "output": None,
        "simulated": True,
    }


def _simulated_status(session_id: str) -> dict[str, Any]:
    # Deterministically advance through a few "steps" so the polling UI moves.
    bucket = int(hashlib.sha256(session_id.encode("utf-8")).hexdigest(), 16) % 6
    states = ["running", "running", "running", "idle", "idle", "idle"]
    return {
        "id": session_id,
        "status": states[bucket],
        "live_url": None,
        "step_count": 3 + bucket * 2,
        "cost_usd": 0.012 + bucket * 0.004,
        "output": None,
        "simulated": True,
    }
