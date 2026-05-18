"""Seed a handful of demo events (rows in the jobs table) so the chat thread
has real events to reference and the /home and /chat surfaces have something
to render right away.

Run after the SSH tunnel to projects-db is open:
    ssh -fN -L 5433:127.0.0.1:5433 ayush@72.62.82.57
    cd backend
    .venv/bin/python scripts/seed_events.py

Idempotent: each event has a stable `business_name + role + start_time` key;
re-runs upsert rather than duplicating rows.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db


@dataclass(frozen=True)
class Event:
    business_name: str
    role: str
    description: str
    location: str
    start_time: str
    end_time: str
    pay_amount: float
    urgency: str
    required_skills: tuple[str, ...]
    status: str  # backlog | drafting | shortlisting | outreach_sent | accepted | completed


SEED: list[Event] = [
    Event(
        business_name="Bay Events Co.",
        role="bartender",
        description="Corporate dinner. 80 guests. Cocktail reception then plated dinner.",
        location="SoMa, SF",
        start_time="Saturday · 6:00 PM",
        end_time="Saturday · 11:00 PM",
        pay_amount=135.00,
        urgency="standard",
        required_skills=("event_bartending", "high_volume", "wine_service"),
        status="shortlisting",
    ),
    Event(
        business_name="Bay Events Co.",
        role="bartender",
        description="Replacement bartender — original contractor canceled 42 minutes ago.",
        location="SoMa, SF",
        start_time="Tonight · 6:00 PM",
        end_time="Tonight · 10:00 PM",
        pay_amount=135.00,
        urgency="urgent",
        required_skills=("event_bartending", "cocktail_menu"),
        status="accepted",
    ),
    Event(
        business_name="Bay Events Co.",
        role="server",
        description="Catering for a private brunch. 2 servers needed.",
        location="Marina, SF",
        start_time="Friday · 10:00 AM",
        end_time="Friday · 2:00 PM",
        pay_amount=100.00,
        urgency="standard",
        required_skills=("plated_service", "wine_service"),
        status="drafting",
    ),
    Event(
        business_name="Bay Events Co.",
        role="setup_crew",
        description="Setup crew — Pier 39 wedding reception. Released $340 to Jordan.",
        location="Pier 39, SF",
        start_time="Last Monday · 9:00 AM",
        end_time="Last Monday · 2:00 PM",
        pay_amount=85.00,
        urgency="standard",
        required_skills=("event_setup", "lifting"),
        status="completed",
    ),
    Event(
        business_name="Bay Events Co.",
        role="line_cook",
        description="Sunday pop-up brunch. Looking for one line cook.",
        location="Mission, SF",
        start_time="Sunday · 8:00 AM",
        end_time="Sunday · 1:00 PM",
        pay_amount=120.00,
        urgency="standard",
        required_skills=("brunch", "fast_service"),
        status="backlog",
    ),
    Event(
        business_name="Bay Events Co.",
        role="event_captain",
        description="Gallery opening. Need a lead to run the floor + 3 servers.",
        location="Hayes Valley, SF",
        start_time="Next Thursday · 6:00 PM",
        end_time="Next Thursday · 9:30 PM",
        pay_amount=160.00,
        urgency="standard",
        required_skills=("captain", "private_events"),
        status="outreach_sent",
    ),
]


UPSERT_SQL = """
WITH ins AS (
    INSERT INTO jobs
        (business_name, role, description, location, start_time, end_time,
         pay_amount, urgency, required_skills, status)
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10
    WHERE NOT EXISTS (
        SELECT 1 FROM jobs
        WHERE business_name = $1 AND role = $2 AND start_time = $5
    )
    RETURNING id
), upd AS (
    UPDATE jobs SET
        description = $3, location = $4, end_time = $6,
        pay_amount = $7, urgency = $8, required_skills = $9::text[], status = $10
    WHERE business_name = $1 AND role = $2 AND start_time = $5
      AND NOT EXISTS (SELECT 1 FROM ins)
    RETURNING id
)
SELECT id FROM ins UNION ALL SELECT id FROM upd
"""


async def main() -> None:
    await db.connect()
    try:
        async with db.pool().acquire() as conn:
            for ev in SEED:
                row = await conn.fetchrow(
                    UPSERT_SQL,
                    ev.business_name, ev.role, ev.description, ev.location,
                    ev.start_time, ev.end_time, ev.pay_amount, ev.urgency,
                    list(ev.required_skills), ev.status,
                )
                print(f"  [{ev.status:14s}] {ev.role:14s} {ev.start_time} → {row['id']}")
            count = await conn.fetchval("SELECT count(*) FROM jobs")
        print(f"\n{count} jobs in DB.")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
