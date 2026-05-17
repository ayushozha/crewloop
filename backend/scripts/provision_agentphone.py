"""Provision an AgentPhone agent + 415 number + webhook for CrewLoop.

Run AFTER the backend is deployed to Coolify at AGENTPHONE_WEBHOOK_URL.
This script has real-world side effects: it creates an agent, rents a phone
number (recurring cost on your AgentPhone account), and registers a webhook.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as `python backend/scripts/provision_agentphone.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import settings


SYSTEM_PROMPT = """You are CrewLoop, the dispatch agent for a contractor-heavy small business.

Goals on a contractor call:
- Confirm the job: role, time, location, pay.
- Get a clear yes or no. If yes, lock the shift.
- If they ask questions ("what's the pay", "where", "is it still on"), answer from the job context.
- Keep it short and warm. Hang up once confirmed.
"""

BEGIN_MESSAGE = "Hey, this is CrewLoop calling on behalf of the venue. Do you have a sec for a quick shift?"


async def main() -> None:
    api_key = settings.agentphone_api_key
    base = settings.agentphone_base_url.rstrip("/")
    webhook_url = settings.agentphone_webhook_url

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60.0) as c:
        print(f"→ Creating agent…")
        agent_resp = await c.post("/agents", json={
            "name": "CrewLoop Dispatcher",
            "description": "AI dispatcher for contractor staffing",
            "voiceMode": "hosted",
            "modelTier": "balanced",
            "enableMessaging": True,
            "systemPrompt": SYSTEM_PROMPT,
            "beginMessage": BEGIN_MESSAGE,
        })
        agent_resp.raise_for_status()
        agent = agent_resp.json()
        agent_id = agent["id"]
        print(f"   agent_id={agent_id}")

        print(f"→ Provisioning US +1 415 number…")
        num_resp = await c.post("/numbers", json={
            "country": "US",
            "areaCode": "415",
            "agentId": agent_id,
        })
        num_resp.raise_for_status()
        number = num_resp.json()
        number_id = number["id"]
        phone = number["phoneNumber"]
        print(f"   number_id={number_id}  phone={phone}")

        print(f"→ Registering webhook at {webhook_url}…")
        wh_resp = await c.post("/webhooks", json={"url": webhook_url, "timeout": 30})
        wh_resp.raise_for_status()
        wh = wh_resp.json()
        secret = wh["secret"]
        print(f"   webhook_id={wh['id']}")

    print("\n=== ADD THESE TO .env.local ===")
    print(f"AGENTPHONE_AGENT_ID={agent_id}")
    print(f"AGENTPHONE_NUMBER_ID={number_id}")
    print(f"AGENTPHONE_FROM_NUMBER={phone}")
    print(f"AGENTPHONE_WEBHOOK_SECRET={secret}")


if __name__ == "__main__":
    asyncio.run(main())
