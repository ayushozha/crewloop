"""Seed the contractor roster + generate Gemini portraits.

Run after the SSH tunnel to projects-db is open:
    ssh -fN -L 5433:127.0.0.1:5433 ayush@72.62.82.57
    cd backend
    .venv/bin/python scripts/seed_contractors.py

Idempotent: skips rows whose phone is already in the DB and skips image
generation when the JPEG already exists on disk.
"""
from __future__ import annotations

import asyncio
import base64
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Allow `python backend/scripts/seed_contractors.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app import db
from app.config import settings


PORTRAITS_DIR = Path(__file__).resolve().parents[1] / "app" / "static" / "portraits"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"


@dataclass(frozen=True)
class Contractor:
    name: str
    phone: str
    email: str
    age: int
    skills: tuple[str, ...]
    location: str
    distance_miles: float
    hourly_rate: float
    reliability_score: int
    response_speed: str  # fast | average | slow
    languages: tuple[str, ...]
    certifications: tuple[str, ...]
    notes: str
    appearance: str  # short descriptor used in the image prompt

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")

    @property
    def attire(self) -> str:
        primary = self.skills[0]
        return {
            "bartender": "a black bartender's vest over a crisp shirt",
            "barback": "a black work shirt",
            "server": "a tailored white button-down shirt",
            "event_captain": "a tailored charcoal blazer over a clean shirt",
            "line_cook": "a white double-breasted chef's coat",
            "prep_cook": "a clean white chef's coat",
            "pastry_cook": "a soft white chef's coat with sleeves rolled",
            "sushi_cook": "a white chef's coat and dark apron",
            "security": "a black security polo with a small radio earpiece",
            "valet": "a charcoal valet jacket",
            "driver": "a simple dark crewneck",
            "mover": "a sturdy workwear button-down",
            "cleaner": "a clean navy work polo",
            "photographer": "casual smart attire, a light camera strap visible",
            "videographer": "casual smart attire",
            "dj": "a stylish layered casual outfit",
            "av_tech": "a simple dark shirt with a small headset",
            "runner": "a relaxed simple shirt",
            "guest_service": "smart hospitality attire",
            "host": "smart hospitality attire",
            "mixologist": "a black bartender vest",
        }.get(primary, "smart hospitality attire")


ROSTER: list[Contractor] = [
    Contractor("Emma Carter", "+14155550101", "emma.carter@example.com", 28, ("bartender", "guest_service"),
        "SoMa", 2.1, 30.00, 98, "fast", ("English",), ("TIPS",),
        "Five years at private event venues, picks up urgent shifts.",
        "a 28-year-old white woman with shoulder-length blonde hair, warm friendly smile"),
    Contractor("DeShawn Williams", "+14155550102", "deshawn.w@example.com", 34, ("line_cook",),
        "Western Addition", 3.8, 32.00, 95, "fast", ("English",), ("ServSafe Manager",),
        "Catering-trained, calm under fire.",
        "a 34-year-old Black man with a short fade and neatly trimmed beard, calm confident expression"),
    Contractor("Aisha Robinson", "+14155550103", "aisha.r@example.com", 31, ("event_captain", "guest_service"),
        "Mission", 1.9, 36.00, 97, "fast", ("English",), ("CPR",),
        "Runs the floor at 200+ guest events.",
        "a 31-year-old Black woman with twist-out natural hair, warm smile, polished look"),
    Contractor("Madison Reed", "+14155550104", "madison.reed@example.com", 33, ("bartender",),
        "Lower Haight", 2.6, 28.00, 78, "average", ("English",), ("TIPS",),
        "Solid bar skills, occasional late confirmations.",
        "a 33-year-old white woman with blonde hair pulled back, easy smile"),
    Contractor("Luis Romero", "+14155550105", "luis.romero@example.com", 26, ("server", "runner"),
        "Excelsior", 5.2, 25.00, 88, "fast", ("English", "Spanish"), (),
        "Bilingual, quick on his feet during peak hours.",
        "a 26-year-old Mexican-American man with short dark hair, friendly grin"),
    Contractor("Ashley Brooks", "+14155550106", "ashley.brooks@example.com", 30, ("event_captain", "host"),
        "Castro", 2.4, 34.00, 94, "fast", ("English",), ("CPR",),
        "Strong with high-end private clients.",
        "a 30-year-old white woman with shoulder-length blonde hair, poised warm smile"),
    Contractor("Marcus Johnson", "+14155550107", "marcus.j@example.com", 41, ("security",),
        "Bayview", 6.1, 30.00, 99, "fast", ("English",), ("Guard Card", "CPR", "First Aid"),
        "Twelve years event security, never a no-show.",
        "a 41-year-old Black man with a clean-shaven head, calm steady gaze"),
    Contractor("Sofia Hernandez", "+14155550108", "sofia.h@example.com", 27, ("bartender", "host"),
        "Mission", 1.7, 29.00, 92, "fast", ("English", "Spanish"), ("TIPS",),
        "Lead bartender at two Mission spots.",
        "a 27-year-old Latina woman with dark wavy shoulder-length hair, bright friendly smile"),
    Contractor("Hiroshi Tanaka", "+14155550109", "hiroshi.t@example.com", 36, ("sushi_cook", "prep_cook"),
        "Japantown", 3.5, 33.00, 96, "average", ("English", "Japanese"), ("ServSafe",),
        "Trained at omakase counters, precise prep.",
        "a 36-year-old Japanese man with short black hair, focused thoughtful look"),
    Contractor("Melanie Cole", "+14155550110", "melanie.cole@example.com", 24, ("server",),
        "Chinatown", 3.1, 25.00, 89, "average", ("English",), (),
        "Front-of-house at busy dim sum service.",
        "a 24-year-old white woman with blonde hair in a clean ponytail, warm reserved smile"),
    Contractor("Joaquin Vega", "+14155550111", "joaquin.v@example.com", 38, ("line_cook",),
        "Outer Mission", 5.6, 31.00, 93, "fast", ("English", "Spanish"), ("ServSafe",),
        "Anchors line for taquerias and pop-ups.",
        "a 38-year-old Mexican-American man with short dark hair, grounded confident look"),
    Contractor("Naomi Park", "+14155550112", "naomi.park@example.com", 28, ("event_captain", "host"),
        "Hayes Valley", 2.2, 35.00, 95, "fast", ("English", "Korean"), ("CPR",),
        "Boutique-event captain, detail-obsessed.",
        "a 28-year-old Korean-American woman with sleek bob haircut, polished friendly smile"),
    Contractor("Tyrese Carter", "+14155550113", "tyrese.c@example.com", 25, ("dj", "av_tech"),
        "Western Addition", 3.9, 40.00, 86, "average", ("English",), (),
        "Versatile DJ, runs his own audio.",
        "a 25-year-old Black man with short twists, headphones around neck, easy creative vibe"),
    Contractor("Sienna Bishop", "+14155550114", "sienna.b@example.com", 29, ("photographer",),
        "Dogpatch", 4.2, 45.00, 91, "fast", ("English",), (),
        "Editorial event photographer, fast turnaround.",
        "a 29-year-old white woman with curly auburn hair, thoughtful warm smile"),
    Contractor("Amir Khan", "+14155550115", "amir.khan@example.com", 32, ("security",),
        "Tenderloin", 2.5, 30.00, 97, "fast", ("English", "Urdu", "Punjabi"), ("Guard Card", "CPR"),
        "Big venue specialist, calm de-escalation.",
        "a 32-year-old Pakistani-American man with short dark hair and a trimmed beard, steady look"),
    Contractor("Camila Souza", "+14155550116", "camila.s@example.com", 31, ("server", "host"),
        "North Beach", 3.0, 26.00, 90, "fast", ("English", "Portuguese"), (),
        "Hospitality lead at an Italian café.",
        "a 31-year-old Brazilian woman with long brown wavy hair, bright open smile"),
    Contractor("Diego Mendoza", "+14155550117", "diego.m@example.com", 27, ("barback", "runner"),
        "Mission", 1.6, 24.00, 84, "average", ("English", "Spanish"), (),
        "Energetic, reliable backup for bar service.",
        "a 27-year-old Mexican-American man with short curly hair, friendly grin"),
    Contractor("Lin Nguyen", "+14155550118", "lin.nguyen@example.com", 35, ("prep_cook", "line_cook"),
        "Sunset", 5.4, 28.00, 96, "fast", ("English", "Vietnamese"), ("ServSafe",),
        "Pho house prep lead, very fast hands.",
        "a 35-year-old Vietnamese-American woman with shoulder-length straight hair, gentle smile"),
    Contractor("Ben Goldberg", "+14155550119", "ben.goldberg@example.com", 39, ("event_captain",),
        "Pacific Heights", 3.7, 36.00, 94, "average", ("English",), ("CPR",),
        "Captains gallery openings and donor dinners.",
        "a 39-year-old white Jewish man with short brown hair and a trimmed beard, warm professional look"),
    Contractor("Aaliyah Brooks", "+14155550120", "aaliyah.b@example.com", 26, ("bartender",),
        "SoMa", 2.0, 30.00, 93, "fast", ("English",), ("TIPS",),
        "Craft cocktail experience, popular with regulars.",
        "a 26-year-old Black woman with long box braids, confident bright smile"),
    Contractor("Connor Walsh", "+14155550121", "connor.w@example.com", 31, ("mover", "driver"),
        "Sunset", 5.8, 26.00, 88, "fast", ("English",), ("Clean Driving Record",),
        "Strong, careful with venue load-ins.",
        "a 31-year-old white Irish-American man with short red-brown hair, friendly grounded look"),
    Contractor("Sarah Goldfarb", "+14155550122", "sarah.g@example.com", 33, ("pastry_cook",),
        "Hayes Valley", 2.3, 32.00, 95, "fast", ("English",), ("ServSafe",),
        "Wedding-cake specialist with event experience.",
        "a 33-year-old white Jewish woman with curly brown hair pulled back, warm focused smile"),
    Contractor("Kenji Sato", "+14155550123", "kenji.sato@example.com", 29, ("bartender", "mixologist"),
        "North Beach", 3.1, 34.00, 96, "fast", ("English", "Japanese"), ("TIPS",),
        "Award-winning mixologist, custom menus on request.",
        "a 29-year-old Japanese-American man with short stylish hair, calm confident smile"),
    Contractor("Liana Costa", "+14155550124", "liana.costa@example.com", 26, ("server",),
        "North Beach", 3.0, 25.00, 87, "average", ("English", "Italian"), (),
        "Trattoria service background, strong with wine.",
        "a 26-year-old Italian-American woman with long dark brown hair, polished warm smile"),
    Contractor("Devon Thomas", "+14155550125", "devon.t@example.com", 36, ("runner", "av_tech"),
        "Bayview", 6.2, 24.00, 91, "average", ("English",), (),
        "Production runner with on-the-fly AV chops.",
        "a 36-year-old Black man with short hair and a small beard, capable hands-on look"),
    Contractor("Yuki Nakamura", "+14155550126", "yuki.n@example.com", 24, ("server", "host"),
        "Japantown", 3.4, 25.00, 92, "fast", ("English", "Japanese"), (),
        "Tea-ceremony precision in service.",
        "a 24-year-old Japanese woman with shoulder-length straight hair, soft welcoming smile"),
    Contractor("Imani Foster", "+14155550127", "imani.f@example.com", 30, ("line_cook", "prep_cook"),
        "Western Addition", 4.0, 30.00, 93, "fast", ("English",), ("ServSafe",),
        "Lead line cook at neighborhood brunch spot.",
        "a 30-year-old Black woman with locs pulled back, focused confident expression"),
    Contractor("Anders Lindqvist", "+14155550128", "anders.l@example.com", 35, ("bartender", "mixologist"),
        "Marina", 3.6, 34.00, 95, "average", ("English", "Swedish"), ("TIPS",),
        "Nordic-style cocktail menus.",
        "a 35-year-old Swedish man with short blonde hair, calm precise expression"),
    Contractor("Eduardo Salgado", "+14155550129", "eduardo.s@example.com", 42, ("security",),
        "Mission", 1.8, 32.00, 98, "fast", ("English", "Spanish"), ("Guard Card", "CPR", "First Aid"),
        "Lead security for major venues across the city.",
        "a 42-year-old Latino man with short salt-and-pepper hair, steady reassuring look"),
    Contractor("Anjali Mehta", "+14155550130", "anjali.m@example.com", 28, ("photographer", "videographer"),
        "Mission", 2.0, 44.00, 89, "average", ("English", "Hindi"), (),
        "Documentary-style event coverage.",
        "a 28-year-old South Asian woman with long dark hair, thoughtful creative smile"),
    Contractor("Khalil Stewart", "+14155550131", "khalil.s@example.com", 27, ("server", "barback"),
        "Hayes Valley", 2.4, 25.00, 86, "fast", ("English",), (),
        "Cocktail-focused server, growing into bar.",
        "a 27-year-old Black man with short hair and goatee, warm engaged smile"),
    Contractor("Olivia Brennan", "+14155550132", "olivia.b@example.com", 33, ("event_captain",),
        "Marina", 3.5, 35.00, 96, "fast", ("English",), ("CPR",),
        "Corporate-event captain, handles VIP rooms.",
        "a 33-year-old white Irish-American woman with auburn hair in a low ponytail, composed smile"),
    Contractor("Min-Jun Lee", "+14155550133", "minjun.l@example.com", 31, ("line_cook",),
        "SoMa", 2.2, 30.00, 94, "fast", ("English", "Korean"), ("ServSafe",),
        "KBBQ and modern Korean kitchens.",
        "a 31-year-old Korean man with short black hair, focused friendly look"),
    Contractor("Fatima Hassan", "+14155550134", "fatima.h@example.com", 29, ("server", "host"),
        "Tenderloin", 2.7, 28.00, 95, "fast", ("English", "Somali", "Arabic"), (),
        "Multilingual hospitality lead, very polished.",
        "a 29-year-old Somali-American woman wearing a soft cream headscarf, gracious confident smile"),
    Contractor("Jamal Carter", "+14155550135", "jamal.c@example.com", 38, ("valet", "driver"),
        "Pacific Heights", 3.8, 26.00, 97, "fast", ("English",), ("Clean Driving Record", "CPR"),
        "Valets exotic and classic cars, spotless record.",
        "a 38-year-old Black man with short hair and a neat beard, professional polished look"),
    Contractor("Ana Lucia Diaz", "+14155550136", "ana.diaz@example.com", 25, ("barback", "runner"),
        "Excelsior", 5.1, 22.00, 82, "average", ("English", "Spanish"), (),
        "Fast learner, picks up urgent shifts.",
        "a 25-year-old Latina woman with shoulder-length wavy hair, bright energetic smile"),
    Contractor("Theo Beaumont", "+14155550137", "theo.b@example.com", 30, ("photographer",),
        "Castro", 2.6, 46.00, 90, "average", ("English", "French"), (),
        "Lifestyle photographer with strong event eye.",
        "a 30-year-old white man with light brown hair and stubble, easy creative smile"),
]


PROMPT_TEMPLATE = (
    "Editorial-quality professional headshot portrait of {appearance}, working as a {role}. "
    "Wearing {attire}. Warm natural studio lighting, soft cream background, looking directly at "
    "camera, head-and-shoulders framing, photorealistic, magazine quality, sharp focus. "
    "No text, no logos, no watermarks."
)


def build_prompt(c: Contractor) -> str:
    role = c.skills[0].replace("_", " ")
    return PROMPT_TEMPLATE.format(appearance=c.appearance, role=role, attire=c.attire)


async def generate_portrait(client: httpx.AsyncClient, c: Contractor) -> Path | None:
    out_path = PORTRAITS_DIR / f"{c.slug}.jpg"
    if out_path.exists():
        return out_path
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}"
        f":generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": build_prompt(c)}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    for attempt in range(3):
        try:
            r = await client.post(url, json=payload, timeout=120)
            if r.status_code == 200:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                b64 = next((p["inlineData"]["data"] for p in parts if "inlineData" in p), None)
                if b64:
                    out_path.write_bytes(base64.b64decode(b64))
                    return out_path
                print(f"  no image in response for {c.name}: {data}")
            else:
                print(f"  HTTP {r.status_code} for {c.name}: {r.text[:200]}")
        except httpx.HTTPError as e:
            print(f"  attempt {attempt + 1} failed for {c.name}: {e}")
        await asyncio.sleep(2 + attempt * 3)
    return None


async def upsert_contractor(c: Contractor, avatar_path: str | None) -> None:
    insert_sql = """
        INSERT INTO contractors
          (name, phone, email, age, location, distance_miles, hourly_rate,
           reliability_score, response_speed, languages, certifications, notes, avatar_path)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (phone) DO UPDATE SET
          name = EXCLUDED.name,
          email = EXCLUDED.email,
          age = EXCLUDED.age,
          location = EXCLUDED.location,
          distance_miles = EXCLUDED.distance_miles,
          hourly_rate = EXCLUDED.hourly_rate,
          reliability_score = EXCLUDED.reliability_score,
          response_speed = EXCLUDED.response_speed,
          languages = EXCLUDED.languages,
          certifications = EXCLUDED.certifications,
          notes = EXCLUDED.notes,
          avatar_path = COALESCE(EXCLUDED.avatar_path, contractors.avatar_path)
        RETURNING id
    """
    skills_sql = """
        INSERT INTO contractor_skills (contractor_id, skill)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                insert_sql,
                c.name, c.phone, c.email, c.age, c.location, c.distance_miles,
                c.hourly_rate, c.reliability_score, c.response_speed,
                list(c.languages), list(c.certifications), c.notes, avatar_path,
            )
            cid = row["id"]
            for skill in c.skills:
                await conn.execute(skills_sql, cid, skill)


async def main() -> None:
    await db.connect()
    try:
        async with httpx.AsyncClient() as http:
            for i, c in enumerate(ROSTER, 1):
                print(f"[{i:2d}/{len(ROSTER)}] {c.name} ({', '.join(c.skills)})")
                portrait = await generate_portrait(http, c)
                avatar = f"/static/portraits/{portrait.name}" if portrait else None
                await upsert_contractor(c, avatar)
        async with db.pool().acquire() as conn:
            total = await conn.fetchval("SELECT count(*) FROM contractors")
            skills = await conn.fetchval("SELECT count(DISTINCT skill) FROM contractor_skills")
        print(f"\nDone. {total} contractors in DB across {skills} distinct skills.")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
