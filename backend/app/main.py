import asyncio
import logging
import os
import secrets as _secrets
from contextlib import asynccontextmanager
from pathlib import Path

# Avoid slow entry-point scanning during local FastAPI/Pydantic startup.
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from . import shifts as shifts_service
from .config import settings
from .routes import (
    browser,
    calls,
    chat,
    contractors,
    conversations,
    dispatch,
    events,
    inventory,
    jobs,
    sms,
    voice_call,
    webhooks,
)
from .routes import shifts as shifts_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("crewloop.main")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    if not settings.app_password:
        logger.warning(
            "APP_PASSWORD is not set — the dashboard/API are open. Fine for local dev, "
            "never for a deployed pilot."
        )
    if settings.demo_mode:
        logger.warning("DEMO_MODE is ON: simulated demo flows are reachable. Turn off for pilots.")
    if not settings.agentphone_webhook_secret:
        logger.warning(
            "AGENTPHONE_WEBHOOK_SECRET is not set — /webhooks/agentphone accepts UNSIGNED events. "
            "A forged webhook could fake contractor replies or trigger opt-outs. Set it before any pilot."
        )
    ping_task = asyncio.create_task(shifts_service.ping_loop()) if db.available() else None
    try:
        yield
    finally:
        if ping_task is not None:
            ping_task.cancel()
        await db.disconnect()


app = FastAPI(title="CrewLoop API", version="0.2.0", lifespan=lifespan)

# The Next.js frontend at crewloop.ayushojha.com calls this API directly from
# the browser, so we need CORS. Allowing localhost too for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://crewloop.ayushojha.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared-password gate for concierge pilots. Protects every owner-facing
# surface; webhooks stay open (they are HMAC-verified), health stays open for
# probes, docs/static stay open. Per-operator auth replaces this before a
# second operator's roster is imported.
_PROTECTED_PREFIXES = ("/api/", "/jobs", "/dispatch")


@app.middleware("http")
async def app_password_gate(request: Request, call_next):
    password = settings.app_password
    # Lowercase before matching: routes are case-sensitive (uppercase paths 404
    # anyway), but the gate must not be the weaker layer.
    path = request.url.path.lower()
    if password and request.method != "OPTIONS" and path.startswith(_PROTECTED_PREFIXES):
        supplied = request.headers.get("x-app-password") or ""
        if not _secrets.compare_digest(supplied, password):
            return JSONResponse(status_code=401, content={"detail": "missing or invalid X-App-Password header"})
    return await call_next(request)


app.include_router(sms.router)
app.include_router(calls.router)
app.include_router(webhooks.router)
app.include_router(conversations.router)
app.include_router(browser.router)
app.include_router(dispatch.router)
app.include_router(jobs.router)
app.include_router(contractors.router)
app.include_router(chat.router)
app.include_router(inventory.router)
app.include_router(events.router)
app.include_router(voice_call.router)
app.include_router(shifts_routes.router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return HTMLResponse(_API_LANDING_HTML)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


_API_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>CrewLoop API</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f7f7f5; color: #1a1a1a; }
  @media (prefers-color-scheme: dark) { body { background: #0f0f10; color: #e8e8e8; } a { color: #7fb3ff; } code { background: #1c1c1f; color: #eaeaea; } .card { background: #161618; border-color: #26262a; } .muted { color: #8a8a93; } }
  main { max-width: 880px; margin: 0 auto; padding: 56px 24px 80px; }
  h1 { font-size: 32px; letter-spacing: -0.01em; margin: 0 0 4px; }
  h2 { font-size: 18px; letter-spacing: -0.005em; margin: 36px 0 12px; }
  .muted { color: #6b6b76; }
  .lead { font-size: 17px; margin: 8px 0 28px; }
  .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .card { display: block; padding: 14px 16px; background: #fff; border: 1px solid #e6e6e0; border-radius: 10px; text-decoration: none; color: inherit; }
  .card:hover { border-color: #888; }
  .card strong { display: block; margin-bottom: 2px; }
  table { width: 100%; border-collapse: collapse; margin-top: 4px; }
  td { padding: 8px 10px; border-bottom: 1px solid rgba(127,127,127,0.18); vertical-align: top; }
  td:first-child { white-space: nowrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; background: #ececea; padding: 1px 5px; border-radius: 4px; }
</style>
</head>
<body>
<main>
  <h1>CrewLoop API</h1>
  <p class="lead muted">Backend for CrewLoop &mdash; AgentPhone-powered SMS &amp; voice dispatch, with Gemini reply generation and Postgres-backed conversation history.</p>

  <h2>Interactive docs</h2>
  <div class="row">
    <a class="card" href="/docs"><strong>Swagger UI &rarr;</strong><span class="muted">Try every endpoint in the browser.</span></a>
    <a class="card" href="/redoc"><strong>ReDoc &rarr;</strong><span class="muted">Read-friendly reference view.</span></a>
    <a class="card" href="/openapi.json"><strong>OpenAPI spec &rarr;</strong><span class="muted">Machine-readable JSON.</span></a>
  </div>

  <p class="muted">The Next.js owner dashboard lives at <a href="https://crewloop.ayushojha.com">crewloop.ayushojha.com</a>.</p>

  <h2>Endpoint groups</h2>
  <table>
    <tr><td><code>POST /api/shifts</code> &amp; <code>/api/shifts/{id}/...</code></td><td>Fill-a-shift loop: create, outreach, board, cascade, call.</td></tr>
    <tr><td><code>POST /api/contractors/import</code></td><td>Roster CSV import (name, phone, roles, priority).</td></tr>
    <tr><td><code>POST /api/sms/send</code></td><td>Outbound SMS to a contractor via AgentPhone.</td></tr>
    <tr><td><code>POST /api/calls/place</code></td><td>Place an outbound voice call.</td></tr>
    <tr><td><code>GET&nbsp; /api/conversations</code></td><td>List conversations with last-message preview and counts.</td></tr>
    <tr><td><code>GET&nbsp; /api/conversations/{phone}</code></td><td>Full SMS + call thread for one E.164 phone.</td></tr>
    <tr><td><code>GET&nbsp; /api/calls</code></td><td>Flat list of all calls.</td></tr>
    <tr><td><code>GET&nbsp; /api/contractors</code></td><td>Contractor roster.</td></tr>
    <tr><td><code>GET&nbsp; /api/inventory</code></td><td>Bar inventory listing.</td></tr>
    <tr><td><code>POST /api/chat</code></td><td>Multimodal owner chat (Gemini).</td></tr>
    <tr><td><code>POST /jobs</code> &amp; <code>/jobs/{id}/...</code></td><td>Jobs lifecycle: rank, outreach, accept, check-in, release.</td></tr>
    <tr><td><code>POST /api/browser/import</code></td><td>Browser-use roster import.</td></tr>
    <tr><td><code>POST /webhooks/agentphone</code></td><td>AgentPhone inbound events (signed).</td></tr>
    <tr><td><code>POST /webhooks/{agentmail,stripe,sponge}</code></td><td>External-service webhooks.</td></tr>
    <tr><td><code>GET&nbsp; /health</code></td><td>Liveness probe.</td></tr>
  </table>
</main>
</body>
</html>
"""
