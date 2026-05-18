import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import ai, bulk_outreach, db, event_plan, invoice_email


logger = logging.getLogger("crewloop.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


class Turn(BaseModel):
    role: str = Field(..., pattern="^(user|model|assistant)$")
    text: str


class Attachment(BaseModel):
    mime_type: str
    data: str  # base64-encoded bytes
    name: str | None = None


class ChatRequest(BaseModel):
    turns: list[Turn] = Field(..., min_length=1)
    attachments: list[Attachment] = Field(default_factory=list)
    structured: bool = Field(
        default=True,
        description="When true (default) the response carries event_draft + action_chips + shortlist.",
    )


class ActionChip(BaseModel):
    label: str
    say: str


class EventDraft(BaseModel):
    event_type: str | None = None
    business_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    guest_count: int | None = None
    pay_amount: float | None = None
    urgency: str | None = None
    required_roles: list[str] = Field(default_factory=list)


class EventPlan(BaseModel):
    event_name: str
    details: str
    event_date: str
    event_time: str
    location: str | None = None
    staff_requirement: str
    responsibilities: str
    inventory_requirement: str
    estimated_labor: str
    invoice_amount: str
    approval_question: str


class BulkOutreachCounts(BaseModel):
    needed: int
    filled: int
    live_texts: int
    live_calls: int
    simulated_replies: int
    declined: int


class BulkOutreachRow(BaseModel):
    name: str
    role: str
    channel: str
    phone_last4: str = ""
    status: str
    response: str
    live: bool = False
    delivery_status: str = ""


class BulkOutreachSnapshot(BaseModel):
    title: str
    tag: str
    status: str
    summary: str
    counts: BulkOutreachCounts
    rows: list[BulkOutreachRow] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class InvoiceLineItem(BaseModel):
    label: str
    amount: str


class InvoiceInventoryItem(BaseModel):
    name: str
    qty: str
    amount: str


class InvoiceEmailReceipt(BaseModel):
    label: str
    to: str
    subject: str
    status: str
    provider: str
    id: str | None = None
    detail: str


class SpongeWalletSnapshot(BaseModel):
    name: str
    role: str
    arrival: str
    shift: str
    pay: str
    wallet_id: str
    status: str
    release_rules: list[str] = Field(default_factory=list)


class InvoiceEmailSnapshot(BaseModel):
    title: str
    tag: str
    status: str
    summary: str
    event: dict[str, str]
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    inventory_items: list[InvoiceInventoryItem] = Field(default_factory=list)
    total: str
    deposit: str
    balance_due: str
    emails: list[InvoiceEmailReceipt] = Field(default_factory=list)
    wallets: list[SpongeWalletSnapshot] = Field(default_factory=list)
    cancellation_policy: str
    evidence: list[str] = Field(default_factory=list)


class ShortlistEntry(BaseModel):
    id: str | None = None
    name: str
    avatar_path: str | None = None
    skills: list[str] = Field(default_factory=list)
    reliability_score: int | None = None
    distance_miles: float | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: str | None = None
    event_draft: EventDraft | None = None
    event_plan: EventPlan | None = None
    bulk_outreach: BulkOutreachSnapshot | None = None
    invoice_email: InvoiceEmailSnapshot | None = None
    action_chips: list[ActionChip] = Field(default_factory=list)
    shortlist: list[ShortlistEntry] = Field(default_factory=list)


# ----- helpers ---------------------------------------------------------------

async def _fetch_contractor_names_and_lookup() -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Return (names_for_prompt, lookup_by_lowercase_name)."""
    sql = """
        SELECT id, name, avatar_path, reliability_score, distance_miles,
               COALESCE(
                 (SELECT array_agg(skill ORDER BY skill)
                  FROM contractor_skills WHERE contractor_id = contractors.id),
                 '{}'::text[]
               ) AS skills
        FROM contractors
        ORDER BY reliability_score DESC
        LIMIT 200
    """
    try:
        async with db.pool().acquire() as conn:
            rows = await conn.fetch(sql)
    except Exception:
        return [], {}
    names: list[str] = []
    by_name: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        if d.get("distance_miles") is not None:
            d["distance_miles"] = float(d["distance_miles"])
        names.append(d["name"])
        by_name[d["name"].lower().strip()] = d
    return names, by_name


async def _fetch_open_events() -> list[dict[str, Any]]:
    sql = """
        SELECT role, start_time, status FROM jobs
        WHERE status NOT IN ('completed', 'cancelled')
        ORDER BY created_at DESC LIMIT 12
    """
    try:
        async with db.pool().acquire() as conn:
            rows = await conn.fetch(sql)
        return [dict(r) for r in rows]
    except Exception:
        return []


def _resolve_shortlist(names: list[str], lookup: dict[str, dict[str, Any]]) -> list[ShortlistEntry]:
    out: list[ShortlistEntry] = []
    for raw in names:
        key = (raw or "").lower().strip()
        c = lookup.get(key)
        if c:
            out.append(ShortlistEntry(
                id=str(c["id"]),
                name=c["name"],
                avatar_path=c.get("avatar_path"),
                skills=list(c.get("skills") or []),
                reliability_score=c.get("reliability_score"),
                distance_miles=c.get("distance_miles"),
            ))
        else:
            out.append(ShortlistEntry(name=raw))
    return out


# ----- route -----------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat_with_loop(payload: ChatRequest) -> ChatResponse:
    turns = [{"role": "user" if t.role != "model" else "model", "text": t.text} for t in payload.turns]
    attachments = [a.model_dump() for a in payload.attachments]

    if not payload.structured:
        # Legacy text-only path. Keep behaviour for any callers that opt out.
        try:
            reply = await ai.generate_chat_reply(turns, attachments=attachments or None)
        except Exception:
            logger.exception("chat reply failed")
            raise HTTPException(status_code=502, detail="Loop couldn't reach Gemini")
        if not reply:
            raise HTTPException(status_code=502, detail="Loop returned no reply")
        return ChatResponse(reply=reply)

    latest_text = event_plan.latest_user_text(turns)
    if event_plan.is_plan_approval(latest_text):
        return ChatResponse(
            reply=(
                "Approved. I’ll shortlist the 10-person crew next, then wait for your approval "
                "before outreach, supplies, invoice, and payment holds."
            ),
            intent="event_plan_approved",
            action_chips=[
                ActionChip(label="Shortlist crew", say="Shortlist the best crew for this event"),
                ActionChip(label="Edit plan", say="I want to edit the event plan first"),
            ],
        )

    if invoice_email.is_invoice_send_request(latest_text):
        result = InvoiceEmailSnapshot(**await invoice_email.send_invoice_emails(send_real=True))
        return ChatResponse(
            reply=(
                "The AgentMail invoice packet is complete. It includes the owner spend log, "
                "customer invoice, and contractor schedule packet with Sponge wallet ids."
            ),
            intent="invoice_email_sent",
            invoice_email=result,
            action_chips=[
                ActionChip(label="Set payment holds", say="Set Sponge payment holds for the finalized roster"),
                ActionChip(label="Owner approval", say="Prepare the owner approval step before payout release"),
            ],
        )

    if invoice_email.is_invoice_preview_request(latest_text):
        preview = InvoiceEmailSnapshot(**invoice_email.build_invoice_preview())
        return ChatResponse(
            reply=(
                "I prepared the invoice and AgentMail packet. Review the totals, email targets, "
                "and Sponge wallet setup before sending."
            ),
            intent="invoice_email_ready",
            invoice_email=preview,
            action_chips=[
                ActionChip(label="Send emails", say="Send the AgentMail invoice emails now"),
                ActionChip(label="Edit invoice", say="Edit the invoice amount before sending"),
            ],
        )

    if bulk_outreach.is_bulk_outreach_start(latest_text):
        result = BulkOutreachSnapshot(**await bulk_outreach.execute_bulk_outreach(send_real=True))
        return ChatResponse(
            reply=(
                "Bulk outreach is complete. I contacted the live targets, simulated the remaining "
                "replies, filled the backup slot, and finalized the roster."
            ),
            intent="bulk_outreach_sent",
            bulk_outreach=result,
            action_chips=[
                ActionChip(label="Set schedule", say="Create the event schedule for the finalized roster"),
                ActionChip(label="Prepare invoice", say="Prepare the client invoice next"),
            ],
        )

    if bulk_outreach.is_shortlist_request(latest_text):
        plan = BulkOutreachSnapshot(**bulk_outreach.build_bulk_outreach_plan())
        return ChatResponse(
            reply=(
                "I have the 10-person shortlist ready. Approve bulk outreach and I’ll text the "
                "three live contacts, call the event lead, then simulate the remaining replies."
            ),
            intent="bulk_outreach_ready",
            bulk_outreach=plan,
            action_chips=[
                ActionChip(label="Start outreach", say="Start bulk outreach now"),
                ActionChip(label="Edit roster", say="Edit the contractor roster before outreach"),
            ],
        )

    inferred_plan = event_plan.infer_event_plan(latest_text)
    if inferred_plan:
        plan = EventPlan(**inferred_plan)
        return ChatResponse(
            reply=(
                "Here’s the concise event plan I inferred. If this looks right, approve it "
                "and I’ll move to crew shortlisting."
            ),
            intent="event_plan",
            event_plan=plan,
            action_chips=[
                ActionChip(label="Approve plan", say="Approve this event plan"),
                ActionChip(label="Edit staff", say="Change the staff requirement"),
                ActionChip(label="Change budget", say="Change the invoice amount"),
            ],
        )

    contractor_names, lookup = await _fetch_contractor_names_and_lookup()
    open_events = await _fetch_open_events()

    try:
        result = await ai.generate_chat_action_reply(
            turns,
            attachments=attachments or None,
            contractor_names=contractor_names,
            open_events=open_events,
        )
    except Exception:
        logger.exception("structured chat reply failed")
        raise HTTPException(status_code=502, detail="Loop couldn't reach Gemini")

    if not result:
        raise HTTPException(status_code=502, detail="Loop returned no reply")

    reply_text = (result.get("reply_text") or "").strip()
    if not reply_text:
        raise HTTPException(status_code=502, detail="Loop returned empty reply")

    raw_draft = result.get("event_draft") or None
    draft = EventDraft(**raw_draft) if isinstance(raw_draft, dict) else None
    chips = [ActionChip(**c) for c in (result.get("action_chips") or []) if isinstance(c, dict)]
    shortlist_names = [s for s in (result.get("shortlist") or []) if isinstance(s, str)]
    shortlist = _resolve_shortlist(shortlist_names, lookup)

    return ChatResponse(
        reply=reply_text,
        intent=result.get("intent") or None,
        event_draft=draft,
        action_chips=chips,
        shortlist=shortlist,
    )
