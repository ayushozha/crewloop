import logging
from typing import Any

import httpx

from .agentphone import get_client
from .config import settings


logger = logging.getLogger("crewloop.sponsors")


async def fetch_moss_contractor_memory() -> dict[str, Any]:
    if not settings.moss_project_id or not settings.moss_project_key:
        return {"source": "seeded_moss_memory", "documents": [], "index": None}

    try:
        indexes = await _moss_manage({"action": "listIndexes"})
        names = [item.get("name") for item in indexes if item.get("name")]
        preferred = [
            settings.moss_contractors_index,
            "crewloop-contractors",
            "contractor-memory",
            "contractors",
        ]
        index_name = next((name for name in preferred if name in names), None)
        if not index_name:
            return {
                "source": "seeded_moss_memory",
                "moss_configured": True,
                "documents": [],
                "index": None,
                "available_indexes": names,
                "status": "no_contractor_index",
            }

        docs = await _moss_manage({"action": "getDocs", "indexName": index_name})
        return {
            "source": "moss",
            "moss_configured": True,
            "documents": docs if isinstance(docs, list) else [],
            "index": index_name,
        }
    except Exception as exc:
        logger.warning("Moss contractor memory unavailable; using seeded memory: %s", exc)
        return {"source": "seeded_moss_memory", "documents": [], "index": None, "error": str(exc)}


async def upsert_moss_contractor_memory(documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.moss_project_id or not settings.moss_project_key:
        return {"source": "seeded_moss_memory", "status": "skipped"}
    try:
        result = await _moss_manage(
            {
                "action": "addDocs",
                "indexName": settings.moss_contractors_index,
                "docs": documents,
                "options": {"upsert": True},
            }
        )
        return {"source": "moss", "status": "queued", "result": result}
    except Exception as exc:
        logger.warning("Moss contractor memory update skipped: %s", exc)
        return {"source": "seeded_moss_memory", "status": "skipped", "error": str(exc)}


async def _moss_manage(payload: dict[str, Any]) -> Any:
    body = {"projectId": settings.moss_project_id, **payload}
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            f"{settings.moss_base_url.rstrip('/')}/manage",
            headers={
                "Content-Type": "application/json",
                "x-service-version": "v1",
                "x-project-key": settings.moss_project_key or "",
            },
            json=body,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Moss API {response.status_code}: {response.text[:200]}")
    return response.json()


async def send_agentphone_sms(
    *,
    to_number: str,
    body: str,
    send_real: bool = False,
) -> dict[str, Any]:
    if not send_real:
        return {"status": "simulated", "provider": "agentphone", "id": None}
    result = await get_client().send_message(to_number=to_number, body=body)
    return {"status": "sent", "provider": "agentphone", "id": result.get("id"), "raw": result}


async def place_agentphone_call(
    *,
    to_number: str,
    initial_greeting: str,
    system_prompt: str,
    send_real: bool = False,
) -> dict[str, Any]:
    if not send_real:
        return {"status": "simulated", "provider": "agentphone", "id": None}
    result = await get_client().place_call(
        to_number=to_number,
        initial_greeting=initial_greeting,
        system_prompt=system_prompt,
    )
    return {"status": "placed", "provider": "agentphone", "id": result.get("id") or result.get("callId"), "raw": result}


async def send_agentmail(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    send_real: bool = False,
) -> dict[str, Any]:
    if not send_real or not settings.agentmail_api_key or not settings.agentmail_inbox_id:
        return {
            "status": "simulated",
            "provider": "agentmail",
            "id": None,
            "reason": "set AGENTMAIL_INBOX_ID and send_real=true to send",
        }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.agentmail_base_url.rstrip('/')}/inboxes/{settings.agentmail_inbox_id}/messages/send",
            headers={
                "Authorization": f"Bearer {settings.agentmail_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "to": to,
                "subject": subject,
                "text": text,
                "html": html,
                "labels": ["crewloop"],
            },
        )
    if response.status_code >= 400:
        logger.warning("AgentMail send failed: %s %s", response.status_code, response.text[:300])
        return {"status": "failed", "provider": "agentmail", "id": None, "error": response.text}
    data = response.json()
    return {"status": "sent", "provider": "agentmail", "id": data.get("message_id"), "raw": data}


async def create_payment_hold(
    *,
    job_id: str,
    contractor_id: str | None,
    amount: float,
    release_conditions: list[dict[str, Any]],
    execute_real: bool = False,
) -> dict[str, Any]:
    # Live payment movement should never happen in this hackathon path without a
    # dedicated money-flow confirmation and account setup. We still record the
    # exact Sponge/Stripe rule state the payment agent would enforce.
    return {
        "status": "held" if execute_real else "simulated_hold",
        "provider": "sponge+stripe",
        "sponge": {
            "wallet_rules": {
                "job_id": job_id,
                "contractor_id": contractor_id,
                "pay_cap": amount,
                "release_conditions": release_conditions,
                "mcp_url": settings.sponge_mcp_url,
            },
            "live": bool(execute_real and settings.sponge_api_key),
        },
        "stripe": {
            "amount": amount,
            "currency": "usd",
            "live": bool(execute_real and settings.stripe_api_key),
        },
    }


async def release_payment(
    *,
    job_id: str,
    contractor_id: str | None,
    amount: float,
    release_conditions: list[dict[str, Any]],
    execute_real: bool = False,
) -> dict[str, Any]:
    all_complete = all(item.get("complete") for item in release_conditions)
    if not all_complete:
        return {
            "status": "blocked",
            "provider": "sponge+stripe",
            "reason": "release conditions incomplete",
        }
    return {
        "status": "released" if execute_real else "simulated_release",
        "provider": "sponge+stripe",
        "receipt_url": f"/receipts/{job_id}",
        "sponge": {"rule_passed": True, "live": bool(execute_real and settings.sponge_api_key)},
        "stripe": {"amount": amount, "currency": "usd", "live": bool(execute_real and settings.stripe_api_key)},
        "contractor_id": contractor_id,
    }
