"""Supplies inference + Browser Use vendor evidence simulation.

Spec §3 steps 9-10:
  9.  Infers a short supply list and asks owner approval before purchase.
  10. Uses Browser Use to check or simulate vendor checkout.

Pipeline:
  1. recommend_supplies(event) → Gemini, grounded against the existing
     inventory_items roster. Returns 3-5 line items (name, qty, unit,
     match_to_inventory_item_id, est_unit_price, vendor_hint, rationale).
  2. persist_supplies(event_id, items) → writes them to event_supplies in
     `recommended` status, joining the inventory row for image + unit cost
     when matched.
  3. simulate_vendor_checkout(supplies) → mocks a Browser Use cart-check:
     picks a plausible vendor per item, attaches a fake but believable
     vendor_url, an ETA window, and a short evidence_note describing what
     "the browser" found.

No actual outbound HTTP — Browser Use is paid + the spec marks "Inventory
store" as demo-controlled. The shape of the evidence object is the same one
real Browser Use returns so we can swap it in later.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from . import ai, db
from .config import settings


logger = logging.getLogger("crewloop.supplies")


# Vendors we pretend to have shopped against. Picked deterministically by item
# category so the demo is stable across reloads.
VENDOR_BY_CATEGORY: dict[str, dict[str, str]] = {
    "spirit": {"name": "K&L Wine Merchants", "host": "https://www.klwines.com"},
    "liqueur": {"name": "K&L Wine Merchants", "host": "https://www.klwines.com"},
    "wine": {"name": "K&L Wine Merchants", "host": "https://www.klwines.com"},
    "beer": {"name": "Bevmo SoMa", "host": "https://www.bevmo.com"},
    "mixer": {"name": "Restaurant Depot SF", "host": "https://www.restaurantdepot.com"},
    "syrup": {"name": "Cocktail Kingdom", "host": "https://www.cocktailkingdom.com"},
    "garnish": {"name": "Local Produce Co-op", "host": "https://www.bifoods.com"},
    "tool": {"name": "Cocktail Kingdom", "host": "https://www.cocktailkingdom.com"},
    "glassware": {"name": "WebstaurantStore", "host": "https://www.webstaurantstore.com"},
    "consumable": {"name": "WebstaurantStore", "host": "https://www.webstaurantstore.com"},
}
DEFAULT_VENDOR = {"name": "Restaurant Depot SF", "host": "https://www.restaurantdepot.com"}


SUPPLIES_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "rationale": {"type": "STRING"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "qty": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "match_sku": {"type": "STRING", "nullable": True},
                    "rationale": {"type": "STRING"},
                },
                "required": ["name", "qty", "unit"],
            },
        },
    },
    "required": ["items"],
}


SUPPLIES_PROMPT = """You are CrewLoop's supplies planner.

Given an event description, recommend a SHORT list of 3-5 supply items the
business needs to purchase ahead of the shift. Lean on the existing pantry —
prefer items already in our inventory, and only recommend things that
materially affect the event service (not "more napkins" if we have plenty).

Rules:
- 3-5 items total. Not more.
- Use SKUs from the provided pantry whenever an item matches. Put the SKU
  string in `match_sku`. Leave `match_sku` null only if nothing in the
  pantry is close.
- `qty` is the quantity to BUY (top-up), not what we have on hand.
- `unit` matches the pantry unit for matched items, otherwise a sensible
  default like "bottle" / "case" / "lb" / "each".
- Each item gets a one-line `rationale` describing why it's needed for
  THIS specific event (e.g. "60 cocktails at 1.5oz each").
- A short top-level `rationale` summarizes the supply plan in one sentence.

Never invent random brand names. If you can't tie an item to the pantry,
use a generic name like "Fresh lemons" or "Cocktail napkins".
"""


def _pantry_summary(items: list[dict[str, Any]], limit: int = 80) -> str:
    """Compact, model-friendly view of the inventory roster."""
    rows: list[str] = []
    # Bias toward items relevant to an event bar: prefer low-on-hand items first,
    # then alphabetical inside each category for stability.
    for item in items[:limit]:
        sku = item.get("sku")
        nm = item.get("name")
        cat = item.get("category")
        unit = item.get("unit")
        cost = item.get("unit_cost")
        rows.append(f"- {sku} · {nm} · {cat} · {unit} · ${cost}")
    return "\n".join(rows)


async def _load_pantry() -> list[dict[str, Any]]:
    sql = """
        SELECT id::text AS id, sku, name, category, unit, par_level, on_hand,
               reorder_point, unit_cost, image_path
        FROM inventory_items
        ORDER BY (on_hand <= reorder_point) DESC, category, name
        LIMIT 200
    """
    try:
        async with db.pool().acquire() as conn:
            rows = await conn.fetch(sql)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        for k in ("par_level", "on_hand", "reorder_point", "unit_cost"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        out.append(d)
    return out


def _event_brief(event: dict[str, Any]) -> str:
    """One-paragraph human description of the event for the planner."""
    pieces = []
    pieces.append(f"Role: {event.get('role')}")
    if event.get("description"):
        pieces.append(f"Detail: {event['description']}")
    if event.get("start_time") or event.get("end_time"):
        pieces.append(f"Window: {event.get('start_time')} → {event.get('end_time')}")
    if event.get("location"):
        pieces.append(f"Location: {event['location']}")
    if event.get("pay_amount") is not None:
        pieces.append(f"Pay budget: ${event['pay_amount']}")
    if event.get("urgency"):
        pieces.append(f"Urgency: {event['urgency']}")
    skills = event.get("required_skills") or []
    if skills:
        pieces.append(f"Required skills: {', '.join(skills)}")
    return " | ".join(pieces)


async def recommend_supplies(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Gemini's recommended supply list (not yet persisted).

    Each item: {name, qty, unit, match_sku|None, rationale, est_unit_price,
                pantry_match (full row or None)}.
    """
    pantry = await _load_pantry()
    by_sku = {p["sku"]: p for p in pantry}
    prompt = f"""Event brief:
{_event_brief(event)}

Available pantry (SKU · name · category · unit · unit_cost):
{_pantry_summary(pantry)}
"""
    raw = await ai._call_gemini_json(
        model=settings.gemini_model_pro,
        system_prompt=SUPPLIES_PROMPT,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        response_schema=SUPPLIES_SCHEMA,
        max_output_tokens=1800,
        temperature=0.4,
    )
    items: list[dict[str, Any]] = []
    if not raw:
        return _fallback_recommendation(event, pantry)
    try:
        parsed = json.loads(raw)
        raw_items = parsed.get("items") or []
    except json.JSONDecodeError:
        return _fallback_recommendation(event, pantry)
    for it in raw_items[:5]:
        sku = it.get("match_sku")
        match = by_sku.get(sku) if sku else None
        est = float(match["unit_cost"]) if match else _guess_price(it.get("name", ""))
        items.append({
            "name": it.get("name") or (match["name"] if match else "Supply item"),
            "qty": float(it.get("qty") or 1),
            "unit": it.get("unit") or (match["unit"] if match else "each"),
            "match_sku": sku,
            "pantry_match": match,
            "est_unit_price": est,
            "rationale": it.get("rationale") or "",
        })
    if not items:
        return _fallback_recommendation(event, pantry)
    return items


def _fallback_recommendation(event: dict[str, Any], pantry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Used when Gemini is unavailable. Picks a small bar-event supply set."""
    by_sku = {p["sku"]: p for p in pantry}
    picks = [
        ("SPR-2619", 2, "Top up well vodka for service."),
        ("LIQ-2700", 2, "Cointreau for margaritas."),
        ("MX-3097", 4, "Fresh lime juice — daily."),
        ("GR-3127", 2, "Cocktail napkins."),
        ("MX-1100", 6, "Tonic water for G&Ts."),
    ]
    out: list[dict[str, Any]] = []
    for sku, qty, why in picks:
        m = by_sku.get(sku)
        if not m:
            continue
        out.append({
            "name": m["name"],
            "qty": qty,
            "unit": m["unit"],
            "match_sku": sku,
            "pantry_match": m,
            "est_unit_price": float(m["unit_cost"]),
            "rationale": why,
        })
    return out[:5]


def _guess_price(name: str) -> float:
    """Rough fallback for items the model invented (no pantry match)."""
    lower = (name or "").lower()
    if any(t in lower for t in ("vodka", "tequila", "whiskey", "rum", "gin", "scotch")):
        return 28.0
    if "wine" in lower or "champagne" in lower:
        return 22.0
    if "beer" in lower or "case" in lower:
        return 32.0
    if "lime" in lower or "lemon" in lower or "orange" in lower:
        return 6.0
    if "napkin" in lower or "straw" in lower or "coaster" in lower:
        return 10.0
    return 12.0


async def persist_supplies(event_id: UUID | str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Write the recommended supplies to event_supplies. Replaces any existing
    recommendations for this event so re-running re-recommends cleanly."""
    delete_sql = "DELETE FROM event_supplies WHERE event_id = $1 AND status = 'recommended'"
    insert_sql = """
        INSERT INTO event_supplies
          (event_id, inventory_item_id, name, qty, unit, vendor, vendor_url,
           unit_price, total_price, status, image_path, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'recommended', $10, $11)
        RETURNING *
    """
    out: list[dict[str, Any]] = []
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(delete_sql, event_id)
            for it in items:
                match = it.get("pantry_match")
                inv_id = UUID(match["id"]) if match and match.get("id") else None
                vendor = _vendor_for_category(match.get("category") if match else None)
                unit_price = float(it.get("est_unit_price") or 0)
                qty = float(it.get("qty") or 0)
                total = round(unit_price * qty, 2)
                row = await conn.fetchrow(
                    insert_sql,
                    event_id, inv_id, it["name"], qty, it.get("unit", "each"),
                    vendor["name"], vendor["host"],
                    unit_price, total,
                    (match or {}).get("image_path"),
                    it.get("rationale"),
                )
                out.append(_row_to_dict(row))
    return out


async def list_supplies(event_id: UUID | str) -> list[dict[str, Any]]:
    sql = "SELECT * FROM event_supplies WHERE event_id = $1 ORDER BY created_at"
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, event_id)
    return [_row_to_dict(r) for r in rows]


async def simulate_vendor_checkout(event_id: UUID | str) -> list[dict[str, Any]]:
    """Flip all recommended supplies for this event to 'approved' and attach
    fake-but-shaped-like-real Browser Use vendor evidence.

    Mirrors what Browser Use's API would return: a vendor URL, a screenshot
    URL (we reuse the inventory item's photo), an ETA, and a one-line note.
    """
    update_sql = """
        UPDATE event_supplies SET
          status = 'approved',
          evidence_url = $2,
          evidence_eta = $3,
          evidence_note = $4,
          approved_at = now()
        WHERE id = $1
        RETURNING *
    """
    listing = await list_supplies(event_id)
    if not listing:
        return []
    out: list[dict[str, Any]] = []
    async with db.pool().acquire() as conn:
        for s in listing:
            if s["status"] != "recommended":
                out.append(s)
                continue
            eta = _eta_window(s.get("vendor", ""))
            evidence_url = s.get("vendor_url") or DEFAULT_VENDOR["host"]
            note = _evidence_note(s)
            row = await conn.fetchrow(update_sql, s["id"], evidence_url, eta, note)
            out.append(_row_to_dict(row))
    return out


def supplies_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(float(i.get("total_price") or 0) for i in items)
    vendors = sorted({i.get("vendor") for i in items if i.get("vendor")})
    status_set = {i.get("status") for i in items}
    return {
        "count": len(items),
        "total": round(total, 2),
        "vendors": vendors,
        "status": "approved" if status_set == {"approved"} else "recommended" if "recommended" in status_set else "mixed",
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _vendor_for_category(category: str | None) -> dict[str, str]:
    if not category:
        return DEFAULT_VENDOR
    return VENDOR_BY_CATEGORY.get(category, DEFAULT_VENDOR)


def _eta_window(vendor: str) -> str:
    """Deterministic, vendor-flavored ETA so the demo is stable."""
    seed = int(hashlib.sha256(vendor.encode("utf-8")).hexdigest(), 16) % 4
    options = ["Same-day · 4-hour window", "Tomorrow morning · 9-11 AM",
               "Tomorrow afternoon · 1-3 PM", "Same-day · evening drop"]
    return options[seed]


def _evidence_note(supply: dict[str, Any]) -> str:
    vendor = supply.get("vendor") or "vendor"
    name = supply.get("name") or "item"
    qty = supply.get("qty") or 0
    unit = supply.get("unit") or "each"
    total = supply.get("total_price") or 0
    return (
        f"Browser Use simulated checkout on {vendor}: confirmed {qty} {unit} "
        f"of {name} in cart at ${total:.2f}. Ready to dispatch on approval."
    )


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k in ("qty", "unit_price", "total_price"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    if d.get("id") is not None:
        d["id"] = str(d["id"])
    if d.get("event_id") is not None:
        d["event_id"] = str(d["event_id"])
    if d.get("inventory_item_id") is not None:
        d["inventory_item_id"] = str(d["inventory_item_id"])
    return d
