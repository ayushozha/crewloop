import asyncio
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import repo
from ..dispatch_room import rank_contractors
from ..workflow import (
    accept_contractor,
    check_in_contractor,
    classify_contractor_reply,
    create_job_from_text,
    hold_payment_for_job,
    parse_job_request,
    rank_job_contractors,
    run_outreach,
    approve_release,
)


router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    request_text: str | None = Field(default=None, description="Owner SMS or free-form staffing request.")
    business_name: str = "Bay Events Co."
    role: str | None = None
    description: str | None = None
    location: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    pay_amount: float | None = None
    urgency: str | None = None
    required_skills: list[str] = Field(default_factory=list)


class OutreachRequest(BaseModel):
    contractor_id: str | None = None
    send_real: bool = False


class AcceptRequest(BaseModel):
    contractor_id: str | None = None
    response: str = "yes"
    send_real_email: bool = False


class CheckInRequest(BaseModel):
    contractor_id: str | None = None
    proof_type: str = "sms"
    content: str | None = "Arrived on site and checked in by SMS."


class ApproveReleaseRequest(BaseModel):
    owner_approved: bool = True
    execute_real_payment: bool = False
    send_real_email: bool = False


class EventRequest(BaseModel):
    type: str
    content: str
    status: str = "complete"
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserSourceRequest(BaseModel):
    source_url: str
    source_type: str = "staffing_portal"
    imported_fields: dict[str, Any]
    screenshot_url: str | None = None
    source_html_url: str | None = None
    extraction_confidence: float = 0.85
    update_status: str = "pending"
    browser_action_log: list[dict[str, Any]] = Field(default_factory=list)


async def _job_or_404(job_id: UUID) -> dict[str, Any]:
    job = await repo.get_job(job_id)
    if job:
        return job
    # Fallback: the repo layer falls back to a local JSON store for some demo
    # paths. Seeded events live in the real Postgres `jobs` table only, so try
    # there before giving up.
    from .. import db as _db
    try:
        async with _db.pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if row:
            d = dict(row)
            for k in ("id",):
                d[k] = str(d[k]) if d.get(k) is not None else d.get(k)
            if d.get("pay_amount") is not None:
                d["pay_amount"] = float(d["pay_amount"])
            return d
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="job not found")


@router.post("/jobs")
async def create_job(payload: CreateJobRequest) -> dict[str, Any]:
    if payload.request_text:
        parsed = parse_job_request(payload.request_text)
        job = await create_job_from_text(payload.request_text)
        return {"job": job, "parsed": parsed, "needs_clarification": bool(parsed["missing_fields"])}

    fields = {
        "business_name": payload.business_name,
        "role": payload.role or "",
        "description": payload.description,
        "location": payload.location or "",
        "start_time": payload.start_time or "",
        "end_time": payload.end_time or "",
        "pay_amount": payload.pay_amount or 0,
        "urgency": payload.urgency or "normal",
        "required_skills": payload.required_skills,
        "source": "api",
    }
    missing = [field for field in ("role", "location", "start_time", "end_time", "pay_amount") if not fields.get(field)]
    fields["missing_fields"] = missing
    fields["clarifying_question"] = None if not missing else f"Missing: {', '.join(missing)}"
    job = await repo.create_job_from_import(fields)
    await repo.create_event(
        job_id=job["id"],
        type="request_parsed" if not missing else "clarification_needed",
        content="Structured job created." if not missing else fields["clarifying_question"],
        status="complete" if not missing else "blocked",
        metadata={"missing_fields": missing},
    )
    return {"job": job, "needs_clarification": bool(missing)}


@router.get("/jobs/{job_id}")
@router.get("/api/jobs/{job_id}")
async def get_job(job_id: UUID) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    return {
        "job": job,
        "browser_sources": await repo.list_browser_sources_for_job(job_id),
        "events": await repo.list_events(job_id),
        "outreach": await repo.list_outreach(job_id),
        "schedules": await repo.list_schedules(job_id),
        "payment": await repo.get_payment(job_id),
        "proofs": await repo.list_proofs(job_id),
        "notifications": await repo.list_notifications(job_id),
    }


@router.post("/jobs/{job_id}/rank-contractors")
async def rank_contractors_endpoint(job_id: UUID) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    return {"contractors": await rank_job_contractors(job)}


@router.post("/jobs/{job_id}/outreach")
async def outreach(job_id: UUID, payload: OutreachRequest = OutreachRequest()) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    result = await run_outreach(job, send_real=payload.send_real)
    if payload.contractor_id and payload.contractor_id != result["contractor"]["id"]:
        # Preserve deterministic ranking for the demo but surface the requested id.
        result["requested_contractor_id"] = payload.contractor_id
    return result


@router.post("/jobs/{job_id}/accept")
async def accept(job_id: UUID, payload: AcceptRequest = AcceptRequest()) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    contractor_id = payload.contractor_id or job.get("assigned_contractor_id")
    if not contractor_id:
        contractor_id = rank_contractors(job)[0]["id"]
    intent = classify_contractor_reply(payload.response)
    if intent == "decline":
        await repo.create_event(
            job_id=job_id,
            type="contractor_declined",
            content=f"{contractor_id} declined: {payload.response}",
            status="blocked",
            metadata={"contractor_id": contractor_id, "response": payload.response},
        )
        return {"status": "declined", "intent": intent}
    result = await accept_contractor(
        job,
        contractor_id=contractor_id,
        response=payload.response,
        send_real_email=payload.send_real_email,
    )
    updated_job = await _job_or_404(job_id)
    payment = await hold_payment_for_job(updated_job)
    result["payment"] = payment
    return result


@router.post("/jobs/{job_id}/check-in")
async def check_in(job_id: UUID, payload: CheckInRequest = CheckInRequest()) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    contractor_id = payload.contractor_id or job.get("assigned_contractor_id")
    if not contractor_id:
        raise HTTPException(status_code=409, detail="no contractor assigned")
    proof = await check_in_contractor(
        job,
        contractor_id=contractor_id,
        proof_type=payload.proof_type,
        content=payload.content,
    )
    return {"proof": proof, "payment": await repo.get_payment(job_id)}


@router.post("/jobs/{job_id}/approve-release")
async def approve(job_id: UUID, payload: ApproveReleaseRequest = ApproveReleaseRequest()) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    payment = await approve_release(
        job,
        owner_approved=payload.owner_approved,
        execute_real=payload.execute_real_payment,
        send_real_email=payload.send_real_email,
    )
    return {"payment": payment}


@router.post("/jobs/{job_id}/events")
async def add_event(job_id: UUID, payload: EventRequest) -> dict[str, Any]:
    await _job_or_404(job_id)
    event = await repo.create_event(
        job_id=job_id,
        type=payload.type,
        content=payload.content,
        status=payload.status,
        metadata=payload.metadata,
    )
    return {"event": event}


@router.get("/jobs/{job_id}/stream")
async def stream_events(job_id: UUID) -> StreamingResponse:
    await _job_or_404(job_id)

    async def event_stream():
        events = await repo.list_events(job_id)
        for event in events:
            yield f"event: {event.get('type', 'event')}\ndata: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.1)
        yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/jobs/{job_id}/browser-sources")
async def add_browser_source(job_id: UUID, payload: BrowserSourceRequest) -> dict[str, Any]:
    await _job_or_404(job_id)
    source = await repo.create_browser_source(
        job_id=job_id,
        source_url=payload.source_url,
        source_type=payload.source_type,
        imported_fields=payload.imported_fields,
        screenshot_url=payload.screenshot_url,
        source_html_url=payload.source_html_url,
        extraction_confidence=payload.extraction_confidence,
        update_status=payload.update_status,
        browser_action_log=payload.browser_action_log,
    )
    await repo.create_event(
        job_id=job_id,
        type="source_imported",
        content=f"Browser source attached: {payload.source_url}",
        metadata={"browser_source_id": source["id"]},
    )
    return {"browser_source": source}


@router.post("/jobs/{job_id}/browser-sync")
async def browser_sync(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    source = await repo.update_browser_source_status(job_id=job_id, update_status="filled")
    await repo.create_event(
        job_id=job_id,
        type="browser_synced",
        content="External web source marked as filled.",
        metadata={"browser_source_id": source.get("id") if source else None},
    )
    return {"browser_source": source, "status": "filled"}


# ---------------------------------------------------------------------------
# Spec §10 fulfillment endpoints (event plan, schedule, invoice, payments,
# proofs). Persistence backed by the new tables in backend/app/db.py.
# ---------------------------------------------------------------------------

from .. import fulfillment  # placed here to avoid a circular import at module top


class ScheduleAssignment(BaseModel):
    contractor_id: str | None = None
    contractor_name: str | None = None
    role: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    status: str | None = None


class ScheduleRequest(BaseModel):
    assignments: list[ScheduleAssignment] = Field(default_factory=list)


class InvoiceRequest(BaseModel):
    client_email: str | None = None
    service_fee_rate: float = 0.10
    deposit_rate: float = 0.50


class ProofPostRequest(BaseModel):
    type: str = Field(..., pattern="^(sms|photo|qr|manager_approval|call|timesheet)$")
    detail: str | None = None
    contractor_id: str | None = None
    content_url: str | None = None
    status: str = "received"


@router.post("/jobs/{job_id}/infer-event-plan")
async def infer_event_plan(job_id: UUID) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    plan_body = await fulfillment.infer_event_plan_for_job(job)
    saved = await fulfillment.persist_event_plan(job_id, plan_body)
    await repo.create_event(
        job_id=job_id,
        type="event_plan_drafted",
        content=f"Event plan drafted: {saved['total_crew']} crew, est. ${saved['estimated_labor_cost']:.2f}",
        metadata={"event_plan_id": saved["id"]},
    )
    return {"event_plan": saved, "job": job}


@router.get("/jobs/{job_id}/event-plans")
async def list_job_event_plans(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    items = await fulfillment.list_event_plans(job_id)
    return {"items": items, "count": len(items)}


@router.post("/jobs/{job_id}/event-plans/{plan_id}/approve")
async def approve_plan(job_id: UUID, plan_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    plan = await fulfillment.approve_event_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="event plan not found")
    await repo.create_event(
        job_id=job_id, type="event_plan_approved",
        content=f"Event plan approved: {plan['total_crew']} crew",
        metadata={"event_plan_id": plan["id"]},
    )
    return {"event_plan": plan}


@router.post("/jobs/{job_id}/schedule")
async def schedule_endpoint(job_id: UUID, payload: ScheduleRequest) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    assignments = [a.model_dump() for a in payload.assignments]
    if not assignments:
        # Auto-derive from approved/draft event plan if owner didn't supply.
        plans = await fulfillment.list_event_plans(job_id)
        plan = next((p for p in plans if p["approval_status"] == "approved"), plans[0] if plans else None)
        if plan:
            for r in plan["roles"]:
                for i in range(int(r.get("count") or 0)):
                    assignments.append({"role": r.get("role")})
    schedule = await fulfillment.create_schedule(job_id, job, assignments)
    await repo.create_event(
        job_id=job_id, type="schedule_created",
        content=f"Schedule created: {len(schedule)} slot(s)",
        metadata={"count": len(schedule)},
    )
    return {"items": schedule, "count": len(schedule), "job": job}


@router.get("/jobs/{job_id}/schedule")
async def list_schedule_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    items = await fulfillment.list_schedule(job_id)
    return {"items": items, "count": len(items)}


@router.post("/jobs/{job_id}/invoice")
async def invoice_endpoint(job_id: UUID, payload: InvoiceRequest = InvoiceRequest()) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    inv = await fulfillment.generate_invoice(
        job_id, job,
        client_email=payload.client_email,
        service_fee_rate=payload.service_fee_rate,
        deposit_rate=payload.deposit_rate,
    )
    await repo.create_event(
        job_id=job_id, type="invoice_drafted",
        content=f"Invoice drafted: ${inv['total_amount']:.2f}",
        metadata={"invoice_id": inv["id"]},
    )
    return {"invoice": inv}


@router.post("/jobs/{job_id}/send-invoice")
async def send_invoice_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    inv = await fulfillment.send_invoice(job_id)
    if not inv:
        raise HTTPException(status_code=409, detail="no draft invoice to send")
    await repo.create_event(
        job_id=job_id, type="invoice_sent",
        content=f"Invoice emailed to {inv['client_email']} (AgentMail {inv['agentmail_id']})",
        metadata={"invoice_id": inv["id"], "agentmail_id": inv["agentmail_id"]},
    )
    return {"invoice": inv}


@router.get("/jobs/{job_id}/invoices")
async def list_invoices_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    items = await fulfillment.list_invoices(job_id)
    return {"items": items, "count": len(items)}


@router.post("/jobs/{job_id}/payment-holds")
async def payment_holds_endpoint(job_id: UUID) -> dict[str, Any]:
    job = await _job_or_404(job_id)
    holds = await fulfillment.create_payment_holds(job_id, job)
    total = round(sum(h["amount"] for h in holds), 2)
    await repo.create_event(
        job_id=job_id, type="worker_payments_held",
        content=f"{len(holds)} worker pay holds opened on Sponge — ${total:.2f}",
        metadata={"count": len(holds), "total": total},
    )
    return {"items": holds, "count": len(holds), "total": total}


@router.post("/jobs/{job_id}/release-payments")
async def release_payments_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    released = await fulfillment.release_payments(job_id)
    total = round(sum(h["amount"] for h in released), 2)
    if released:
        await repo.create_event(
            job_id=job_id, type="worker_payments_released",
            content=f"{len(released)} worker pay holds released — ${total:.2f}",
            metadata={"count": len(released), "total": total},
        )
    return {"items": released, "count": len(released), "total": total}


@router.get("/jobs/{job_id}/payment-holds")
async def list_payment_holds_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    items = await fulfillment.list_worker_payments(job_id)
    return {"items": items, "count": len(items)}


# Spec §10 path aliases that re-use the supplies routes (functionally
# identical to /api/events/{id}/supplies/{recommend,approve}, but the spec
# names them under /jobs/).
@router.post("/jobs/{job_id}/recommend-supplies")
async def recommend_supplies_alias(job_id: UUID, regenerate: bool = False) -> dict[str, Any]:
    await _job_or_404(job_id)
    from .. import supplies as _supplies
    existing = await _supplies.list_supplies(job_id)
    if existing and not regenerate:
        return {"items": existing, "summary": _supplies.supplies_summary(existing)}
    drafts = await _supplies.recommend_supplies({"id": str(job_id), **(await _job_or_404(job_id))})
    saved = await _supplies.persist_supplies(job_id, drafts)
    return {"items": saved, "summary": _supplies.supplies_summary(saved)}


@router.post("/jobs/{job_id}/approve-supplies")
async def approve_supplies_alias(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    from .. import supplies as _supplies
    items = await _supplies.simulate_vendor_checkout(job_id)
    if not items:
        raise HTTPException(status_code=409, detail="no supplies to approve — recommend first")
    return {"items": items, "summary": _supplies.supplies_summary(items)}


@router.post("/jobs/{job_id}/proofs")
async def post_proof_endpoint(job_id: UUID, payload: ProofPostRequest) -> dict[str, Any]:
    await _job_or_404(job_id)
    proof = await fulfillment.record_proof(
        job_id,
        proof_type=payload.type,
        detail=payload.detail,
        contractor_id=payload.contractor_id,
        content_url=payload.content_url,
        status=payload.status,
    )
    await repo.create_event(
        job_id=job_id, type="proof_received",
        content=f"Proof received ({payload.type})",
        metadata={"proof_id": proof["id"]},
    )
    return {"proof": proof}


@router.get("/jobs/{job_id}/proofs")
async def list_proofs_endpoint(job_id: UUID) -> dict[str, Any]:
    await _job_or_404(job_id)
    items = await fulfillment.list_proofs(job_id)
    return {"items": items, "count": len(items)}
