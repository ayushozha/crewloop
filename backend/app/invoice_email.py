"""Invoice and AgentMail packet for the chat demo flow.

The golden path intentionally sends exactly three email packets:
owner log, customer invoice, and contractor schedule/wallet packet.
"""
from __future__ import annotations

import copy
import hashlib
from html import escape
from typing import Any

from .config import settings
from .sponsors import send_agentmail


_EXECUTED_EMAIL_RESULT: dict[str, Any] | None = None


EVENT = {
    "name": "Corporate dinner",
    "details": "80-guest corporate dinner in SoMa, San Francisco.",
    "date": "This Saturday",
    "time": "6:00 PM - 11:00 PM",
    "location": "SoMa, San Francisco",
    "guests": "80",
}

LINE_ITEMS = [
    {"label": "Labor", "amount": 1450},
    {"label": "Supplies", "amount": 86},
    {"label": "Service fee", "amount": 220},
]

INVENTORY_ITEMS = [
    {"name": "Compostable cups", "qty": "100", "amount": 18},
    {"name": "Napkins", "qty": "100", "amount": 12},
    {"name": "Ice bags", "qty": "4", "amount": 24},
    {"name": "Tablecloths", "qty": "2", "amount": 20},
    {"name": "Bartender tool kit rental", "qty": "1", "amount": 12},
]

CONTRACTOR_ROSTER = [
    {"name": "Emma Carter", "role": "Event lead", "arrival": "5:30 PM", "shift": "5:30 PM - 11:30 PM", "pay": 175},
    {"name": "Madison Reed", "role": "Bartender", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 175},
    {"name": "Ashley Brooks", "role": "Server", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 125},
    {"name": "Olivia Parker", "role": "Bartender", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 175},
    {"name": "Claire Walsh", "role": "Server", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 125},
    {"name": "Harper Lane", "role": "Server", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 125},
    {"name": "Brooke Miller", "role": "Server", "arrival": "6:00 PM", "shift": "6:00 PM - 11:00 PM", "pay": 125},
    {"name": "Luis Romero", "role": "Setup crew", "arrival": "5:00 PM", "shift": "5:00 PM - 8:00 PM", "pay": 150},
    {"name": "Natalie Cole", "role": "Cleanup lead", "arrival": "10:30 PM", "shift": "10:30 PM - 11:30 PM", "pay": 150},
    {"name": "Taylor Adams", "role": "Setup crew", "arrival": "5:00 PM", "shift": "5:00 PM - 8:00 PM", "pay": 125},
]

RELEASE_RULES = [
    "Contractor confirms schedule",
    "On-site check-in required",
    "Shift completion proof required",
    "Owner approval required before release",
]

CANCELLATION_POLICY = (
    "Contractors must cancel at least 24 hours before the shift when possible. "
    "Late cancellations stay blocked for payout review unless the owner approves an exception."
)


def is_invoice_preview_request(text: str) -> bool:
    lower = text.lower()
    if "invoice" not in lower and "agentmail" not in lower:
        return False
    return any(word in lower for word in ("prepare", "preview", "draft", "next", "client invoice"))


def is_invoice_send_request(text: str) -> bool:
    lower = text.lower()
    return (
        ("send" in lower or "trigger" in lower or "run" in lower)
        and ("email" in lower or "agentmail" in lower or "invoice" in lower)
    )


def build_invoice_preview() -> dict[str, Any]:
    return _snapshot(
        title="Invoice + AgentMail preview",
        tag="ready",
        status="ready",
        summary=(
            "Ready to send the owner spend log, customer invoice, and contractor schedule "
            "packet after the event details and supply list are finalized."
        ),
        emails=_email_previews(),
        evidence=[
            "AgentMail packet prepared with owner log, client invoice, and contractor schedule email.",
            "Sponge wallet IDs are prepared per contractor with proof-and-approval release rules.",
        ],
    )


async def send_invoice_emails(*, send_real: bool = True) -> dict[str, Any]:
    global _EXECUTED_EMAIL_RESULT
    if _EXECUTED_EMAIL_RESULT is not None:
        result = copy.deepcopy(_EXECUTED_EMAIL_RESULT)
        result["evidence"] = result.get("evidence", []) + [
            "Duplicate AgentMail send avoided in this server session.",
        ]
        return result

    messages = _email_messages()
    sent: list[dict[str, Any]] = []
    for message in messages:
        receipt = await send_agentmail(
            to=message["to"],
            subject=message["subject"],
            text=message["text"],
            html=message["html"],
            send_real=send_real,
        )
        sent.append(
            {
                "label": message["label"],
                "to": message["to"],
                "subject": message["subject"],
                "status": receipt.get("status") or "unknown",
                "provider": receipt.get("provider") or "agentmail",
                "id": receipt.get("id"),
                "detail": receipt.get("reason") or receipt.get("error") or "AgentMail request accepted.",
            }
        )

    all_sent = all(item["status"] == "sent" for item in sent)
    any_failed = any(item["status"] == "failed" for item in sent)
    status = "failed" if any_failed else ("sent" if all_sent else "simulated")
    tag = "AgentMail sent" if status == "sent" else ("needs inbox" if status == "simulated" else "failed")
    summary = (
        "AgentMail sent the owner log, customer invoice, and contractor schedule packet."
        if status == "sent"
        else "AgentMail packet is simulated because a live AgentMail inbox id is not configured."
    )
    result = _snapshot(
        title="Invoice + AgentMail packet",
        tag=tag,
        status=status,
        summary=summary,
        emails=sent,
        evidence=[
            f"AgentMail base URL: {settings.agentmail_base_url}.",
            f"Sponge MCP wallet rules prepared at {settings.sponge_mcp_url}.",
            "Each contractor has an individual Sponge wallet id and proof-gated payout rule.",
        ],
    )
    _EXECUTED_EMAIL_RESULT = copy.deepcopy(result)
    return result


def _snapshot(
    *,
    title: str,
    tag: str,
    status: str,
    summary: str,
    emails: list[dict[str, Any]],
    evidence: list[str],
) -> dict[str, Any]:
    total = sum(item["amount"] for item in LINE_ITEMS)
    deposit = 500
    return {
        "title": title,
        "tag": tag,
        "status": status,
        "summary": summary,
        "event": EVENT,
        "line_items": [{"label": item["label"], "amount": _money(item["amount"])} for item in LINE_ITEMS],
        "inventory_items": [
            {"name": item["name"], "qty": item["qty"], "amount": _money(item["amount"])}
            for item in INVENTORY_ITEMS
        ],
        "total": _money(total),
        "deposit": _money(deposit),
        "balance_due": _money(total - deposit),
        "emails": emails,
        "wallets": _wallets(),
        "cancellation_policy": CANCELLATION_POLICY,
        "evidence": evidence,
    }


def _email_previews() -> list[dict[str, Any]]:
    return [
        {
            "label": "Owner spend log",
            "to": settings.owner_email,
            "subject": "CrewLoop event log: Corporate dinner ready",
            "status": "ready",
            "provider": "agentmail",
            "id": None,
            "detail": "Confirms money spent, items purchased, event details, invoice total, and roster.",
        },
        {
            "label": "Customer invoice",
            "to": "customer@example.com",
            "subject": "Invoice: Corporate dinner staffing and supplies - $1,756",
            "status": "ready",
            "provider": "agentmail",
            "id": None,
            "detail": "Sends invoice total, deposit request, balance due, labor, supplies, and service fee.",
        },
        {
            "label": "Contractor schedule packet",
            "to": "crew-schedule@example.com",
            "subject": "CrewLoop schedule packet: Corporate dinner",
            "status": "ready",
            "provider": "agentmail",
            "id": None,
            "detail": "Lists all contractors, shift pay, cancellation policy, and Sponge wallet ids.",
        },
    ]


def _email_messages() -> list[dict[str, Any]]:
    total = sum(item["amount"] for item in LINE_ITEMS)
    deposit = 500
    balance = total - deposit
    owner_text = "\n".join(
        [
            "CrewLoop event log",
            f"Event: {EVENT['name']}",
            f"Details: {EVENT['details']}",
            f"Date/time: {EVENT['date']}, {EVENT['time']}",
            f"Location: {EVENT['location']}",
            "",
            "Money spent / prepared:",
            *[f"- {item['label']}: {_money(item['amount'])}" for item in LINE_ITEMS],
            f"Total invoice: {_money(total)}",
            f"Deposit requested: {_money(deposit)}",
            f"Balance due: {_money(balance)}",
            "",
            "Items purchased:",
            *[f"- {item['qty']} {item['name']}: {_money(item['amount'])}" for item in INVENTORY_ITEMS],
            "",
            "Final crew:",
            *[f"- {c['name']}, {c['role']}, {c['shift']}, pay {_money(c['pay'])}" for c in CONTRACTOR_ROSTER],
        ]
    )
    invoice_text = "\n".join(
        [
            "Invoice for Corporate dinner",
            f"Event: {EVENT['details']}",
            f"Date/time: {EVENT['date']}, {EVENT['time']}",
            f"Location: {EVENT['location']}",
            "",
            *[f"{item['label']}: {_money(item['amount'])}" for item in LINE_ITEMS],
            f"Total: {_money(total)}",
            f"Deposit requested today: {_money(deposit)}",
            f"Balance due after event: {_money(balance)}",
            "",
            "CrewLoop will keep worker payouts held until check-in, proof of completion, and owner approval.",
        ]
    )
    schedule_text = "\n".join(
        [
            "CrewLoop contractor schedule packet",
            f"Event: {EVENT['name']} - {EVENT['date']}, {EVENT['time']}",
            f"Location: {EVENT['location']}",
            "",
            *[
                (
                    f"- {wallet['name']}: {wallet['role']}, {wallet['shift']}, pay {wallet['pay']}, "
                    f"Sponge wallet {wallet['wallet_id']}"
                )
                for wallet in _wallets()
            ],
            "",
            f"Cancellation policy: {CANCELLATION_POLICY}",
            "Payout release: check-in, shift completion proof, and owner approval.",
        ]
    )
    return [
        {
            "label": "Owner spend log",
            "to": settings.owner_email,
            "subject": "CrewLoop event log: Corporate dinner ready",
            "text": owner_text,
            "html": _html("CrewLoop event log", owner_text),
        },
        {
            "label": "Customer invoice",
            "to": "customer@example.com",
            "subject": "Invoice: Corporate dinner staffing and supplies - $1,756",
            "text": invoice_text,
            "html": _html("Corporate dinner invoice", invoice_text),
        },
        {
            "label": "Contractor schedule packet",
            "to": "crew-schedule@example.com",
            "subject": "CrewLoop schedule packet: Corporate dinner",
            "text": schedule_text,
            "html": _html("Contractor schedule packet", schedule_text),
        },
    ]


def _wallets() -> list[dict[str, Any]]:
    wallets = []
    for contractor in CONTRACTOR_ROSTER:
        slug = contractor["name"].lower().replace(" ", "-")
        digest = hashlib.sha256(f"{slug}:{EVENT['date']}:{EVENT['time']}".encode("utf-8")).hexdigest()[:10]
        wallets.append(
            {
                "name": contractor["name"],
                "role": contractor["role"],
                "arrival": contractor["arrival"],
                "shift": contractor["shift"],
                "pay": _money(contractor["pay"]),
                "wallet_id": f"spg_{digest}",
                "status": "hold_prepared",
                "release_rules": RELEASE_RULES,
            }
        )
    return wallets


def _html(title: str, text: str) -> str:
    body = "<br />".join(escape(line) for line in text.splitlines())
    return (
        "<div style=\"font-family:Inter,Arial,sans-serif;line-height:1.5;color:#161410\">"
        f"<h2>{escape(title)}</h2><p>{body}</p></div>"
    )


def _money(amount: int) -> str:
    return f"${amount:,}"
