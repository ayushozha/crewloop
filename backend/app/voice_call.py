"""Voice call orchestrator: scripted Ayush opening + Gemini-driven turns +
ElevenLabs synthesis.

The owner triggers a "voice call" for a contractor+job. The flow runs:

  1. Opening turn — hard-coded line that starts with
     "Hi this is Ayush, I'm calling on behalf of CrewLoop…", customized
     with the contractor name and the job details we already know.
  2. Multi-turn loop — Gemini (3.1-pro) generates each next agent line
     from the conversation so far. A scripted "expected contractor reply"
     is synthesized via Gemini for the demo path so the call has a
     believable other side; in production we'd transcribe the real
     contractor audio instead.
  3. Each agent line is sent through ElevenLabs TTS and stored as an
     MP3 file under backend/app/static/voice-calls/{call_id}/{turn:02d}.mp3.
     The transcript is persisted to voice_call_turns so the UI can
     render the synced player.

The full demo can be replayed in the browser at /voice-call/{id}; the
"trigger one" endpoint runs the whole conversation server-side and
returns the call_id so the frontend can immediately load the player.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from . import ai, db, elevenlabs_client
from .config import settings


logger = logging.getLogger("crewloop.voice_call")

VOICE_DIR = Path(__file__).resolve().parent / "static" / "voice-calls"


# ---------------------------------------------------------------------------
# Scripted scenario: outbound shift offer.
# Pairs an Ayush line with the contractor's expected response. The agent
# adapts to whatever the contractor actually said via Gemini, but for the
# demo trigger we simulate the contractor side too.
# ---------------------------------------------------------------------------

SCRIPT_OPENING = (
    "Hi this is Ayush, I'm calling on behalf of CrewLoop for {business}. "
    "Hey {first_name}, got a sec for a quick shift question?"
)

SCRIPT_PITCH = (
    "Cool. So we've got a {hours_label} {role_label} shift {when_label} in "
    "{location}. It's {event_kind}, and pay is ${pay} flat. Are you free to take it?"
)


SIMULATED_CONTRACTOR_TURNS = [
    "Sure, what is it?",
    "Sounds doable but can the pay be a bit higher? Short notice.",
    "$150 works. I'm in.",
    "Nope, all good. I'll be there.",
]


AYUSH_FOLLOWUPS = [
    None,  # turn 0 = opening (above)
    None,  # turn 1 = pitch (above)
    # Turn 2: negotiate pay if asked
    (
        "Totally fair, given the same-day timing. I can flex to ${pay_high}. "
        "Does that work for you?"
    ),
    # Turn 3: confirm
    (
        "Locking it in. I'll text you the address, the bar setup photo, and the drink menu "
        "in the next 30 seconds. Plan to arrive by {arrival}. Anything you need from us?"
    ),
    # Turn 4: close
    (
        "Great. You're confirmed. Thanks {first_name}, talk soon."
    ),
]


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------

def _opening_line(contractor_name: str, business: str) -> str:
    first = contractor_name.split()[0] if contractor_name else "there"
    return SCRIPT_OPENING.format(business=business, first_name=first)


def _pitch_line(job: dict[str, Any]) -> str:
    start = job.get("start_time") or "tonight"
    end = job.get("end_time") or ""
    # naive duration string for the script
    hours_label = "4-hour" if "PM" in (start + end) else "shift"
    return SCRIPT_PITCH.format(
        hours_label=hours_label,
        role_label=(job.get("role") or "shift").replace("_", " "),
        when_label=start,
        location=job.get("location") or "the venue",
        event_kind=_describe_event(job),
        pay=int(float(job.get("pay_amount") or 0)),
    )


def _describe_event(job: dict[str, Any]) -> str:
    desc = (job.get("description") or "").lower()
    if "cocktail" in desc:
        return "a 60-person cocktail reception with a signature menu"
    if "dinner" in desc:
        return "a corporate plated dinner"
    if "wedding" in desc:
        return "a wedding reception"
    if "brunch" in desc:
        return "a Sunday pop-up brunch"
    return "an event we're staffing"


def _followup_line(turn_idx: int, job: dict[str, Any], contractor_name: str) -> str:
    template = AYUSH_FOLLOWUPS[turn_idx] if turn_idx < len(AYUSH_FOLLOWUPS) else None
    first = contractor_name.split()[0] if contractor_name else "there"
    pay = int(float(job.get("pay_amount") or 0))
    pay_high = pay + 15  # the "I can flex" amount
    arrival = "5:55 PM" if "Tonight" in (job.get("start_time") or "") else "the start time"
    if template is None:
        return ""
    return template.format(pay_high=pay_high, first_name=first, arrival=arrival)


VOICE_SYSTEM_PROMPT_OUTBOUND = """You are Ayush, calling a contractor on behalf of CrewLoop to offer them a paid event shift.

Style:
- Sound human, warm, direct. Contractions, no list-speak.
- One short turn at a time. Never deliver more than 2 sentences.
- Listen for confirmations / declines / questions and respond.
- Wrap up cleanly with a confirmation message if they accept.

When the contractor asks for more pay and the job has same-day timing, you may flex by up to $15. Confirm explicitly when you do.

If they decline, thank them briefly and end the call ("Thanks for picking up, talk soon").
"""


# ---------------------------------------------------------------------------
# Core flow
# ---------------------------------------------------------------------------

async def create_call(
    *,
    job: dict[str, Any] | None,
    contractor_name: str,
    contractor_id: UUID | None = None,
) -> dict[str, Any]:
    sql = """
        INSERT INTO voice_calls (job_id, contractor_id, contractor_name, scenario, status)
        VALUES ($1, $2, $3, 'shift_offer', 'in_progress')
        RETURNING *
    """
    job_id = UUID(job["id"]) if (job and job.get("id")) else None
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, job_id, contractor_id, contractor_name)
    return _row_to_dict(row)


async def append_turn(
    call_id: UUID | str,
    turn_idx: int,
    role: str,
    text: str,
    audio_path: str | None = None,
    audio_bytes: int = 0,
) -> dict[str, Any]:
    sql = """
        INSERT INTO voice_call_turns (call_id, turn_index, role, text, audio_path, audio_bytes)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (call_id, turn_index) DO UPDATE SET
          text = EXCLUDED.text,
          audio_path = COALESCE(EXCLUDED.audio_path, voice_call_turns.audio_path),
          audio_bytes = EXCLUDED.audio_bytes
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, call_id, turn_idx, role, text, audio_path, audio_bytes)
    return _row_to_dict(row)


async def synth_and_save(text: str, call_id: str, turn_idx: int) -> tuple[str | None, int]:
    """Generate audio for an Ayush turn. Returns (relative_url, byte_count)."""
    audio = await elevenlabs_client.synthesize(text)
    if not audio:
        return None, 0
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    call_dir = VOICE_DIR / call_id
    call_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{turn_idx:02d}.mp3"
    out = call_dir / fname
    out.write_bytes(audio)
    return f"/static/voice-calls/{call_id}/{fname}", len(audio)


async def run_demo_call(*, job: dict[str, Any], contractor_name: str, contractor_id: UUID | None = None) -> dict[str, Any]:
    """Run the full scripted shift-offer conversation. Each Ayush line is
    synthesized via ElevenLabs and stored. Contractor lines come from the
    simulated script (so we have a believable other side without a real
    phone call). Returns the call_id + transcript with audio URLs."""
    call = await create_call(job=job, contractor_name=contractor_name, contractor_id=contractor_id)
    call_id = call["id"]
    business = (job or {}).get("business_name") or "Bay Events Co."

    turns: list[dict[str, Any]] = []
    turn_idx = 0

    # Turn 0 — opening
    opener = _opening_line(contractor_name, business)
    path, n = await synth_and_save(opener, call_id, turn_idx)
    await append_turn(call_id, turn_idx, "ayush", opener, path, n)
    turns.append({"role": "ayush", "text": opener, "audio_path": path})
    turn_idx += 1

    # Turn 1 — simulated contractor: "Sure, what is it?"
    contractor_line = SIMULATED_CONTRACTOR_TURNS[0]
    await append_turn(call_id, turn_idx, "contractor", contractor_line)
    turns.append({"role": "contractor", "text": contractor_line, "audio_path": None})
    turn_idx += 1

    # Turn 2 — pitch
    pitch = _pitch_line(job or {})
    path, n = await synth_and_save(pitch, call_id, turn_idx)
    await append_turn(call_id, turn_idx, "ayush", pitch, path, n)
    turns.append({"role": "ayush", "text": pitch, "audio_path": path})
    turn_idx += 1

    # Turn 3 — simulated contractor: pay ask
    contractor_line = SIMULATED_CONTRACTOR_TURNS[1]
    await append_turn(call_id, turn_idx, "contractor", contractor_line)
    turns.append({"role": "contractor", "text": contractor_line, "audio_path": None})
    turn_idx += 1

    # Turn 4 — flex pay
    flex = _followup_line(2, job or {}, contractor_name)
    path, n = await synth_and_save(flex, call_id, turn_idx)
    await append_turn(call_id, turn_idx, "ayush", flex, path, n)
    turns.append({"role": "ayush", "text": flex, "audio_path": path})
    turn_idx += 1

    # Turn 5 — simulated contractor: accept
    contractor_line = SIMULATED_CONTRACTOR_TURNS[2]
    await append_turn(call_id, turn_idx, "contractor", contractor_line)
    turns.append({"role": "contractor", "text": contractor_line, "audio_path": None})
    turn_idx += 1

    # Turn 6 — confirm
    confirm = _followup_line(3, job or {}, contractor_name)
    path, n = await synth_and_save(confirm, call_id, turn_idx)
    await append_turn(call_id, turn_idx, "ayush", confirm, path, n)
    turns.append({"role": "ayush", "text": confirm, "audio_path": path})
    turn_idx += 1

    # Turn 7 — simulated contractor close
    contractor_line = SIMULATED_CONTRACTOR_TURNS[3]
    await append_turn(call_id, turn_idx, "contractor", contractor_line)
    turns.append({"role": "contractor", "text": contractor_line, "audio_path": None})
    turn_idx += 1

    # Turn 8 — close
    close = _followup_line(4, job or {}, contractor_name)
    path, n = await synth_and_save(close, call_id, turn_idx)
    await append_turn(call_id, turn_idx, "ayush", close, path, n)
    turns.append({"role": "ayush", "text": close, "audio_path": path})

    # Finalize call
    finalize_sql = """
        UPDATE voice_calls SET
          status = 'completed',
          outcome = 'accepted_with_pay_flex',
          ended_at = now(),
          total_seconds = $2
        WHERE id = $1
        RETURNING *
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(finalize_sql, call_id, 75)
    return {"call": _row_to_dict(row), "turns": turns}


async def list_call(call_id: UUID | str) -> dict[str, Any] | None:
    call_sql = "SELECT * FROM voice_calls WHERE id = $1"
    turns_sql = "SELECT * FROM voice_call_turns WHERE call_id = $1 ORDER BY turn_index"
    async with db.pool().acquire() as conn:
        call_row = await conn.fetchrow(call_sql, call_id)
        if not call_row:
            return None
        turn_rows = await conn.fetch(turns_sql, call_id)
    return {
        "call": _row_to_dict(call_row),
        "turns": [_row_to_dict(t) for t in turn_rows],
    }


async def list_calls(limit: int = 20) -> list[dict[str, Any]]:
    sql = "SELECT * FROM voice_calls ORDER BY started_at DESC LIMIT $1"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, limit)
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    for k in ("id", "job_id", "contractor_id", "call_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d
