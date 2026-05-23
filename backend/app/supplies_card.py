"""Supplies-recommendation card for the owner chat demo.

The full Browser Use checkout flow lives at /events/{id}/supplies. This card
gives the owner the supply list inline and a CTA to open that page when they
are ready to actually browse vendors.
"""
from __future__ import annotations

from typing import Any


SUPPLY_ITEMS: list[dict[str, Any]] = [
    {"name": "Compostable cups (16 oz)", "qty": "100", "note": "BevMo or Costco — house run", "amount": "$22"},
    {"name": "Cocktail napkins", "qty": "100", "note": "Pack of 200, BevMo", "amount": "$8"},
    {"name": "Bag of ice", "qty": "4", "note": "Reddy Ice, deliver by 5:30 PM", "amount": "$28"},
    {"name": "Table linens", "qty": "2", "note": "Venue concierge rental", "amount": "$36"},
    {"name": "Bartender tool kit", "qty": "1", "note": "Owned kit – Madison brings", "amount": "$0"},
]


def is_supplies_request(text: str) -> bool:
    lower = text.lower()
    has_subject = "supplies" in lower or "inventory" in lower or "supply" in lower
    if not has_subject:
        return False
    return any(
        verb in lower
        for verb in (
            "recommend",
            "buy",
            "browse",
            "shop",
            "purchase",
            "open",
            "show",
            "list",
            "prepare",
            "start",
            "get",
            "order",
        )
    )


def build_supplies_card(event_id: str | None = None) -> dict[str, Any]:
    total = sum(int(item["amount"].lstrip("$")) for item in SUPPLY_ITEMS)
    return {
        "title": "Supply list – ready for vendor checkout",
        "tag": f"{len(SUPPLY_ITEMS)} items",
        "status": "ready",
        "summary": (
            "Lean supply list grounded against the bar inventory. The Browser Use room "
            "opens parallel vendor sessions so you can confirm price + delivery before paying."
        ),
        "event_id": event_id,
        "open_link": f"/events/{event_id}/supplies" if event_id else "/events",
        "items": SUPPLY_ITEMS,
        "total": f"${total:,}",
        "vendors": ["BevMo", "Costco", "Reddy Ice", "Venue concierge"],
        "evidence": [
            "Quantities sized for 80 guests, 10 staff.",
            "Tool kit reuse from Madison's owned bar kit – $0.",
            "Browser Use will run live sessions for BevMo + Reddy Ice; the venue rental is confirmed by phone.",
        ],
    }
