import re
from typing import Any

from . import repo
from .config import settings
from .dispatch_room import CONTRACTORS, rank_contractors
from .sponsors import (
    create_payment_hold,
    fetch_moss_contractor_memory,
    place_agentphone_call,
    release_payment,
    send_agentmail,
    send_agentphone_sms,
    upsert_moss_contractor_memory,
)


REQUIRED_JOB_FIELDS = ["role", "location", "start_time", "end_time", "pay_amount"]


def parse_job_request(text: str) -> dict[str, Any]:
    normalized = " ".join(text.strip().split())
    lower = normalized.lower()
    role_match = re.search(r"\b(bartender|server|cleaner|mover|photographer|security|driver|barback)\b", lower)
    pay_match = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)", normalized)
    time_match = re.search(
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
        lower,
    )
    location_match = re.search(
        r"\b(?:in|at|near)\s+([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3}|SoMa|SOMA|Mission|Oakland|Berkeley)\b",
        normalized,
    )
    skills: list[str] = []
    if "event experience" in lower:
        skills.append("event experience")
    if "bartend" in lower:
        skills.append("bartending")
    if "guest" in lower:
        skills.append("guest service")
    if role_match and role_match.group(1) not in skills:
        role = role_match.group(1)
        if role == "bartender":
            skills.append("bartending")
    else:
        role = role_match.group(1) if role_match else ""

    start_time = ""
    end_time = ""
    if time_match:
        start_raw = time_match.group(1)
        end_raw = time_match.group(2)
        if not re.search(r"\b(am|pm)\b", start_raw, re.IGNORECASE):
            meridiem = re.search(r"\b(am|pm)\b", end_raw, re.IGNORECASE)
            if meridiem:
                start_raw = f"{start_raw} {meridiem.group(1)}"
        start_time = _normalize_time(start_raw, lower)
        end_time = _normalize_time(end_raw, lower)

    urgency = "urgent" if re.search(r"\b(urgent|asap|tonight|canceled|cancelled|last[- ]minute|in 1 hour)\b", lower) else "normal"
    fields = {
        "business_name": "Bay Events Co.",
        "role": role,
        "description": normalized,
        "location": location_match.group(1) if location_match else "",
        "start_time": start_time,
        "end_time": end_time,
        "pay_amount": float(pay_match.group(1)) if pay_match else 0,
        "urgency": urgency,
        "required_skills": sorted(set(skills)),
        "source": "sms",
    }
    missing = [field for field in REQUIRED_JOB_FIELDS if not fields.get(field)]
    if not fields["required_skills"] and fields["role"]:
        fields["required_skills"] = [fields["role"]]
    fields["missing_fields"] = missing
    fields["clarifying_question"] = _clarifying_question(missing)
    return fields


def classify_contractor_reply(text: str) -> str:
    lower = text.lower().strip()
    if re.search(r"\b(yes|yep|yeah|i can|available|confirmed|accept|works|sounds good)\b", lower):
        return "accept"
    if re.search(r"\b(no|can't|cannot|unavailable|pass|sorry|decline)\b", lower):
        return "decline"
    if "pay" in lower or "$" in lower:
        return "question_pay"
    if "where" in lower or "address" in lower or "location" in lower:
        return "question_location"
    if "time" in lower or "when" in lower:
        return "question_time"
    if "check" in lower or "here" in lower or "arrived" in lower:
        return "check_in"
    return "question"


async def create_job_from_text(text: str) -> dict[str, Any]:
    fields = parse_job_request(text)
    job = await repo.create_job_from_import(fields)
    if fields["missing_fields"]:
        await repo.update_job(job["id"], status="needs_clarification")
        job["status"] = "needs_clarification"
        await repo.create_event(
            job_id=job["id"],
            type="clarification_needed",
            content=fields["clarifying_question"] or "Missing job details.",
            status="blocked",
            metadata={"missing_fields": fields["missing_fields"]},
        )
    else:
        await repo.create_event(
            job_id=job["id"],
            type="request_parsed",
            content=f"Parsed {job['role']} shift in {job['location']}.",
        )
    return job


async def rank_job_contractors(job: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = rank_contractors(job)
    moss_memory = await fetch_moss_contractor_memory()
    memory_by_id = _contractor_memory_by_id(moss_memory.get("documents", []))
    moss_enabled = moss_memory.get("source") == "moss"
    for contractor in ranked:
        moss_doc = memory_by_id.get(contractor["id"])
        if moss_doc:
            contractor["memory_source"] = "moss"
            contractor["memory"] = {**contractor_seed_memory(contractor), **moss_doc}
            if isinstance(moss_doc.get("reliability_score"), (int, float)):
                reliability_delta = int(moss_doc["reliability_score"]) - int(contractor["reliability_score"])
                contractor["reliability_score"] = int(moss_doc["reliability_score"])
                contractor["match_score"] = max(0, contractor["match_score"] + round(reliability_delta * 0.22))
            if isinstance(moss_doc.get("response_speed"), str):
                contractor["response_speed"] = moss_doc["response_speed"]
        else:
            contractor["memory_source"] = "moss" if moss_enabled else "seeded_moss_memory"
            contractor["memory"] = contractor_seed_memory(contractor)
    ranked = sorted(ranked, key=lambda item: item["match_score"], reverse=True)
    if moss_memory.get("index"):
        await upsert_moss_contractor_memory([contractor_memory_document(contractor) for contractor in ranked])
    for contractor in ranked:
        contractor.setdefault("memory", contractor_seed_memory(contractor))
        contractor["memory"]["moss_index"] = moss_memory.get("index")
    await repo.create_event(
        job_id=job["id"],
        type="contractor_matched",
        content=f"Ranked {len(ranked)} contractors; {ranked[0]['name']} is top match.",
        metadata={
            "top_contractor_id": ranked[0]["id"],
            "moss_enabled": moss_enabled,
            "moss_configured": moss_memory.get("moss_configured", bool(settings.moss_project_id and settings.moss_project_key)),
            "moss_index": moss_memory.get("index"),
            "memory_source": moss_memory.get("source"),
        },
    )
    return ranked


async def run_outreach(job: dict[str, Any], *, send_real: bool = False) -> dict[str, Any]:
    ranked = await rank_job_contractors(job)
    top = ranked[0]
    sms_body = (
        f"CrewLoop: urgent {job['role']} shift tonight, {job['start_time']} - {job['end_time']} "
        f"in {job['location']}. Pay {job['pay_amount']:g}. Can you take it?"
    )
    sms_result = await send_agentphone_sms(to_number=top["phone"], body=sms_body, send_real=send_real)
    sms = await repo.create_outreach(
        job_id=job["id"],
        contractor_id=top["id"],
        channel="sms",
        message=sms_body,
        status=sms_result["status"],
        provider_id=sms_result.get("id"),
        metadata=sms_result,
    )
    await repo.create_event(
        job_id=job["id"],
        type="text_sent",
        content=f"Texted {top['name']} about the {job['role']} shift.",
        metadata={"contractor_id": top["id"], "send_real": send_real},
    )

    call = None
    if job.get("urgency") == "urgent":
        greeting = f"Hi {top['name'].split()[0]}, this is CrewLoop calling about an urgent {job['role']} shift in {job['location']} tonight."
        system_prompt = (
            "You are CrewLoop's dispatcher. Confirm whether the contractor can take "
            f"the {job['role']} shift from {job['start_time']} to {job['end_time']} for ${job['pay_amount']:g}."
        )
        call_result = await place_agentphone_call(
            to_number=top["phone"],
            initial_greeting=greeting,
            system_prompt=system_prompt,
            send_real=send_real,
        )
        call = await repo.create_outreach(
            job_id=job["id"],
            contractor_id=top["id"],
            channel="call",
            message=greeting,
            status=call_result["status"],
            provider_id=call_result.get("id"),
            metadata=call_result,
        )
        await repo.create_event(
            job_id=job["id"],
            type="call_placed",
            content=f"Urgent call queued for {top['name']}.",
            metadata={"contractor_id": top["id"], "send_real": send_real},
        )

    await repo.update_job(job["id"], status="outreach_sent", assigned_contractor_id=top["id"])
    return {"contractor": top, "sms": sms, "call": call}


async def accept_contractor(
    job: dict[str, Any],
    *,
    contractor_id: str,
    response: str = "yes",
    send_real_email: bool = False,
) -> dict[str, Any]:
    contractor = get_contractor(contractor_id)
    await repo.update_outreach_response(
        job_id=job["id"],
        contractor_id=contractor_id,
        response=response,
        status="accepted",
    )
    await repo.update_job(
        job["id"],
        status="accepted",
        assigned_contractor_id=contractor_id,
        locked_at=repo._now_iso(),  # internal timestamp helper; JSON fallback only.
    )
    await repo.create_event(
        job_id=job["id"],
        type="contractor_accepted",
        content=f"{contractor['name']} accepted the shift.",
        metadata={"contractor_id": contractor_id, "response": response},
    )
    schedule = await repo.create_schedule(
        job_id=job["id"],
        contractor_id=contractor_id,
        start_time=job["start_time"],
        end_time=job["end_time"],
    )
    await repo.update_browser_source_status(job_id=job["id"], update_status="filled")
    await repo.create_event(
        job_id=job["id"],
        type="schedule_created",
        content=f"Created confirmed schedule for {contractor['name']}.",
        metadata={"schedule_id": schedule["id"]},
    )
    confirmation = await send_agentmail(
        to=contractor["email"],
        subject=f"CrewLoop confirmation: {job['role']} shift",
        text=contractor_confirmation_text(job, contractor),
        send_real=send_real_email,
    )
    await repo.create_notification(
        job_id=job["id"],
        channel="email",
        recipient=contractor["email"],
        subject=f"CrewLoop confirmation: {job['role']} shift",
        body=contractor_confirmation_text(job, contractor),
        status=confirmation["status"],
        provider_id=confirmation.get("id"),
        metadata=confirmation,
    )
    owner_summary = await send_owner_summary(job, contractor, send_real=send_real_email)
    return {"schedule": schedule, "contractor_notification": confirmation, "owner_summary": owner_summary}


async def hold_payment_for_job(job: dict[str, Any], *, execute_real: bool = False) -> dict[str, Any]:
    contractor_id = job.get("assigned_contractor_id")
    conditions = release_conditions(
        accepted=bool(contractor_id),
        checked_in=False,
        proof_submitted=False,
        owner_approved=False,
    )
    provider_state = await create_payment_hold(
        job_id=str(job["id"]),
        contractor_id=contractor_id,
        amount=float(job["pay_amount"]),
        release_conditions=conditions,
        execute_real=execute_real,
    )
    payment = await repo.upsert_payment(
        job_id=job["id"],
        contractor_id=contractor_id,
        amount=float(job["pay_amount"]),
        status="held",
        release_conditions=conditions,
        provider_state=provider_state,
    )
    await repo.create_event(
        job_id=job["id"],
        type="payment_held",
        content=f"Payment hold created for ${float(job['pay_amount']):g}.",
        metadata={"execute_real": execute_real, "provider_state": provider_state},
    )
    return payment


async def check_in_contractor(
    job: dict[str, Any],
    *,
    contractor_id: str,
    proof_type: str = "sms",
    content: str | None = None,
) -> dict[str, Any]:
    proof = await repo.create_proof(
        job_id=job["id"],
        contractor_id=contractor_id,
        type=proof_type,
        content_url=content,
        status="received",
        metadata={"content": content},
    )
    payment = await repo.get_payment(job["id"])
    if payment:
        conditions = release_conditions(
            accepted=True,
            checked_in=True,
            proof_submitted=True,
            owner_approved=False,
        )
        await repo.upsert_payment(
            job_id=job["id"],
            contractor_id=contractor_id,
            amount=float(job["pay_amount"]),
            status="held",
            release_conditions=conditions,
            provider_state=payment.get("provider_state") or {},
        )
    await repo.create_event(
        job_id=job["id"],
        type="proof_received",
        content=f"Received {proof_type} proof from {get_contractor(contractor_id)['name']}.",
        metadata={"proof_id": proof["id"]},
    )
    return proof


async def approve_release(
    job: dict[str, Any],
    *,
    owner_approved: bool = True,
    execute_real: bool = False,
    send_real_email: bool = False,
) -> dict[str, Any]:
    contractor_id = job.get("assigned_contractor_id")
    proofs = await repo.list_proofs(job["id"])
    conditions = release_conditions(
        accepted=bool(contractor_id),
        checked_in=bool(proofs),
        proof_submitted=bool(proofs),
        owner_approved=owner_approved,
    )
    provider_state = await release_payment(
        job_id=str(job["id"]),
        contractor_id=contractor_id,
        amount=float(job["pay_amount"]),
        release_conditions=conditions,
        execute_real=execute_real,
    )
    status = "released" if provider_state["status"] in {"released", "simulated_release"} else "blocked"
    payment = await repo.upsert_payment(
        job_id=job["id"],
        contractor_id=contractor_id,
        amount=float(job["pay_amount"]),
        status=status,
        release_conditions=conditions,
        provider_state=provider_state,
        receipt_url=provider_state.get("receipt_url"),
    )
    await repo.update_job(job["id"], status="completed" if status == "released" else "blocked")
    await repo.create_event(
        job_id=job["id"],
        type="payment_released" if status == "released" else "payment_blocked",
        content=(
            f"Payment released for ${float(job['pay_amount']):g}."
            if status == "released"
            else "Payment blocked because release conditions are incomplete."
        ),
        status="complete" if status == "released" else "blocked",
        metadata={"provider_state": provider_state},
    )
    if status == "released" and contractor_id:
        contractor = get_contractor(contractor_id)
        await send_final_report(job, contractor, payment, send_real=send_real_email)
        await send_receipt_email(job, contractor, payment, send_real=send_real_email)
    return payment


async def handle_contractor_message(phone: str, body: str) -> dict[str, Any] | None:
    contractor = next((item for item in CONTRACTORS if item["phone"] == phone), None)
    if not contractor:
        return None
    jobs = await repo.list_jobs(limit=50)
    active = next(
        (
            job
            for job in jobs
            if job.get("assigned_contractor_id") == contractor["id"]
            and job.get("status") in {"outreach_sent", "accepted", "scheduled"}
        ),
        None,
    )
    if not active:
        return None

    intent = classify_contractor_reply(body)
    if intent == "accept":
        result = await accept_contractor(active, contractor_id=contractor["id"], response=body)
        updated = await repo.get_job(active["id"])
        if updated:
            result["payment"] = await hold_payment_for_job(updated)
        return {"intent": intent, "job_id": active["id"], "result": result}
    if intent == "decline":
        await repo.update_outreach_response(
            job_id=active["id"],
            contractor_id=contractor["id"],
            response=body,
            status="declined",
        )
        await repo.create_event(
            job_id=active["id"],
            type="contractor_declined",
            content=f"{contractor['name']} declined: {body}",
            status="blocked",
            metadata={"contractor_id": contractor["id"]},
        )
        return {"intent": intent, "job_id": active["id"]}
    if intent == "check_in":
        proof = await check_in_contractor(
            active,
            contractor_id=contractor["id"],
            proof_type="sms",
            content=body,
        )
        return {"intent": intent, "job_id": active["id"], "proof": proof}

    await repo.create_event(
        job_id=active["id"],
        type="contractor_question",
        content=f"{contractor['name']} asked: {body}",
        status="ready",
        metadata={"contractor_id": contractor["id"], "intent": intent},
    )
    return {"intent": intent, "job_id": active["id"]}


async def send_owner_summary(
    job: dict[str, Any],
    contractor: dict[str, Any],
    *,
    send_real: bool = False,
) -> dict[str, Any]:
    text = (
        f"{contractor['name']} is confirmed for {job['business_name']}.\n"
        f"Role: {job['role']}\nTime: {job['start_time']} - {job['end_time']}\n"
        f"Location: {job['location']}\nPay: ${float(job['pay_amount']):g}\n"
        "Payment will release after check-in, proof, and owner approval."
    )
    result = await send_agentmail(
        to=settings.owner_email,
        subject=f"CrewLoop: {job['role']} shift covered",
        text=text,
        send_real=send_real,
    )
    await repo.create_notification(
        job_id=job["id"],
        channel="email",
        recipient=settings.owner_email,
        subject=f"CrewLoop: {job['role']} shift covered",
        body=text,
        status=result["status"],
        provider_id=result.get("id"),
        metadata=result,
    )
    return result


async def send_final_report(
    job: dict[str, Any],
    contractor: dict[str, Any],
    payment: dict[str, Any],
    *,
    send_real: bool = False,
) -> dict[str, Any]:
    text = (
        f"Final report for {job['business_name']} {job['role']} shift.\n"
        f"Contractor: {contractor['name']}\n"
        f"Payment: {payment['status']} ${float(payment['amount']):g}\n"
        f"Receipt: {payment.get('receipt_url') or 'simulated receipt'}"
    )
    result = await send_agentmail(
        to=settings.owner_email,
        subject=f"CrewLoop final report: {job['role']} shift",
        text=text,
        send_real=send_real,
    )
    await repo.create_notification(
        job_id=job["id"],
        channel="email",
        recipient=settings.owner_email,
        subject=f"CrewLoop final report: {job['role']} shift",
        body=text,
        status=result["status"],
        provider_id=result.get("id"),
        metadata=result,
    )
    return result


async def send_receipt_email(
    job: dict[str, Any],
    contractor: dict[str, Any],
    payment: dict[str, Any],
    *,
    send_real: bool = False,
) -> dict[str, Any]:
    text = (
        f"Receipt for {job['business_name']} {job['role']} shift.\n"
        f"Contractor: {contractor['name']}\n"
        f"Amount released: ${float(payment['amount']):g}\n"
        f"Receipt URL: {payment.get('receipt_url') or 'simulated receipt'}"
    )
    result = await send_agentmail(
        to=settings.owner_email,
        subject=f"CrewLoop receipt: {job['role']} shift",
        text=text,
        send_real=send_real,
    )
    await repo.create_notification(
        job_id=job["id"],
        channel="email",
        recipient=settings.owner_email,
        subject=f"CrewLoop receipt: {job['role']} shift",
        body=text,
        status=result["status"],
        provider_id=result.get("id"),
        metadata=result,
    )
    return result


def release_conditions(
    *,
    accepted: bool,
    checked_in: bool,
    proof_submitted: bool,
    owner_approved: bool,
) -> list[dict[str, Any]]:
    return [
        {"label": "Contractor accepted shift", "complete": accepted},
        {"label": "Contractor checked in", "complete": checked_in},
        {"label": "Proof submitted", "complete": proof_submitted},
        {"label": "Owner approved completion", "complete": owner_approved},
    ]


def get_contractor(contractor_id: str) -> dict[str, Any]:
    for contractor in CONTRACTORS:
        if contractor["id"] == contractor_id:
            return contractor
    raise ValueError(f"unknown contractor_id: {contractor_id}")


def contractor_confirmation_text(job: dict[str, Any], contractor: dict[str, Any]) -> str:
    return (
        f"You're confirmed for the {job['role']} shift.\n"
        f"Business: {job['business_name']}\n"
        f"Time: {job['start_time']} - {job['end_time']}\n"
        f"Location: {job['location']}\n"
        f"Pay: ${float(job['pay_amount']):g}\n"
        "Please check in by SMS when you arrive."
    )


def contractor_seed_memory(contractor: dict[str, Any]) -> dict[str, Any]:
    return {
        "reliability_score": contractor["reliability_score"],
        "response_speed": contractor["response_speed"],
        "notes": contractor["notes"],
        "skills": contractor["skills"],
        "capabilities": contractor.get("capabilities", []),
        "can_do": contractor.get("can_do"),
        "hourly_rate": contractor["hourly_rate"],
        "distance_miles": contractor["distance_miles"],
    }


def contractor_memory_document(contractor: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"contractor-{contractor['id']}",
        "text": (
            f"{contractor['name']} is a {contractor['availability']} contractor with "
            f"{', '.join(contractor['skills'])}. Reliability {contractor['reliability_score']}%. "
            f"Typical response speed {contractor['response_speed']}. Rate ${contractor['hourly_rate']}/hr. "
            f"{contractor['notes']}"
        ),
        "metadata": {
            "contractor_id": contractor["id"],
            "name": contractor["name"],
            "skills": contractor["skills"],
            "capabilities": contractor.get("capabilities", []),
            "can_do": contractor.get("can_do"),
            "reliability_score": contractor["reliability_score"],
            "response_speed": contractor["response_speed"],
            "hourly_rate": contractor["hourly_rate"],
            "distance_miles": contractor["distance_miles"],
        },
    }


def _contractor_memory_by_id(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    memory: dict[str, dict[str, Any]] = {}
    for doc in documents:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        contractor_id = metadata.get("contractor_id") or str(doc.get("id", "")).removeprefix("contractor-")
        if contractor_id:
            memory[str(contractor_id)] = {**metadata, "text": doc.get("text")}
    return memory


def _normalize_time(value: str, lower_text: str) -> str:
    value = value.strip().upper().replace(" ", "")
    if "tonight" in lower_text:
        return f"Tonight, {value}"
    return value


def _clarifying_question(missing: list[str]) -> str | None:
    if not missing:
        return None
    labels = {
        "role": "what role you need",
        "location": "where the shift is",
        "start_time": "the start time",
        "end_time": "the end time",
        "pay_amount": "the pay amount",
    }
    needed = [labels.get(field, field) for field in missing]
    if len(needed) == 1:
        return f"Can you confirm {needed[0]}?"
    return f"Can you confirm {', '.join(needed[:-1])}, and {needed[-1]}?"
