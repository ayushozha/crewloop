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
    # --- the spec demo: corporate dinner Saturday, SoMa, 80 guests ---
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="Corporate dinner. 80 guests. Cocktail reception then plated dinner.",
        location="SoMa, SF", start_time="Saturday · 6:00 PM", end_time="Saturday · 11:00 PM",
        pay_amount=135.00, urgency="standard",
        required_skills=("event_bartending", "high_volume", "wine_service"),
        status="shortlisting",
    ),
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="Replacement bartender — original contractor canceled 42 minutes ago.",
        location="SoMa, SF", start_time="Tonight · 6:00 PM", end_time="Tonight · 10:00 PM",
        pay_amount=135.00, urgency="urgent",
        required_skills=("event_bartending", "cocktail_menu"),
        status="accepted",
    ),
    Event(
        business_name="Bay Events Co.", role="server",
        description="Catering for a private brunch. 2 servers needed.",
        location="Marina, SF", start_time="Friday · 10:00 AM", end_time="Friday · 2:00 PM",
        pay_amount=100.00, urgency="standard",
        required_skills=("plated_service", "wine_service"),
        status="drafting",
    ),
    Event(
        business_name="Bay Events Co.", role="setup_crew",
        description="Setup crew — Pier 39 wedding reception. Released $340 to Jordan.",
        location="Pier 39, SF", start_time="Last Monday · 9:00 AM", end_time="Last Monday · 2:00 PM",
        pay_amount=85.00, urgency="standard",
        required_skills=("event_setup", "lifting"),
        status="completed",
    ),
    Event(
        business_name="Bay Events Co.", role="line_cook",
        description="Sunday pop-up brunch. Looking for one line cook.",
        location="Mission, SF", start_time="Sunday · 8:00 AM", end_time="Sunday · 1:00 PM",
        pay_amount=120.00, urgency="standard",
        required_skills=("brunch", "fast_service"),
        status="backlog",
    ),
    Event(
        business_name="Bay Events Co.", role="event_captain",
        description="Gallery opening reception. Captain to run the floor + 3 servers.",
        location="Hayes Valley, SF", start_time="Next Thursday · 6:00 PM", end_time="Next Thursday · 9:30 PM",
        pay_amount=160.00, urgency="standard",
        required_skills=("captain", "private_events"),
        status="outreach_sent",
    ),
    # --- weddings, weekends, premium events ---
    Event(
        business_name="Bay Events Co.", role="event_captain",
        description="Outdoor wedding · 120 guests · full ceremony + reception staffing run.",
        location="Presidio, SF", start_time="Sat May 30 · 3:00 PM", end_time="Sat May 30 · 11:00 PM",
        pay_amount=220.00, urgency="standard",
        required_skills=("captain", "weddings", "high_volume"),
        status="shortlisting",
    ),
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="Wedding cocktail hour · 120 guests · signature menu (3 drinks).",
        location="Presidio, SF", start_time="Sat May 30 · 5:00 PM", end_time="Sat May 30 · 9:00 PM",
        pay_amount=140.00, urgency="standard",
        required_skills=("event_bartending", "weddings"),
        status="drafting",
    ),
    Event(
        business_name="Bay Events Co.", role="server",
        description="Wedding plated dinner · 120 guests · 6 servers needed.",
        location="Presidio, SF", start_time="Sat May 30 · 6:30 PM", end_time="Sat May 30 · 10:30 PM",
        pay_amount=110.00, urgency="standard",
        required_skills=("plated_service", "wine_service"),
        status="drafting",
    ),
    Event(
        business_name="Bay Events Co.", role="photographer",
        description="Wedding day photography · 8-hour coverage.",
        location="Presidio, SF", start_time="Sat May 30 · 2:00 PM", end_time="Sat May 30 · 10:00 PM",
        pay_amount=720.00, urgency="standard",
        required_skills=("weddings", "candid", "portraits"),
        status="accepted",
    ),
    # --- corporate & product launches ---
    Event(
        business_name="Bay Events Co.", role="event_captain",
        description="Y Combinator demo-day after-party · 200 guests · cocktail-only.",
        location="Dogpatch, SF", start_time="Tue Jun 3 · 7:00 PM", end_time="Tue Jun 3 · 11:30 PM",
        pay_amount=180.00, urgency="urgent",
        required_skills=("captain", "high_volume", "private_events"),
        status="shortlisting",
    ),
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="YC demo-day after-party · 4 bartenders for 200 guests.",
        location="Dogpatch, SF", start_time="Tue Jun 3 · 7:00 PM", end_time="Tue Jun 3 · 11:30 PM",
        pay_amount=145.00, urgency="urgent",
        required_skills=("event_bartending", "high_volume", "cocktail_menu"),
        status="outreach_sent",
    ),
    Event(
        business_name="Bay Events Co.", role="security",
        description="Tech product launch · door + crowd control · 150 expected.",
        location="SoMa, SF", start_time="Thu Jun 5 · 5:30 PM", end_time="Thu Jun 5 · 10:30 PM",
        pay_amount=160.00, urgency="standard",
        required_skills=("door_security", "guest_list", "deescalation"),
        status="drafting",
    ),
    # --- catering / brunch / pop-ups ---
    Event(
        business_name="Bay Events Co.", role="line_cook",
        description="Weekend pop-up brunch series · 60 covers · 2 line cooks per day.",
        location="Mission, SF", start_time="Sat Jun 7 · 9:00 AM", end_time="Sat Jun 7 · 2:30 PM",
        pay_amount=140.00, urgency="standard",
        required_skills=("brunch", "fast_service", "egg_station"),
        status="backlog",
    ),
    Event(
        business_name="Bay Events Co.", role="server",
        description="Investor dinner · 24 guests · plated wine-paired tasting menu.",
        location="Pacific Heights, SF", start_time="Wed Jun 4 · 7:00 PM", end_time="Wed Jun 4 · 10:30 PM",
        pay_amount=130.00, urgency="standard",
        required_skills=("plated_service", "wine_service", "fine_dining"),
        status="backlog",
    ),
    Event(
        business_name="Bay Events Co.", role="event_captain",
        description="Networking mixer for SF marketing leaders · 90 guests.",
        location="Hayes Valley, SF", start_time="Wed Jun 11 · 6:00 PM", end_time="Wed Jun 11 · 9:00 PM",
        pay_amount=170.00, urgency="standard",
        required_skills=("captain", "private_events"),
        status="shortlisting",
    ),
    # --- urgent same-day fills ---
    Event(
        business_name="Bay Events Co.", role="server",
        description="Urgent same-day fill: 2 servers for a downtown private dinner.",
        location="FiDi, SF", start_time="Tonight · 7:00 PM", end_time="Tonight · 11:00 PM",
        pay_amount=120.00, urgency="urgent",
        required_skills=("plated_service",),
        status="outreach_sent",
    ),
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="Same-day backup bartender · craft cocktail bar in Mission.",
        location="Mission, SF", start_time="Tomorrow · 5:00 PM", end_time="Tomorrow · 11:00 PM",
        pay_amount=180.00, urgency="urgent",
        required_skills=("event_bartending", "cocktail_menu"),
        status="shortlisting",
    ),
    # --- non-profit / community ---
    Event(
        business_name="Bay Events Co.", role="setup_crew",
        description="Charity gala load-in · 3-person crew · stages, tables, draping.",
        location="Civic Center, SF", start_time="Fri Jun 6 · 8:00 AM", end_time="Fri Jun 6 · 2:00 PM",
        pay_amount=100.00, urgency="standard",
        required_skills=("event_setup", "lifting", "draping"),
        status="drafting",
    ),
    Event(
        business_name="Bay Events Co.", role="cleanup_crew",
        description="Charity gala teardown · same crew, late night.",
        location="Civic Center, SF", start_time="Fri Jun 6 · 11:00 PM", end_time="Sat Jun 7 · 2:00 AM",
        pay_amount=110.00, urgency="standard",
        required_skills=("teardown", "lifting"),
        status="drafting",
    ),
    # --- past completed events ---
    Event(
        business_name="Bay Events Co.", role="bartender",
        description="Holiday party at a tech HQ · 4 bartenders · completed last month.",
        location="South Beach, SF", start_time="Last month · 6:00 PM", end_time="Last month · 11:00 PM",
        pay_amount=160.00, urgency="standard",
        required_skills=("event_bartending", "high_volume"),
        status="completed",
    ),
    Event(
        business_name="Bay Events Co.", role="server",
        description="Mother's Day brunch service · 80 covers · 4 servers · paid out clean.",
        location="Pacific Heights, SF", start_time="Last week · 10:30 AM", end_time="Last week · 3:00 PM",
        pay_amount=110.00, urgency="standard",
        required_skills=("brunch", "plated_service"),
        status="completed",
    ),
    Event(
        business_name="Bay Events Co.", role="security",
        description="Outdoor festival booth · 2-day security shifts · proof + payment cleared.",
        location="Golden Gate Park, SF", start_time="Mar 22 · 11:00 AM", end_time="Mar 22 · 9:00 PM",
        pay_amount=240.00, urgency="standard",
        required_skills=("event_security", "crowd_control"),
        status="completed",
    ),
    # --- upcoming summer slate ---
    Event(
        business_name="Bay Events Co.", role="photographer",
        description="Corporate offsite headshots · 30 staff · half-day studio.",
        location="Marina, SF", start_time="Tue Jun 10 · 9:00 AM", end_time="Tue Jun 10 · 1:00 PM",
        pay_amount=480.00, urgency="standard",
        required_skills=("headshots", "studio"),
        status="backlog",
    ),
    Event(
        business_name="Bay Events Co.", role="event_captain",
        description="Birthday party for a 16-person book club · light catering only.",
        location="Noe Valley, SF", start_time="Sat Jun 14 · 6:00 PM", end_time="Sat Jun 14 · 9:30 PM",
        pay_amount=120.00, urgency="standard",
        required_skills=("captain", "small_events"),
        status="backlog",
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
