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

    database_url: str = (
        "postgres://admin:i87RfJUBx5HZJuykZt4v9u3zaq10wAqV@localhost:5433/crewloop?sslmode=disable"
    )


settings = Settings()
