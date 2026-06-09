"""Pure logic for the fill-a-shift loop: reply classification, STOP/opt-out
detection, roster CSV parsing, and at-risk computation.

No I/O and no settings import on purpose — everything here is unit-testable
without a database or environment.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any

# CTIA-standard opt-out keywords. A message counts as an opt-out only when the
# trimmed body IS one of these (case-insensitive) — "please don't cancel my
# shift" must not opt anyone out.
STOP_KEYWORDS = {"stop", "stopall", "stop all", "unsubscribe", "cancel", "end", "quit", "revoke", "optout", "opt out"}
START_KEYWORDS = {"start", "unstop", "subscribe", "opt in", "optin"}

_MAYBE_RE = re.compile(r"\b(maybe|possibly|depends|not sure|might|tentative|let me check|check my)\b")
_NO_RE = re.compile(r"\b(no|nope|nah|can'?t|cannot|unavailable|not available|pass|won'?t|decline|booked|sorry)\b")
_YES_RE = re.compile(
    r"\b(yes|yep|yeah|ya|yup|confirm|confirmed|i'?m in|count me in|i can|i'?ll take|available|works|sounds good|sure|down|in)\b"
)


def classify_reply(text: str) -> str:
    """Classify an inbound SMS reply to a shift invite.

    Returns one of: 'stop', 'start', 'maybe', 'no', 'yes', 'other'.
    Order matters: STOP/START are compliance and beat everything; 'maybe'
    beats 'yes' so "not sure" doesn't match the 'sure' in the yes-list;
    'no' beats 'yes' so "no, sorry" doesn't match 'sounds good'-style tokens.
    """
    lower = " ".join((text or "").lower().split())
    if not lower:
        return "other"
    normalized = lower.rstrip(".!,")
    if normalized in STOP_KEYWORDS:
        return "stop"
    if normalized in START_KEYWORDS:
        return "start"
    if _MAYBE_RE.search(lower):
        return "maybe"
    if _NO_RE.search(lower):
        return "no"
    if _YES_RE.search(lower):
        return "yes"
    return "other"


def normalize_phone(raw: str) -> str | None:
    """Normalize a phone number to E.164. US-biased on purpose (pilots are US):
    10 digits get +1. Returns None when the number can't be normalized."""
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw.strip())
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        return f"+{digits}" if 7 <= len(digits) <= 15 and digits.isdigit() else None
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"+1{cleaned}"
    if len(cleaned) == 11 and cleaned.startswith("1") and cleaned.isdigit():
        return f"+{cleaned}"
    return None


_HEADER_ALIASES = {
    "name": "name", "full_name": "name", "contractor": "name", "worker": "name",
    "phone": "phone", "phone_number": "phone", "mobile": "phone", "cell": "phone", "number": "phone",
    "roles": "skills", "role": "skills", "skills": "skills", "skill": "skills", "positions": "skills",
    "priority": "priority", "rank": "priority", "order": "priority",
    "rate": "hourly_rate", "hourly_rate": "hourly_rate", "pay_rate": "hourly_rate", "pay": "hourly_rate",
    "notes": "notes", "note": "notes",
    "email": "email",
    "location": "location", "city": "location",
}


def parse_roster_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse an operator's roster CSV into contractor rows.

    Required columns (any alias): name, phone. Optional: roles (split on
    ; | or /), priority (int, lower = called first), rate, notes, email,
    location. Returns (rows, errors); a bad row becomes an error, never a
    silent skip.
    """
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    reader = csv.DictReader(io.StringIO(text or ""))
    if not reader.fieldnames:
        return [], ["empty CSV: no header row found"]

    field_map: dict[str, str] = {}
    for raw in reader.fieldnames:
        key = (raw or "").strip().lower().replace(" ", "_")
        if key in _HEADER_ALIASES:
            field_map[raw] = _HEADER_ALIASES[key]
    if "name" not in field_map.values() or "phone" not in field_map.values():
        return [], [f"CSV must include name and phone columns; found: {', '.join(reader.fieldnames)}"]

    seen_phones: set[str] = set()
    for line_no, raw_row in enumerate(reader, start=2):
        row: dict[str, Any] = {}
        for raw_key, canonical in field_map.items():
            value = (raw_row.get(raw_key) or "").strip()
            if value:
                row[canonical] = value

        name = row.get("name")
        phone = normalize_phone(row.get("phone", ""))
        if not name or not phone:
            errors.append(f"row {line_no}: missing or invalid name/phone ({row.get('name')!r}, {row.get('phone')!r})")
            continue
        if phone in seen_phones:
            errors.append(f"row {line_no}: duplicate phone {phone}, keeping the first occurrence")
            continue
        seen_phones.add(phone)

        skills = [s.strip().lower() for s in re.split(r"[;|/]", row.get("skills", "")) if s.strip()]
        priority = 100
        if row.get("priority"):
            try:
                priority = int(float(row["priority"]))
            except ValueError:
                errors.append(f"row {line_no}: priority {row['priority']!r} is not a number, defaulting to 100")
        hourly_rate = None
        if row.get("hourly_rate"):
            try:
                hourly_rate = float(row["hourly_rate"].lstrip("$"))
            except ValueError:
                errors.append(f"row {line_no}: rate {row['hourly_rate']!r} is not a number, leaving unset")

        rows.append(
            {
                "name": name,
                "phone": phone,
                "skills": skills,
                "priority": priority,
                "hourly_rate": hourly_rate,
                "notes": row.get("notes"),
                "email": row.get("email"),
                "location": row.get("location") or "",
            }
        )
    return rows, errors


def is_at_risk(
    *,
    status: str,
    ping_48_sent_at: datetime | None,
    ping_4_sent_at: datetime | None,
    last_reply_at: datetime | None,
    now: datetime,
    grace_hours: float = 2.0,
) -> bool:
    """v1 flake detection: a worker who said yes but hasn't answered the most
    recent confirmation ping within the grace window is flagged at-risk on the
    board. A flag plus founder judgment — not a model."""
    if status != "yes":
        return False
    last_ping = max((p for p in (ping_48_sent_at, ping_4_sent_at) if p is not None), default=None)
    if last_ping is None:
        return False
    if last_reply_at is not None and last_reply_at >= last_ping:
        return False
    return now - last_ping > timedelta(hours=grace_hours)


def invite_message(job: dict[str, Any], business: str | None = None) -> str:
    """The outbound invite text. Always carries the STOP notice (TCPA/CTIA)."""
    biz = business or job.get("business_name") or "CrewLoop"
    when = job.get("start_time") or "TBD"
    end = job.get("end_time")
    if end:
        when = f"{when} - {end}"
    pay = job.get("pay_amount")
    pay_part = f" Pay ${float(pay):g}." if pay else ""
    return (
        f"{biz} via CrewLoop: {job.get('role', 'shift')} shift {when} at "
        f"{job.get('location', 'TBD')}.{pay_part} Reply YES to take it or NO to pass. Reply STOP to opt out."
    )


def ping_message(job: dict[str, Any], horizon: str) -> str:
    """Confirmation ping text for T-48h / T-4h."""
    when = job.get("start_time") or "your shift time"
    return (
        f"CrewLoop check-in ({horizon} out): confirming your {job.get('role', '')} shift {when} at "
        f"{job.get('location', 'the venue')}. Reply YES to confirm."
    )
