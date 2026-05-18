from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agentphone_api_key: str
    agentphone_base_url: str = "https://api.agentphone.ai/v1"
    agentphone_agent_id: str | None = None
    agentphone_number_id: str | None = None
    agentphone_from_number: str | None = None
    agentphone_webhook_secret: str | None = None
    agentphone_webhook_url: str = "https://crewloop-api.ayushojha.com/webhooks/agentphone"

    browser_use_api_key: str | None = None
    browser_use_base_url: str = "https://api.browser-use.com/api/v3"
    browser_use_model: str = "bu-mini"

    agentmail_api_key: str | None = None
    agentmail_base_url: str = "https://api.agentmail.to/v0"
    agentmail_inbox_name: str = "CallMyAgent"
    agentmail_inbox_id: str | None = None
    owner_email: str = "owner@example.com"

    moss_project_id: str | None = None
    moss_project_key: str | None = None
    moss_base_url: str = "https://service.usemoss.dev/v1"
    moss_contractors_index: str = "contractors"

    sponge_api_key: str | None = None
    sponge_mcp_api_key: str | None = None
    sponge_mcp_url: str = "https://api.wallet.paysponge.com/mcp"
    stripe_api_key: str | None = None

    supermemory_api_key: str | None = None
    supermemory_base_url: str = "https://api.supermemory.ai"
    supermemory_container_tag: str = "crewloop:owner:ayush"

    database_url: str = (
        "postgres://admin:i87RfJUBx5HZJuykZt4v9u3zaq10wAqV@localhost:5433/crewloop?sslmode=disable"
    )

    gemini_api_key: str | None = None
    # Fast: short SMS replies. Pro: voice turns + multimodal (image proof of work).
    # gemini-3.1-pro-preview is multimodal (text/image/video/audio/PDF in, text out).
    gemini_model_fast: str = "gemini-3-flash-preview"
    gemini_model_pro: str = "gemini-3.1-pro-preview"


settings = Settings()
