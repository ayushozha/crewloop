from typing import Any

CONTRACTORS = [
    {
        "id": "emma",
        "name": "Emma Carter",
        "initials": "EC",
        "profile_image_url": "/static/portraits/emma-carter.jpg",
        "phone": "+14155550118",
        "email": "emma@example.com",
        "skills": ["bartending", "event experience", "guest service", "food safety"],
        "capabilities": ["high-volume bar", "cocktail batching", "guest service", "food safety"],
        "can_do": "Can run the bar solo, batch cocktails, manage guest-facing service, and close with food-safety standards.",
        "distance_miles": 2.1,
        "reliability_score": 98,
        "response_speed": "4 min",
        "availability": "available",
        "hourly_rate": 30,
        "notes": "Prefers evening event work. Accepted last 5 urgent shifts.",
    },
    {
        "id": "madison",
        "name": "Madison Reed",
        "initials": "MR",
        "profile_image_url": "/static/portraits/madison-reed.jpg",
        "phone": "+14155550142",
        "email": "madison@example.com",
        "skills": ["bartending", "barback", "private events"],
        "capabilities": ["barback support", "private events", "beer and wine", "setup"],
        "can_do": "Can support a staffed bar, handle beer and wine service, prep stations, and reset private events.",
        "distance_miles": 4.8,
        "reliability_score": 61,
        "response_speed": "18 min",
        "availability": "available",
        "hourly_rate": 28,
        "notes": "Skill match, but two late check-ins in prior month.",
    },
    {
        "id": "ashley",
        "name": "Ashley Brooks",
        "initials": "AB",
        "profile_image_url": "/static/portraits/ashley-brooks.jpg",
        "phone": "+14155550173",
        "email": "ashley@example.com",
        "skills": ["server", "event experience", "guest service"],
        "capabilities": ["tray pass", "check-in desk", "guest service", "event support"],
        "can_do": "Can cover guest check-in, tray pass, event support, and front-of-house service.",
        "distance_miles": 3.4,
        "reliability_score": 91,
        "response_speed": "7 min",
        "availability": "standby",
        "hourly_rate": 26,
        "notes": "Reliable backup for guest-facing event roles.",
    },
    {
        "id": "luis",
        "name": "Luis Romero",
        "initials": "LR",
        "profile_image_url": "/static/portraits/luis-romero.jpg",
        "phone": "+14155550194",
        "email": "luis@example.com",
        "skills": ["moving", "setup crew", "driver"],
        "capabilities": ["load-in", "venue setup", "driving", "strike crew"],
        "can_do": "Can handle load-in, venue setup, driving runs, and end-of-night strike crew.",
        "distance_miles": 1.6,
        "reliability_score": 94,
        "response_speed": "6 min",
        "availability": "available",
        "hourly_rate": 32,
        "notes": "Nearby and reliable, but wrong primary skill.",
    },
]


def build_dispatch_payload(
    job: dict[str, Any],
    browser_sources: list[dict[str, Any]],
    *,
    events: list[dict[str, Any]] | None = None,
    outreach: list[dict[str, Any]] | None = None,
    schedules: list[dict[str, Any]] | None = None,
    payment: dict[str, Any] | None = None,
    proofs: list[dict[str, Any]] | None = None,
    notifications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    contractors = rank_contractors(job)
    top = contractors[0] if contractors else None
    browser_source = browser_sources[0] if browser_sources else None
    events = events or []
    outreach = outreach or []
    schedules = schedules or []
    proofs = proofs or []
    notifications = notifications or []

    return {
        "job": job,
        "contractors": contractors,
        "timeline": _timeline(job, browser_source, top, events),
        "outreach": outreach,
        "schedules": schedules,
        "payment": _payment(job, payment),
        "proof": _proof(job, proofs),
        "owner_summary": _owner_summary(job, top, schedules, payment, proofs, notifications),
        "web_source": browser_source,
        "notifications": notifications,
    }


def rank_contractors(job: dict[str, Any]) -> list[dict[str, Any]]:
    role = str(job.get("role") or "").lower()
    role_aliases = {
        "bartender": {"bartender", "bartending", "barback"},
        "server": {"server", "serving", "guest service"},
        "cleaner": {"cleaner", "cleaning"},
        "mover": {"mover", "moving"},
        "security": {"security"},
    }
    accepted_role_skills = role_aliases.get(role, {role})
    required = {str(skill).lower() for skill in job.get("required_skills") or []}
    ranked = []

    for contractor in CONTRACTORS:
        skills = {skill.lower() for skill in contractor["skills"]}
        role_score = 32 if role and (accepted_role_skills & skills) else 0
        required_score = 0 if not required else round(30 * len(required & skills) / len(required))
        reliability_score = contractor["reliability_score"] * 0.22
        distance_score = max(0, 10 - contractor["distance_miles"])
        availability_score = 6 if contractor["availability"] == "available" else 2
        score = round(role_score + required_score + reliability_score + distance_score + availability_score)

        if role_score and score >= 85:
            status = "recommended"
        elif role_score:
            status = "backup"
        elif required & skills:
            status = "partial"
        else:
            status = "mismatch"

        ranked.append(
            {
                **contractor,
                "match_score": score,
                "status": status,
                "memory_source": "seeded_moss_memory",
            }
        )

    return sorted(ranked, key=lambda item: item["match_score"], reverse=True)


def _timeline(
    job: dict[str, Any],
    browser_source: dict[str, Any] | None,
    top_contractor: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if events:
        return [
            {
                "label": _event_label(event.get("type", "event")),
                "detail": event.get("content") or "",
                "status": event.get("status") or "complete",
                "time": event.get("created_at", "now"),
            }
            for event in events
        ]

    source_name = "Bay Events staffing page"
    if browser_source:
        source_name = browser_source.get("source_url") or source_name

    top_name = top_contractor["name"] if top_contractor else "Top contractor"
    return [
        {
            "label": "Source imported",
            "detail": source_name,
            "status": "complete",
            "time": "now",
        },
        {
            "label": "Job parsed",
            "detail": f"{job.get('role', 'Contractor')} shift in {job.get('location', 'unknown location')}",
            "status": "complete",
            "time": "+4s",
        },
        {
            "label": "Contractors ranked",
            "detail": f"{top_name} is the recommended match",
            "status": "complete",
            "time": "+8s",
        },
        {
            "label": "Text prepared",
            "detail": f"SMS ready for {top_name}",
            "status": "ready",
            "time": "next",
        },
        {
            "label": "Urgent call",
            "detail": "Queued because job urgency is high",
            "status": "pending",
            "time": "next",
        },
        {
            "label": "Schedule",
            "detail": "Waiting for contractor acceptance",
            "status": "pending",
            "time": "pending",
        },
        {
            "label": "Payment hold",
            "detail": f"${job.get('pay_amount', 0):g} hold prepared",
            "status": "pending",
            "time": "pending",
        },
        {
            "label": "Proof received",
            "detail": "Check-in and manager approval required",
            "status": "blocked",
            "time": "blocked",
        },
    ]


def _payment(job: dict[str, Any], payment: dict[str, Any] | None = None) -> dict[str, Any]:
    if payment:
        return {
            "amount": float(payment.get("amount") or job.get("pay_amount") or 0),
            "status": payment.get("status") or "pending",
            "provider": "Sponge rules + Stripe payment state",
            "release_conditions": payment.get("release_conditions") or [],
            "provider_state": payment.get("provider_state") or {},
            "receipt_url": payment.get("receipt_url"),
        }
    return {
        "amount": float(job.get("pay_amount") or 0),
        "status": "pending",
        "provider": "Sponge rules + Stripe payment state",
        "release_conditions": [
            {"label": "Contractor accepted shift", "complete": False},
            {"label": "Contractor checked in", "complete": False},
            {"label": "Proof submitted", "complete": False},
            {"label": "Owner approved completion", "complete": False},
        ],
    }


def _proof(job: dict[str, Any], proofs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    proofs = proofs or []
    if proofs:
        return {
            "status": "received",
            "items": [
                {
                    "type": proof.get("type", "proof"),
                    "status": proof.get("status", "received"),
                    "detail": proof.get("content_url") or proof.get("metadata", {}).get("content") or "Proof captured",
                }
                for proof in proofs
            ],
        }
    return {
        "status": "awaiting contractor",
        "items": [
            {"type": "SMS check-in", "status": "pending", "detail": "Requested before shift start"},
            {"type": "Photo proof", "status": "pending", "detail": "Optional venue or station photo"},
            {"type": "Manager confirmation", "status": "required", "detail": "Needed before payment release"},
            {"type": "Timesheet", "status": "pending", "detail": f"{job.get('start_time')} - {job.get('end_time')}"},
        ],
    }


def _owner_summary(
    job: dict[str, Any],
    top_contractor: dict[str, Any] | None,
    schedules: list[dict[str, Any]],
    payment: dict[str, Any] | None,
    proofs: list[dict[str, Any]],
    notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    top_name = top_contractor["name"] if top_contractor else "No recommendation yet"
    assigned = job.get("assigned_contractor_id")
    confirmed = "Pending acceptance"
    if assigned:
        match = next((contractor for contractor in CONTRACTORS if contractor["id"] == assigned), None)
        confirmed = match["name"] if match else assigned
    eta = "18 min" if top_contractor else "pending"
    payment_status = payment.get("status") if payment else "Pending hold"
    return {
        "business_name": job.get("business_name"),
        "confirmed_contractor": confirmed,
        "recommended_contractor": top_name,
        "eta": "scheduled" if schedules else eta,
        "pay": float(job.get("pay_amount") or 0),
        "proof": "Received" if proofs else "Required before release",
        "payment_status": payment_status,
        "notifications_sent": len(notifications),
        "message": (
            f"{confirmed if assigned else top_name} is "
            f"{'confirmed' if assigned else 'the strongest match'} for the {job.get('role')} shift in "
            f"{job.get('location')}."
        ),
    }


def _event_label(event_type: str) -> str:
    return {
        "source_imported": "Source imported",
        "request_parsed": "Request parsed",
        "clarification_needed": "Clarification needed",
        "contractor_matched": "Contractor matched",
        "text_sent": "Text sent",
        "call_placed": "Call placed",
        "contractor_accepted": "Contractor accepted",
        "contractor_declined": "Contractor declined",
        "schedule_created": "Schedule created",
        "payment_held": "Payment held",
        "proof_received": "Proof received",
        "payment_released": "Payment released",
        "payment_blocked": "Payment blocked",
        "email_sent": "Email sent",
        "browser_synced": "Browser synced",
    }.get(event_type, event_type.replace("_", " ").title())
