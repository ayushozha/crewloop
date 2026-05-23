import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import (
    ai,
    bulk_outreach,
    db,
    event_plan,
    invoice_email,
    repo,
    schedule as schedule_mod,
    supermemory_client,
    supplies_card,
)


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
    thread_id: UUID | None = None
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
    source_event_id: str | None = None
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


class ScheduleRow(BaseModel):
    name: str
    role: str
    call_time: str
    shift: str
    station: str
    pay: str
    phone_last4: str = ""
    live: bool = False


class ScheduleTotals(BaseModel):
    crew: int
    labor: str
    arrive_by: str
    live_confirmed: int = 0


class ScheduleSnapshot(BaseModel):
    title: str
    tag: str
    status: str
    summary: str
    event: dict[str, str]
    rows: list[ScheduleRow] = Field(default_factory=list)
    totals: ScheduleTotals
    evidence: list[str] = Field(default_factory=list)


class SupplyItem(BaseModel):
    name: str
    qty: str
    note: str = ""
    amount: str = ""


class SuppliesSnapshot(BaseModel):
    title: str
    tag: str
    status: str
    summary: str
    event_id: str | None = None
    open_link: str
    items: list[SupplyItem] = Field(default_factory=list)
    total: str
    vendors: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    thread_id: UUID | None = None
    reply: str
    intent: str | None = None
    event_draft: EventDraft | None = None
    event_plan: EventPlan | None = None
    bulk_outreach: BulkOutreachSnapshot | None = None
    invoice_email: InvoiceEmailSnapshot | None = None
    schedule: ScheduleSnapshot | None = None
    supplies: SuppliesSnapshot | None = None
    action_chips: list[ActionChip] = Field(default_factory=list)
    shortlist: list[ShortlistEntry] = Field(default_factory=list)


class CreateChatThreadRequest(BaseModel):
    title: str | None = None
    initial_message: str | None = Field(default=None, max_length=5000)


class ChatThreadRecord(BaseModel):
    id: UUID
    title: str
    summary: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: str | None = None
    last_role: str | None = None


class ChatMessageRecord(BaseModel):
    id: UUID
    thread_id: UUID
    role: str
    body: str
    payload: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ChatThreadDetail(BaseModel):
    thread: ChatThreadRecord
    messages: list[ChatMessageRecord] = Field(default_factory=list)


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


async def _latest_event_id() -> str | None:
    """Most-recent jobs row — used to deep-link to /events/{id}/supplies."""
    if not db.available():
        return None
    try:
        async with db.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM jobs ORDER BY created_at DESC LIMIT 1"
            )
        return str(row["id"]) if row else None
    except Exception:
        return None


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


def _thread_title_from_text(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return "New operation"
    lowered = cleaned.lower()
    if "corporate dinner" in lowered:
        return "Corporate dinner"
    if "bartender" in lowered:
        return "Bartender shift"
    if "invoice" in lowered:
        return "Invoice follow-up"
    if "inventory" in lowered or "supplies" in lowered:
        return "Inventory run"
    return cleaned[:54] + ("…" if len(cleaned) > 54 else "")


def _money_number(value: str) -> float:
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _time_parts(time_window: str) -> tuple[str, str]:
    if " - " in time_window:
        start, end = time_window.split(" - ", 1)
        return start.strip(), end.strip()
    if "–" in time_window:
        start, end = time_window.split("–", 1)
        return start.strip(), end.strip()
    return time_window, ""


async def _persist_event_record(plan: dict[str, Any]) -> str | None:
    if not db.available():
        return None
    start, end = _time_parts(str(plan.get("event_time") or ""))
    description = (
        f"{plan.get('details')}\n\n"
        f"Crew: {plan.get('staff_requirement')}\n"
        f"Supplies: {plan.get('inventory_requirement')}\n"
        f"Invoice: {plan.get('invoice_amount')}"
    )
    sql = """
        INSERT INTO jobs (business_name, role, description, location, start_time,
                          end_time, pay_amount, urgency, required_skills, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10)
        RETURNING id
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            sql,
            "Bay Events Co.",
            str(plan.get("event_name") or "Event"),
            description,
            str(plan.get("location") or "TBD"),
            f"{plan.get('event_date')}, {start}".strip(", "),
            end or str(plan.get("event_time") or ""),
            _money_number(str(plan.get("estimated_labor") or "")),
            "standard",
            ["bartending", "serving", "setup", "cleanup", "event lead"],
            "plan_ready",
        )
    return str(row["id"]) if row else None


def _latest_event_plan_name(turns: list[dict[str, str]]) -> str | None:
    for turn in reversed(turns):
        text = (turn.get("text") or "").strip()
        for line in text.splitlines():
            if line.lower().startswith("event plan:"):
                name = line.split(":", 1)[1].strip()
                if name:
                    return name
    return None


async def _mark_latest_plan_approved(turns: list[dict[str, str]]) -> str | None:
    if not db.available():
        return None
    plan_name = _latest_event_plan_name(turns)
    if not plan_name:
        return None
    sql = """
        WITH target AS (
          SELECT id
          FROM jobs
          WHERE lower(role) = lower($1)
            AND status NOT IN ('completed', 'cancelled')
          ORDER BY created_at DESC
          LIMIT 1
        )
        UPDATE jobs
        SET status = 'approved'
        WHERE id = (SELECT id FROM target)
        RETURNING id
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, plan_name)
    return str(row["id"]) if row else None


def _latest_user_turn(payload: ChatRequest) -> Turn | None:
    for turn in reversed(payload.turns):
        if turn.role == "user" and turn.text.strip():
            return turn
    return None


def _assistant_body(response: ChatResponse) -> str:
    if response.event_plan:
        return response.reply or f"Event plan ready: {response.event_plan.event_name}"
    if response.bulk_outreach:
        return response.reply or response.bulk_outreach.summary
    if response.schedule:
        return response.reply or response.schedule.summary
    if response.supplies:
        return response.reply or response.supplies.summary
    if response.invoice_email:
        return response.reply or response.invoice_email.summary
    return response.reply


async def _chat_thread_detail(thread_id: UUID | str) -> ChatThreadDetail:
    thread = await repo.get_chat_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="chat thread not found")
    messages = await repo.list_chat_messages(thread_id)
    enriched_thread = {
        **thread,
        "message_count": len(messages),
        "last_message": messages[-1]["body"] if messages else None,
        "last_role": messages[-1]["role"] if messages else None,
    }
    return ChatThreadDetail(thread=enriched_thread, messages=messages)


async def _append_user_turn(thread_id: UUID, payload: ChatRequest) -> None:
    latest = _latest_user_turn(payload)
    if not latest:
        return
    await repo.append_chat_message(
        thread_id=thread_id,
        role="user",
        body=latest.text.strip(),
        attachments=[a.model_dump() for a in payload.attachments],
    )


async def _append_assistant_response(thread_id: UUID, response: ChatResponse) -> None:
    await repo.append_chat_message(
        thread_id=thread_id,
        role="agent",
        body=_assistant_body(response),
        payload=response.model_dump(mode="json", exclude_none=True),
    )


async def _sync_supermemory_thread(thread_id: UUID | str) -> None:
    if not supermemory_client.enabled():
        return
    thread = await repo.get_chat_thread(thread_id)
    if not thread:
        return
    messages = await repo.list_chat_messages(thread_id)
    await supermemory_client.ingest_chat_thread(
        thread_id=str(thread_id),
        title=str(thread.get("title") or "CrewLoop chat"),
        messages=messages,
    )


def _schedule_supermemory_sync(thread_id: UUID | str) -> None:
    if not supermemory_client.enabled():
        return
    try:
        asyncio.create_task(_sync_supermemory_thread(thread_id))
    except RuntimeError:
        logger.warning("Could not schedule Supermemory sync for thread %s", thread_id)


# ----- route -----------------------------------------------------------------

async def _generate_chat_response(payload: ChatRequest) -> ChatResponse:
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
        await _mark_latest_plan_approved(turns)
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

    if event_plan.is_plan_edit_request(latest_text):
        return ChatResponse(
            reply="What should I change in the approved plan before outreach?",
            intent="event_plan_edit",
            action_chips=[
                ActionChip(label="Edit staffing", say="Change the staff requirement"),
                ActionChip(label="Edit supplies", say="Change the inventory requirement"),
                ActionChip(label="Edit invoice", say="Change the invoice amount"),
                ActionChip(label="Edit timing", say="Change the event date, time, or location"),
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

    if schedule_mod.is_schedule_request(latest_text):
        snapshot = ScheduleSnapshot(**schedule_mod.build_schedule_snapshot())
        return ChatResponse(
            reply=(
                "Schedule locked for the 10-person roster. Each contractor gets an SMS "
                "with their call time, station, and Sponge wallet id."
            ),
            intent="schedule_ready",
            schedule=snapshot,
            action_chips=[
                ActionChip(label="Recommend supplies", say="Recommend the supplies list for this event"),
                ActionChip(label="Prepare invoice", say="Prepare the client invoice next"),
            ],
        )

    if supplies_card.is_supplies_request(latest_text):
        latest_event_id = await _latest_event_id()
        snapshot = SuppliesSnapshot(**supplies_card.build_supplies_card(event_id=latest_event_id))
        return ChatResponse(
            reply=(
                "Here is the supply list. Open the Browser Use room to confirm vendor "
                "price + delivery, then pay through Sponge or Stripe."
            ),
            intent="supplies_ready",
            supplies=snapshot,
            action_chips=[
                ActionChip(label="Open Browser Use", say="Open the Browser Use supplies room"),
                ActionChip(label="Prepare invoice", say="Prepare the client invoice next"),
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

    inferred_plan = event_plan.infer_event_plan(latest_text)
    if inferred_plan:
        inferred_plan["source_event_id"] = await _persist_event_record(inferred_plan)
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


@router.get("/threads", response_model=dict[str, list[ChatThreadRecord]])
async def list_chat_threads(limit: int = 50) -> dict[str, list[ChatThreadRecord]]:
    return {"items": await repo.list_chat_threads(limit=limit)}


@router.post("/threads", response_model=ChatThreadDetail)
async def create_chat_thread(payload: CreateChatThreadRequest) -> ChatThreadDetail:
    initial_message = (payload.initial_message or "").strip()
    title = (payload.title or "").strip() or _thread_title_from_text(initial_message)
    thread = await repo.create_chat_thread(title=title, summary=initial_message[:140] or None)

    if initial_message:
        thread_id = thread["id"]
        await repo.append_chat_message(thread_id=thread_id, role="user", body=initial_message)
        response = await _generate_chat_response(
            ChatRequest(turns=[Turn(role="user", text=initial_message)], thread_id=thread_id)
        )
        response.thread_id = thread_id
        await _append_assistant_response(thread_id, response)
        _schedule_supermemory_sync(thread_id)

    return await _chat_thread_detail(thread["id"])


@router.get("/threads/{thread_id}", response_model=ChatThreadDetail)
async def get_chat_thread(thread_id: UUID) -> ChatThreadDetail:
    return await _chat_thread_detail(thread_id)


@router.post("", response_model=ChatResponse)
async def chat_with_loop(payload: ChatRequest) -> ChatResponse:
    if payload.thread_id:
        if not await repo.get_chat_thread(payload.thread_id):
            raise HTTPException(status_code=404, detail="chat thread not found")
        await _append_user_turn(payload.thread_id, payload)

    response = await _generate_chat_response(payload)

    if payload.thread_id:
        response.thread_id = payload.thread_id
        await _append_assistant_response(payload.thread_id, response)
        _schedule_supermemory_sync(payload.thread_id)

    return response
