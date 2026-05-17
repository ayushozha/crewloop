from typing import Any

import httpx

from .config import settings


class AgentPhoneError(RuntimeError):
    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"AgentPhone API {status}: {body}")
        self.status = status
        self.body = body


class AgentPhoneClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or settings.agentphone_api_key
        self._base_url = (base_url or settings.agentphone_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.post(path, json=payload)
        if r.status_code >= 400:
            raise AgentPhoneError(r.status_code, r.text)
        return r.json()

    async def send_message(
        self,
        to_number: str,
        body: str,
        agent_id: str | None = None,
        number_id: str | None = None,
    ) -> dict[str, Any]:
        # POST /v1/messages uses snake_case per AgentPhone docs.
        payload = {
            "agent_id": agent_id or settings.agentphone_agent_id,
            "to_number": to_number,
            "body": body,
        }
        nid = number_id or settings.agentphone_number_id
        if nid:
            payload["number_id"] = nid
        if not payload["agent_id"]:
            raise RuntimeError("AGENTPHONE_AGENT_ID is not configured")
        return await self._post("/messages", payload)

    async def place_call(
        self,
        to_number: str,
        initial_greeting: str | None = None,
        system_prompt: str | None = None,
        agent_id: str | None = None,
        from_number_id: str | None = None,
    ) -> dict[str, Any]:
        # POST /v1/calls uses camelCase per AgentPhone docs.
        payload: dict[str, Any] = {
            "agentId": agent_id or settings.agentphone_agent_id,
            "toNumber": to_number,
        }
        if initial_greeting:
            payload["initialGreeting"] = initial_greeting
        if system_prompt:
            payload["systemPrompt"] = system_prompt
        fid = from_number_id or settings.agentphone_number_id
        if fid:
            payload["fromNumberId"] = fid
        if not payload["agentId"]:
            raise RuntimeError("AGENTPHONE_AGENT_ID is not configured")
        return await self._post("/calls", payload)


_client: AgentPhoneClient | None = None


def get_client() -> AgentPhoneClient:
    global _client
    if _client is None:
        _client = AgentPhoneClient()
    return _client
