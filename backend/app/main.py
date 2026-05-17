import logging

from fastapi import FastAPI

from .routes import calls, sms, webhooks


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="CrewLoop API", version="0.1.0")
app.include_router(sms.router)
app.include_router(calls.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
