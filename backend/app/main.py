import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .routes import browser, calls, conversations, dispatch, jobs, sms, webhooks


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        yield
    finally:
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

app.include_router(sms.router)
app.include_router(calls.router)
app.include_router(webhooks.router)
app.include_router(conversations.router)
app.include_router(browser.router)
app.include_router(dispatch.router)
app.include_router(jobs.router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/browser-import", include_in_schema=False)
async def browser_import_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "browser-import.html")


@app.get("/bay-events/staffing", include_in_schema=False)
async def bay_events_staffing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "bay-events-staffing.html")
