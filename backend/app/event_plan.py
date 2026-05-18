"""Deterministic event-plan inference for the owner chat demo.

The chat can still use Gemini for open-ended conversation, but this narrow path
keeps the live demo reliable when the owner asks CrewLoop to fulfill an event.
"""
from __future__ import annotations

import re
from typing import Any


PLAN_KEYWORDS = (
    "event",
    "corporate dinner",
    "staff",
    "crew",
    "supplies",
    "inventory",
    "invoice",
    "fulfill",
)


def latest_user_text(turns: list[dict[str, str]]) -> str:
    for turn in reversed(turns):
        if turn.get("role") == "user":
            return (turn.get("text") or "").strip()
    return ""


def is_event_plan_request(text: str) -> bool:
    lower = text.lower()
    if "approve" in lower and "plan" in lower:
        return False
    return any(keyword in lower for keyword in PLAN_KEYWORDS)


def is_plan_approval(text: str) -> bool:
    lower = text.lower()
    return "approve" in lower and "plan" in lower


def infer_event_plan(text: str) -> dict[str, Any] | None:
    if not is_event_plan_request(text):
        return None

    lower = text.lower()
    guest_count = _first_int_before(text, ("guest", "guests", "person", "people")) or 80
    staff_count = _first_int_before(text, ("staff", "crew", "people", "person")) or 10
    if "10" in lower and ("people" in lower or "person" in lower or "crew" in lower):
        staff_count = 10

    event_name = "Corporate dinner" if "corporate dinner" in lower else "Event fulfillment"
    event_date = "This Saturday" if "saturday" in lower else "This weekend"
    event_time = _infer_time_window(text) or "6:00 PM - 11:00 PM"
    location = "SoMa, San Francisco" if "soma" in lower else "SoMa, San Francisco"

    labor_amount = _estimate_labor_amount(staff_count)
    supplies_amount = 86
    service_fee = 220
    invoice_amount = labor_amount + supplies_amount + service_fee

    return {
        "event_name": event_name,
        "details": f"{guest_count}-guest corporate dinner in {location}.",
        "event_date": event_date,
        "event_time": event_time,
        "location": location,
        "staff_requirement": (
            f"{staff_count} staff: 2 bartenders, 4 servers, 2 setup crew, "
            "1 event lead, 1 cleanup lead."
        ),
        "responsibilities": "Setup, food service, bartending, cleanup, and event lead oversight.",
        "inventory_requirement": (
            "100 compostable cups, 100 napkins, 4 bags of ice, "
            "2 tablecloths, bartender tool kit rental."
        ),
        "estimated_labor": f"${labor_amount:,}",
        "invoice_amount": f"${invoice_amount:,}",
        "approval_question": "Approve this plan so I can shortlist the crew and start the next steps?",
    }


def _first_int_before(text: str, words: tuple[str, ...]) -> int | None:
    pattern = r"\b(\d{1,4})\s+(?:" + "|".join(re.escape(word) for word in words) + r")\b"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _infer_time_window(text: str) -> str | None:
    match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|–|to)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    start_hour, start_min, start_ampm, end_hour, end_min, end_ampm = match.groups()
    start_ampm = start_ampm or end_ampm
    return f"{_fmt_time(start_hour, start_min, start_ampm)} - {_fmt_time(end_hour, end_min, end_ampm)}"


def _fmt_time(hour: str, minute: str | None, ampm: str | None) -> str:
    suffix = (ampm or "").upper()
    return f"{int(hour)}:{minute or '00'} {suffix}".strip()


def _estimate_labor_amount(staff_count: int) -> int:
    if staff_count == 10:
        return 1450
    return max(650, round(staff_count * 145))
