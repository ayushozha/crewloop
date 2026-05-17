from typing import Any


CONTRACTORS = [
    {
        "id": "maya",
        "name": "Maya Chen",
        "initials": "MC",
        "phone": "+14155550118",
        "email": "maya@example.com",
        "skills": ["bartending", "event experience", "guest service", "food safety"],
        "distance_miles": 2.1,
        "reliability_score": 98,
        "response_speed": "4 min",
        "availability": "available",
        "hourly_rate": 30,
        "notes": "Prefers evening event work. Accepted last 5 urgent shifts.",
    },
    {
        "id": "chris",
        "name": "Chris Patel",
        "initials": "CP",
        "phone": "+14155550142",
        "email": "chris@example.com",
        "skills": ["bartending", "barback", "private events"],
        "distance_miles": 4.8,
        "reliability_score": 61,
        "response_speed": "18 min",
        "availability": "available",
        "hourly_rate": 28,
        "notes": "Skill match, but two late check-ins in prior month.",
    },
    {
        "id": "priya",
        "name": "Priya Shah",
        "initials": "PS",
        "phone": "+14155550173",
        "email": "priya@example.com",
        "skills": ["server", "event experience", "guest service"],
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
        "phone": "+14155550194",
        "email": "luis@example.com",
        "skills": ["moving", "setup crew", "driver"],
        "distance_miles": 1.6,
        "reliability_score": 94,
        "response_speed": "6 min",
        "availability": "available",
        "hourly_rate": 32,
        "notes": "Nearby and reliable, but wrong primary skill.",
    },
]


def build_dispatch_payload(job: dict[str, Any], browser_sources: list[dict[str, Any]]) -> dict[str, Any]:
    contractors = _rank_contractors(job)
    top = contractors[0] if contractors else None
    browser_source = browser_sources[0] if browser_sources else None

    return {
        "job": job,
        "contractors": contractors,
        "timeline": _timeline(job, browser_source, top),
        "payment": _payment(job),
        "proof": _proof(job),
        "owner_summary": _owner_summary(job, top),
        "web_source": browser_source,
    }


def _rank_contractors(job: dict[str, Any]) -> list[dict[str, Any]]:
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

        ranked.append({**contractor, "match_score": score, "status": status})

    return sorted(ranked, key=lambda item: item["match_score"], reverse=True)


def _timeline(
    job: dict[str, Any],
    browser_source: dict[str, Any] | None,
    top_contractor: dict[str, Any] | None,
) -> list[dict[str, Any]]:
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


def _payment(job: dict[str, Any]) -> dict[str, Any]:
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


def _proof(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "awaiting contractor",
        "items": [
            {"type": "SMS check-in", "status": "pending", "detail": "Requested before shift start"},
            {"type": "Photo proof", "status": "pending", "detail": "Optional venue or station photo"},
            {"type": "Manager confirmation", "status": "required", "detail": "Needed before payment release"},
            {"type": "Timesheet", "status": "pending", "detail": f"{job.get('start_time')} - {job.get('end_time')}"},
        ],
    }


def _owner_summary(job: dict[str, Any], top_contractor: dict[str, Any] | None) -> dict[str, Any]:
    top_name = top_contractor["name"] if top_contractor else "No recommendation yet"
    eta = "18 min" if top_contractor else "pending"
    return {
        "business_name": job.get("business_name"),
        "confirmed_contractor": "Pending acceptance",
        "recommended_contractor": top_name,
        "eta": eta,
        "pay": float(job.get("pay_amount") or 0),
        "proof": "Required before release",
        "payment_status": "Pending hold",
        "message": (
            f"{top_name} is the strongest match for the {job.get('role')} shift in "
            f"{job.get('location')}. Outreach is ready."
        ),
    }
