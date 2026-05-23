"""Event schedule snapshot for the owner chat demo.

Returned after bulk outreach completes. Deterministic data so the demo always
shows the same finalized roster with call-times, stations, and pay rows.
"""
from __future__ import annotations

from typing import Any


SCHEDULE_ROWS: list[dict[str, Any]] = [
    {
        "name": "Emma Carter",
        "role": "Event lead",
        "call_time": "5:00 PM",
        "shift": "5:00 PM – 11:30 PM",
        "station": "Owner-side / runner of show",
        "pay": "$175",
        "phone_last4": "9008",
        "live": True,
    },
    {
        "name": "Madison Reed",
        "role": "Bartender",
        "call_time": "5:30 PM",
        "shift": "5:30 PM – 11:15 PM",
        "station": "Bar 1 (lobby)",
        "pay": "$175",
        "phone_last4": "0513",
        "live": True,
    },
    {
        "name": "Olivia Parker",
        "role": "Bartender",
        "call_time": "5:30 PM",
        "shift": "5:30 PM – 11:15 PM",
        "station": "Bar 2 (dining room)",
        "pay": "$165",
        "phone_last4": "4471",
        "live": False,
    },
    {
        "name": "Ashley Brooks",
        "role": "Server",
        "call_time": "5:45 PM",
        "shift": "5:45 PM – 11:00 PM",
        "station": "Floor section A (north)",
        "pay": "$125",
        "phone_last4": "9702",
        "live": True,
    },
    {
        "name": "Claire Walsh",
        "role": "Server",
        "call_time": "5:45 PM",
        "shift": "5:45 PM – 11:00 PM",
        "station": "Floor section B (south)",
        "pay": "$125",
        "phone_last4": "3318",
        "live": False,
    },
    {
        "name": "Harper Lane",
        "role": "Server",
        "call_time": "5:45 PM",
        "shift": "5:45 PM – 11:00 PM",
        "station": "Floor section C (east)",
        "pay": "$125",
        "phone_last4": "6602",
        "live": False,
    },
    {
        "name": "Brooke Miller",
        "role": "Server",
        "call_time": "5:45 PM",
        "shift": "5:45 PM – 11:00 PM",
        "station": "Floor section D (west)",
        "pay": "$125",
        "phone_last4": "8190",
        "live": False,
    },
    {
        "name": "Luis Romero",
        "role": "Setup crew",
        "call_time": "4:00 PM",
        "shift": "4:00 PM – 6:30 PM",
        "station": "Load-in / table + linen setup",
        "pay": "$110",
        "phone_last4": "2274",
        "live": False,
    },
    {
        "name": "Taylor Adams",
        "role": "Setup crew",
        "call_time": "4:00 PM",
        "shift": "4:00 PM – 6:30 PM",
        "station": "Load-in / AV + ice run",
        "pay": "$110",
        "phone_last4": "5538",
        "live": False,
    },
    {
        "name": "Natalie Cole",
        "role": "Cleanup lead",
        "call_time": "10:00 PM",
        "shift": "10:00 PM – 12:30 AM",
        "station": "Cleanup + venue handoff",
        "pay": "$135",
        "phone_last4": "9027",
        "live": False,
    },
]


def is_schedule_request(text: str) -> bool:
    lower = text.lower()
    if "schedule" not in lower:
        return False
    return any(
        verb in lower
        for verb in ("create", "set", "build", "make", "draft", "finalize", "publish", "send", "share")
    ) or "finalized" in lower or "roster" in lower


def _call_time_minutes(call_time: str) -> int:
    """Return minutes-from-midnight for sorting (e.g. '4:00 PM' → 960)."""
    raw, ampm = call_time.rsplit(" ", 1)
    hour_str, minute_str = raw.split(":")
    hour, minute = int(hour_str), int(minute_str)
    if ampm.upper() == "PM" and hour != 12:
        hour += 12
    if ampm.upper() == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def build_schedule_snapshot() -> dict[str, Any]:
    total_labor = sum(int(row["pay"].lstrip("$")) for row in SCHEDULE_ROWS)
    earliest_call = min(SCHEDULE_ROWS, key=lambda r: _call_time_minutes(r["call_time"]))["call_time"]
    return {
        "title": "Event schedule – Saturday corporate dinner",
        "tag": f"{len(SCHEDULE_ROWS)}-person roster",
        "status": "ready",
        "summary": (
            f"Schedule locked for the 10-person roster. Earliest call is {earliest_call} "
            "(setup crew). Cleanup lead arrives at 10:00 PM."
        ),
        "event": {
            "date": "This Saturday",
            "time": "6:00 PM – 11:00 PM",
            "location": "SoMa, San Francisco",
        },
        "rows": SCHEDULE_ROWS,
        "totals": {
            "crew": len(SCHEDULE_ROWS),
            "labor": f"${total_labor:,}",
            "arrive_by": earliest_call,
            "live_confirmed": sum(1 for row in SCHEDULE_ROWS if row["live"]),
        },
        "evidence": [
            "Call times staggered by role: setup at 4:00 PM, bar at 5:30 PM, floor at 5:45 PM, cleanup at 10:00 PM.",
            "Each contractor will receive an AgentPhone SMS with their call time, station, and Sponge wallet id.",
            "Schedule is locked but editable until 12 hours before call time.",
        ],
    }
