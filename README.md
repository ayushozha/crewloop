<div align="center">

# CrewLoop

**AI dispatcher that fills shifts for event businesses over real SMS and voice.**
Create a shift, blast your own roster in priority order, watch the YES/NO board fill live, cascade to backups, and let automatic confirmation pings catch flakes before the event does.

[![Status](https://img.shields.io/badge/status-pilot_hardening-orange?style=flat-square)](#status-at-a-glance)
[![Tests](https://img.shields.io/badge/tests-77_passing-brightgreen?style=flat-square)](./backend/tests)
[![CI](https://img.shields.io/badge/CI-ruff_·_pytest_·_tsc-blue?style=flat-square)](./.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Postgres](https://img.shields.io/badge/Postgres-17-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

</div>

---

CrewLoop started as a hackathon demo (an AI agent coordinating event staff via SMS/voice) and is being hardened into a pilot product for concierge pilots (June 2026). The wedge is one loop — **fill a shift** — and everything in that loop sends real SMS and places real calls. The hackathon's demo theater (scripted voice calls, simulated contractor replies, fabricated payment refs) still exists, but it is now **disabled by default** behind a `DEMO_MODE` kill switch.

## Table of contents

- [What is CrewLoop?](#what-is-crewloop)
- [Status at a glance](#status-at-a-glance)
- [The fill-a-shift loop (pilot)](#the-fill-a-shift-loop-pilot)
- [SMS compliance](#sms-compliance)
- [Pilot mode vs demo mode](#pilot-mode-vs-demo-mode)
- [Auth](#auth)
- [The hackathon demo (DEMO_MODE)](#the-hackathon-demo-demo_mode)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Sponsor integrations](#sponsor-integrations)
- [Repository layout](#repository-layout)
- [Quickstart](#quickstart)
- [Environment variables](#environment-variables)
- [Data model](#data-model)
- [API reference](#api-reference)
- [Tests & CI](#tests--ci)
- [Seeding demo data](#seeding-demo-data)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [License](#license)

---

## What is CrewLoop?

CrewLoop is an **AI ops dispatcher for event businesses** — catering, event staffing, venue ops, cleaning crews, photographers, hospitality, security, field service. The pilot pitch is one sentence:

> Give CrewLoop a shift and your roster, and it texts the right workers in priority order, tracks who's in, backfills decliners, calls the stragglers, and confirms everyone before the event — so nobody no-shows you at 5pm on a Saturday.

The original hackathon build chased a much wider 14-step fulfillment loop (staffing + supplies + invoicing + conditional worker pay). That scope still exists in the codebase, but the parts that faked external side effects are now demo-only (see [Pilot mode vs demo mode](#pilot-mode-vs-demo-mode)). The pilot product is the narrow loop that is real end to end.

## Status at a glance

| Area | Status | Where |
|---|---|---|
| Fill-a-shift loop (create → outreach → board → cascade → call → pings) | **Implemented, pilot-ready** — all sends are real SMS/voice via AgentPhone | `backend/app/shifts.py`, `backend/app/routes/shifts.py` |
| Roster CSV import (upsert by phone) | **Implemented** | `POST /api/contractors/import`, `backend/app/shift_logic.py` |
| STOP/START SMS compliance (CTIA keywords, persisted opt-out) | **Implemented** | `backend/app/shift_logic.py`, `backend/app/shifts.py` |
| Shared-password gate (`APP_PASSWORD` → `X-App-Password`) | **Implemented** | `backend/app/main.py` |
| Signed AgentPhone webhooks + Gemini SMS auto-reply | **Implemented** | `backend/app/routes/webhooks.py`, `backend/app/signature.py` |
| Tests (77) + GitHub Actions CI (ruff, pytest, tsc) | **Implemented** | `backend/tests/`, `.github/workflows/ci.yml` |
| Scripted voice-call demo (contractor side simulated) | **Demo-only**, HTTP 501 unless `DEMO_MODE=true` | `backend/app/routes/voice_call.py` |
| Bulk-outreach demo with simulated replies | **Demo-only**, gated | `backend/app/bulk_outreach.py` |
| Simulated vendor checkout (fabricated Browser Use evidence) | **Demo-only**, gated | `backend/app/supplies.py` |
| Invoice "send" / payment holds & releases (fabricated AgentMail/Sponge refs) | **Demo-only**, gated — returns 501 or `status: "disabled"` in pilot mode | `backend/app/fulfillment.py`, `backend/app/sponsors.py` |
| Supermemory / Moss memory | **Stubbed** — client wired, write/query not in the loop | `backend/app/supermemory_client.py` |
| Next.js dashboard: shift create/list, live fill board, CSV import UI, password gate | **Implemented** — `/shifts`, `/shifts/[id]`, `/contractors/import` | `frontend/src/app/shifts/`, `frontend/src/components/PasswordGate.tsx` |
| Per-operator auth, real STT on calls, real vendor checkout, payouts | **Roadmap** | [Roadmap](#roadmap) |

## The fill-a-shift loop (pilot)

The one loop the pilot runs on. Every message in it is a real SMS through AgentPhone; every call is a real outbound call. There is no simulated path in this module (`backend/app/shifts.py`).

1. **Import your roster** — `POST /api/contractors/import` takes a CSV (`name`, `phone` required; `roles`, `priority`, `rate`, `notes`, `email`, `location` optional, with forgiving header aliases). Rows are upserted by E.164 phone; bad rows come back as errors, never silent skips.
2. **Create a shift** — `POST /api/shifts` with role, location, time, pay, `headcount`, and an optional `event_at` ISO timestamp (this drives the confirmation pings).
3. **Outreach** — `POST /api/shifts/{id}/outreach` invites the next batch of contractors (default 5) in **priority order** (operator priority, then reliability), skipping opted-out workers and anyone already invited. Each invite is a real SMS ending in "Reply STOP to opt out."
4. **Live fill board** — `GET /api/shifts/{id}/board` returns every invite with YES / NO / MAYBE / confirmed status, needed-vs-filled counts, and **at-risk flags** (said yes, then went silent on the latest confirmation ping past a 2-hour grace window).
5. **Cascade** — `POST /api/shifts/{id}/cascade` backfills with the next batch down the priority list when someone declines.
6. **Voice escalation** — `POST /api/shifts/{id}/call/{contractor_id}` places a real outbound call to a specific worker through AgentPhone's hosted voice agent.
7. **Automatic confirmation pings** — a background loop (every 5 minutes, started in the app lifespan) sends **T-48h and T-4h** "reply YES to confirm" texts to everyone who accepted. A YES after a ping upgrades the worker to `confirmed`; silence flips the at-risk flag on the board. `POST /api/shifts/pings/run` triggers the sweep manually.

Inbound replies hit the signed AgentPhone webhook and are classified (`backend/app/shift_logic.py`): STOP/START first (compliance beats everything), then yes / no / maybe with ordering rules so "not sure" and "no, sorry" don't false-positive as yes. Free-text questions fall through to the Gemini auto-reply, which has the thread context.

## SMS compliance

- **STOP** (and the CTIA set: `STOPALL`, `UNSUBSCRIBE`, `CANCEL`, `END`, `QUIT`, `REVOKE`, `OPTOUT`, `OPT OUT`) opts a worker out. Matching is **exact-match on the trimmed body** (case-insensitive, trailing punctuation stripped) — "please don't cancel my shift" opts nobody out.
- Opt-out **persists on the contractor row** (`contractors.opted_out`) and blocks every send: future invites, confirmation pings, and escalation calls. Active invites are cancelled.
- **START** / `UNSTOP` / `SUBSCRIBE` / `OPT IN` opts back in.
- Every invite text carries **"Reply STOP to opt out."**

## Pilot mode vs demo mode

`DEMO_MODE` (env var, **default `false` = pilot mode**) is the demo-theater kill switch (`backend/app/config.py`, `backend/app/demo.py`). The rule from the June 2026 hardening: anything that fakes an external side effect must be impossible to reach by accident. In pilot mode these paths return **HTTP 501** (or `status: "disabled"` for non-route helpers) instead of fabricating success:

| Gated path | What it fakes |
|---|---|
| `POST /api/voice-call/demo` | Scripted 9-turn shift-offer call — the contractor side was always simulated; only the owner's ElevenLabs voice is real |
| Bulk-outreach demo (`backend/app/bulk_outreach.py`) | A handful of live texts plus **simulated contractor replies** to close the roster inside a 2-minute demo |
| Simulated vendor checkout (`backend/app/supplies.py`, behind `POST /api/events/{id}/supplies/approve`) | Fabricated Browser Use vendor evidence (URL, ETA, screenshot) |
| Invoice send (`backend/app/fulfillment.py`) | A fabricated AgentMail `message_id` — nothing is emailed |
| Worker payment holds/releases (`backend/app/fulfillment.py`, `backend/app/sponsors.py`) | Fabricated Sponge/Stripe refs — CrewLoop does not touch worker pay in v1 |

Set `DEMO_MODE=true` to re-enable all of it for demos; the server logs a warning at boot when demo mode is on.

## Auth

Set `APP_PASSWORD` and every request to `/api/*`, `/jobs*`, and `/dispatch*` must carry a matching **`X-App-Password`** header (constant-time compared). Webhooks stay open because they are HMAC-signature-verified; `/health`, docs, and static files stay open. When `APP_PASSWORD` is unset the API is open and the server logs a warning — fine for local dev, never for a deployed pilot. This is a **shared-password pilot gate**; per-operator auth is roadmap and replaces it before a second operator's roster is imported.

## The hackathon demo (DEMO_MODE)

The original build demonstrated a 14-step "fulfill this event" loop: owner texts about an event → Gemini infers a staffing plan and labor cost → shortlist by reliability → SMS + a scripted voice call → supply list grounded against a seeded inventory → Browser Use sessions for vendor shopping → invoice → conditional pay holds → proof → release. The chat-first intake (`POST /api/chat`, Gemini envelopes with action chips), the contractor/inventory/event browsing APIs, and the Event Fulfillment Room snapshots are still live code. The steps that faked side effects — scripted contractor replies, pretend checkout, fabricated invoice/payment refs — are the ones now gated behind `DEMO_MODE` (table above).

To run the scripted voice demo locally with `DEMO_MODE=true` (and `ELEVENLABS_API_KEY` set for real audio):

```bash
curl -X POST http://localhost:8000/api/voice-call/demo \
     -H 'Content-Type: application/json' \
     -H 'X-App-Password: <your APP_PASSWORD, if set>' \
     -d '{}'
```

It picks the most recent Saturday bartender shift and the highest-reliability bartender, synthesizes every owner line through ElevenLabs, and stores per-turn MP3s under `backend/app/static/voice-calls/` (generated at run time, not tracked in git). In pilot mode the same request returns `501`.

## Architecture

```
                          ┌──────────────────────────────┐
                          │       Operator / owner        │
                          └──────────────┬───────────────┘
                                         │ dashboard • SMS • call
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │   Next.js 16 dashboard (crewloop.ayushojha)  │
                  │   shifts • roster import • chat • dispatch   │
                  └──────────────┬───────────────────────────────┘
                                 │ HTTPS + X-App-Password
                                 ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │            FastAPI 0.115 (crewloop-api.ayushojha.com)               │
   │   APP_PASSWORD gate on /api/* /jobs* /dispatch*  ·  HMAC webhooks   │
   │                                                                     │
   │  /api/shifts  /api/contractors  /api/sms  /api/calls  /api/chat     │
   │  /api/events  /api/inventory  /jobs/*  /webhooks/*  /api/voice-call │
   └───┬───────────┬────────────┬────────────┬─────────────┬─────────────┘
       │           │            │            │             │
       ▼           ▼            ▼            ▼             ▼
   ┌────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐
   │Postgres│ │AgentPhone│ │ElevenLabs│ │Browser   │ │Gemini 3.1-pro / │
   │  17    │ │SMS+Voice │ │TTS (demo)│ │Use Cloud │ │ Flash           │
   └────────┘ └─────────┘ └──────────┘ └──────────┘ └─────────────────┘
       │
       └──► AgentMail • Stripe MPP • Sponge   (demo-gated paths)
```

The frontend never holds secrets — every external API is fronted by the FastAPI service. A background task in the app lifespan runs the T-48h/T-4h confirmation-ping sweep every 5 minutes.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI 0.115 + uvicorn** on **Python 3.12** (CI runs 3.11) | Async-first, OpenAPI-by-default, plays well with `asyncpg` |
| Database | **PostgreSQL 17** | Single source of truth for SMS, calls, shifts, invites |
| DB driver | **asyncpg** | Fastest Python Postgres driver, native pool |
| LLM | **Gemini 3.1-pro-preview** + **3-flash-preview** | Pro for plan inference & voice replies, Flash for SMS auto-reply |
| SMS + Voice transport | **AgentPhone Cloud** | One US 415 number, hosted voice mode, signed webhooks |
| Voice TTS | **ElevenLabs `eleven_turbo_v2_5`** | Cloned-voice synthesis for the demo call (demo-gated) |
| Browser automation | **Browser Use Cloud `/api/v3/sessions`** | Embeddable `live_url` iframes for the supplies demo |
| Payments | **Sponge** + **Stripe MPP** | Demo-gated hold/release refs; no real money movement in v1 |
| Email | **AgentMail** | Real send path exists; the invoice-send flow is demo-gated |
| Memory | **Supermemory** (`crewloop:owner:ayush` container) | Client wired, write/query stubbed |
| Frontend | **Next.js 16 + React 19 + Tailwind v4 + Turbopack** | App Router, server components, instant HMR |
| Tests / lint | **pytest 8 + anyio + ruff 0.9** | 77 tests, no DB required; ruff config in `backend/pyproject.toml` |
| CI | **GitHub Actions** (`.github/workflows/ci.yml`) | Backend: ruff + pytest · Frontend: `tsc --noEmit` |
| Deploy | **Coolify** on bare-metal VPS, **Traefik** + auto-SSL | Self-hosted, single-command rebuilds |

## Sponsor integrations

| Sponsor | Used for | Status |
|---|---|---|
| **AgentPhone** | All pilot SMS + voice (invites, pings, acks, escalation calls), signed webhooks | **Live** |
| **Gemini (Google)** | Plan inference, chat envelopes, SMS auto-reply, voice replies | **Live** (optional key) |
| **ElevenLabs** | Cloned-voice TTS for the scripted demo call | Demo-gated (`DEMO_MODE`) |
| **Browser Use** | Live `live_url` sessions for the supplies demo; the *simulated* checkout is demo-gated | Live sessions optional; simulation gated |
| **AgentMail** | Invoice email — the invoice-send flow fabricates ids and is demo-gated | Demo-gated |
| **Sponge** / **Stripe MPP** | Worker pay hold/release refs — fabricated, demo-gated; pilot returns `disabled` | Demo-gated |
| **Moss / Supermemory** | Per-owner long-term memory | Client wired, write/query stubbed |

## Repository layout

```
.
├── CrewLoop_Spec.md            # Product spec (sections §1–§15)
├── README.md                   # ← you are here
├── index.html                  # Landing page design handoff
├── .github/workflows/ci.yml    # CI: backend ruff+pytest, frontend tsc
├── docs/                       # Implementation notes (per module)
│   ├── agentphone-integration.md
│   └── frontend-nextjs.md
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app + lifespan + CORS + APP_PASSWORD gate
│   │   ├── config.py           # Pydantic settings; DATABASE_URL required, DEMO_MODE default false
│   │   ├── demo.py             # require_demo_mode(): 501s simulations in pilot mode
│   │   ├── shifts.py           # Fill-a-shift loop: outreach, board, pings, escalation (all real sends)
│   │   ├── shift_logic.py      # Pure logic: reply classification, STOP, CSV parsing, at-risk
│   │   ├── db.py               # asyncpg pool + INIT_SQL (auto-applied on boot)
│   │   ├── repo.py             # Storage helpers
│   │   ├── ai.py               # Gemini wrappers (SMS, voice, chat actions, JSON mode)
│   │   ├── agentphone.py       # AgentPhone REST client
│   │   ├── signature.py        # AgentPhone webhook HMAC verifier
│   │   ├── elevenlabs_client.py# ElevenLabs TTS wrapper (demo)
│   │   ├── browser_use_cloud.py# Browser Use /v3/sessions wrapper
│   │   ├── browser_import.py   # Browser-based roster/shift import (optional Playwright, SVG fallback)
│   │   ├── voice_call.py       # Scripted shift-offer orchestrator (demo-gated)
│   │   ├── bulk_outreach.py    # Demo bulk outreach with simulated replies (demo-gated)
│   │   ├── supplies.py         # Inventory grounding + live browse; simulated checkout is demo-gated
│   │   ├── fulfillment.py      # Plans, schedules, invoices, holds (send/hold paths demo-gated)
│   │   ├── sponsors.py         # Sponge + Stripe + AgentMail wrappers (simulations demo-gated)
│   │   ├── event_plan.py       # Event plan inference (Gemini JSON schema)
│   │   ├── dispatch_room.py    # Aggregated state for the fulfillment room
│   │   ├── routes/
│   │   │   ├── shifts.py       # /api/shifts/* — the pilot loop
│   │   │   ├── contractors.py  # /api/contractors + /api/contractors/import (CSV)
│   │   │   ├── sms.py          # /api/sms/send
│   │   │   ├── calls.py        # /api/calls/place
│   │   │   ├── voice_call.py   # /api/voice-call/* (demo-gated)
│   │   │   ├── chat.py         # /api/chat
│   │   │   ├── events.py       # /api/events/* + supplies sub-routes
│   │   │   ├── inventory.py    # /api/inventory
│   │   │   ├── jobs.py         # /jobs/* lifecycle (spec §10)
│   │   │   ├── conversations.py# Dashboard read endpoints
│   │   │   ├── dispatch.py     # Event Fulfillment Room snapshots
│   │   │   ├── browser.py      # Browser-use roster import
│   │   │   └── webhooks.py     # /webhooks/{agentphone,agentmail,stripe,sponge}
│   │   └── static/             # Generated media (portraits, inventory, voice MP3s) — not tracked in git
│   ├── tests/                  # 77 tests: shift logic, STOP, CSV, at-risk, signature, demo gates, wiring
│   ├── scripts/
│   │   ├── init_db.sql         # Canonical schema
│   │   ├── provision_agentphone.py  # Buys a US number, creates the agent
│   │   ├── seed_contractors.py # Demo roster seed
│   │   ├── seed_inventory.py   # Demo inventory seed (images generated at seed time)
│   │   └── seed_events.py      # Demo events across all statuses
│   ├── .env.example            # Canonical env-var names (values live in repo-root .env.local)
│   ├── requirements.txt        # Runtime deps
│   ├── requirements-dev.txt    # + pytest, anyio, ruff
│   ├── pyproject.toml          # ruff + pytest config
│   └── Dockerfile
└── frontend/
    └── src/app/                # Next.js App Router pages (see frontend note below)
```

**Frontend note:** the demo-era pages (`/chat`, `/dispatch/[jobId]`, `/contractors`, `/events`, `/dashboard`, `/conversations`, `/home`, `/browser-import`, `/bay-events`) are in the tree. The pilot dashboard surfaces ship in this hardening: `/shifts` (create + list), `/shifts/[id]` (live fill board, polls every 5s), and `/contractors/import` (roster CSV upload), all wrapped in `<PasswordGate>`, which sends the `X-App-Password` header from local storage.

**Generated media:** the Gemini-generated portraits, inventory photos, and demo-call MP3s under `backend/app/static/` are produced at seed/demo time and are **not tracked in git** (`.gitignore` covers them); deployed instances keep them on disk/CDN.

## Quickstart

### Prerequisites

- Python **3.11+** (3.12 in the production image)
- Node.js **20+** and `npm`
- A PostgreSQL **17** database you can reach — `DATABASE_URL` is **required**; the app refuses to boot without it
- An `AGENTPHONE_API_KEY` (also required at boot; any non-empty string works for local dev without live sends)

### 1. Clone & configure

Config is read from the **repo root** `.env` / `.env.local` (see `backend/app/config.py`).

**Windows (PowerShell):**

```powershell
git clone https://github.com/ayushozha/crewloop.git
cd crewloop
Copy-Item backend\.env.example .env.local
# edit .env.local: set DATABASE_URL (required), AGENTPHONE_API_KEY, GEMINI_API_KEY, APP_PASSWORD…
```

**macOS / Linux (bash):**

```bash
git clone https://github.com/ayushozha/crewloop.git
cd crewloop
cp backend/.env.example .env.local
# edit .env.local: set DATABASE_URL (required), AGENTPHONE_API_KEY, GEMINI_API_KEY, APP_PASSWORD…
```

### 2. Backend

**Windows (PowerShell):**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

**macOS / Linux (bash):**

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000` with Swagger at `/docs`. The schema is auto-applied on startup via `db.ensure_schema()`.

### 3. Frontend

```bash
cd ../frontend
npm install
npm run dev  # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` to point the local dashboard at your local API.

### 4. Try the pilot loop

```bash
# Import a roster (CSV with at least name + phone columns)
curl -X POST http://localhost:8000/api/contractors/import \
     -H 'Content-Type: application/json' \
     -d '{"csv_text":"name,phone,roles,priority\nSam Rivera,4155550101,bartender,1\n"}'

# Create a shift
curl -X POST http://localhost:8000/api/shifts \
     -H 'Content-Type: application/json' \
     -d '{"role":"bartender","location":"SoMa","start_time":"Saturday 6:00 PM","pay_amount":135,"headcount":2,"event_at":"2026-06-13T18:00:00-07:00"}'

# Send the first outreach batch (real SMS — needs live AgentPhone credentials)
curl -X POST http://localhost:8000/api/shifts/<id>/outreach -H 'Content-Type: application/json' -d '{}'

# Watch the board fill
curl http://localhost:8000/api/shifts/<id>/board
```

If `APP_PASSWORD` is set, add `-H 'X-App-Password: <password>'` to every `/api/*` request.

## Environment variables

Names live in [`backend/.env.example`](./backend/.env.example); values go in the repo-root `.env.local`, never in git.

| Variable | Default | Effect |
|---|---|---|
| `DATABASE_URL` | **none — required, app refuses to boot** | asyncpg Postgres DSN. The old hardcoded fallback (which leaked a real password) was removed |
| `DEMO_MODE` | `false` (pilot mode) | `true` re-enables the simulated demo flows; otherwise they 501 / report `disabled` |
| `APP_PASSWORD` | unset (open, warning logged) | Requires `X-App-Password` on `/api/*`, `/jobs*`, `/dispatch*`. Set it on any deployed instance |
| `AGENTPHONE_API_KEY` | **none — required at boot** | AgentPhone Cloud token (live sends need a real one) |
| `AGENTPHONE_BASE_URL` | `https://api.agentphone.ai/v1` | API base |
| `AGENTPHONE_AGENT_ID` / `AGENTPHONE_NUMBER_ID` / `AGENTPHONE_FROM_NUMBER` | unset | Populated by `scripts/provision_agentphone.py`; needed for live SMS/voice |
| `AGENTPHONE_WEBHOOK_SECRET` | unset | HMAC verification of inbound webhooks (skipped when unset) |
| `AGENTPHONE_WEBHOOK_URL` | production URL | Public webhook endpoint registered with AgentPhone |
| `GEMINI_API_KEY` | unset | Chat intake, plan inference, SMS auto-reply (features no-op without it) |
| `GEMINI_MODEL_FAST` / `GEMINI_MODEL_PRO` | `gemini-3-flash-preview` / `gemini-3.1-pro-preview` | Model selection |
| `ELEVENLABS_API_KEY` | unset | TTS for the demo voice call (demo-gated; silent fallback without it) |
| `ELEVENLABS_VOICE_ID` / `ELEVENLABS_MODEL_ID` | cloned voice / `eleven_turbo_v2_5` | Voice + model for demo TTS |
| `BROWSER_USE_API_KEY` / `BROWSER_USE_BASE_URL` / `BROWSER_USE_MODEL` | unset / v3 API / `bu-mini` | Live `live_url` browse sessions for the supplies demo |
| `AGENTMAIL_API_KEY` / `AGENTMAIL_BASE_URL` / `AGENTMAIL_INBOX_NAME` / `AGENTMAIL_INBOX_ID` | unset | Email send path (the invoice-send simulation is demo-gated) |
| `SPONGE_API_KEY` / `SPONGE_MCP_API_KEY` / `SPONGE_MCP_URL` / `STRIPE_API_KEY` | unset | Payment refs — demo-gated paths only; no real money movement in v1 |
| `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` / `SUPERMEMORY_API_KEY` / `SUPERMEMORY_CONTAINER_TAG` | unset | Memory integrations (stubbed) |

## Data model

All tables live in the `crewloop` Postgres database. `db.ensure_schema()` runs on startup and is idempotent.

| Table | Purpose |
|---|---|
| `contractors` | Roster: name, phone, rate, reliability, **`priority`** (lower = called first), **`opted_out`** (STOP compliance) |
| `contractor_skills` | Many-to-many role/skill tags per contractor |
| `jobs` | Shift/event lifecycle, plus **`headcount`** and **`event_at`** (drives T-48h/T-4h pings) |
| `shift_invites` | Per-shift invite state: batch, status (`invited`/`yes`/`maybe`/`no`/`confirmed`/`cancelled`), ping timestamps, last reply |
| `conversations` / `messages` | SMS threads keyed by E.164 phone |
| `calls` | Outbound voice call records (transport-level) |
| `voice_calls` / `voice_call_turns` | Scripted demo calls + per-turn audio (demo) |
| `inventory_items` / `event_supplies` / `browser_sources` | Supplies demo: items, recommendations, Browser Use evidence |
| `event_plans` / `schedules` | Inferred crew plans + schedule rows |
| `client_invoices` / `worker_payments` / `proofs` | Invoice, hold, and proof records (write paths demo-gated) |
| `chat_threads` / `chat_messages` | Per-owner chat history with structured envelopes |

## API reference

Interactive Swagger lives at `/docs`, the machine-readable spec at `/openapi.json`. With `APP_PASSWORD` set, all of the below (except webhooks and `/health`) require the `X-App-Password` header.

### Fill-a-shift loop (pilot — all sends real)

| Endpoint | What it does |
|---|---|
| `POST /api/shifts` | Create a shift: role, location, start/end time, pay, `headcount`, optional `event_at` |
| `GET /api/shifts` | List open shifts with invited/yes counts |
| `GET /api/shifts/{id}/board` | Live fill board: invites with YES/NO/MAYBE/confirmed status, needed-vs-filled counts, at-risk flags |
| `POST /api/shifts/{id}/outreach` | Invite the next priority batch over real SMS (`batch_size` ≤ 50, `match_role`) |
| `POST /api/shifts/{id}/cascade` | One-click backfill: next batch down the priority list |
| `POST /api/shifts/{id}/call/{contractor_id}` | Real voice escalation call to one worker (409 if opted out) |
| `POST /api/shifts/pings/run` | Manually trigger the T-48h/T-4h confirmation-ping sweep (also runs every 5 min) |
| `POST /api/contractors/import` | Roster CSV import — `name`, `phone` required; `roles`, `priority`, `rate`, `notes`, `email`, `location` optional |

### Conversations, SMS & voice

```
POST /api/sms/send                   # Outbound SMS via AgentPhone
POST /api/calls/place                # Outbound transport-level voice call
GET  /api/conversations              # All threads with last-message preview
GET  /api/conversations/{phone}      # Full SMS + call thread for one number
POST /api/voice-call/demo            # Scripted demo call — 501 unless DEMO_MODE=true
GET  /api/voice-call[/{id}]          # Demo call transcripts + MP3 paths
```

### Chat, contractors & inventory

```
POST /api/chat                       # Owner message → structured envelope (Gemini)
GET  /api/contractors                # Roster + skills + reliability
GET  /api/inventory                  # Inventory items
```

### Events + supplies (demo surface)

```
GET  /api/events                       # All events with status
POST /api/events/{id}/supplies/recommend
POST /api/events/{id}/supplies/approve   # Simulated vendor checkout — 501 unless DEMO_MODE=true
POST /api/events/{id}/supplies/browse    # Real parallel Browser Use sessions (needs BROWSER_USE_API_KEY)
POST /api/events/{id}/supplies/pay       # Attaches demo payment refs to approved items
```

### Jobs lifecycle (spec §10 — fabricating steps demo-gated)

```
POST /jobs                                  # Create job
POST /jobs/{id}/infer-event-plan            # Gemini-inferred crew plan
POST /jobs/{id}/schedule                    # Schedule rows
POST /jobs/{id}/invoice                     # Draft client invoice
POST /jobs/{id}/send-invoice                # 501 unless DEMO_MODE (fabricated AgentMail id)
POST /jobs/{id}/payment-holds               # 501 unless DEMO_MODE (fabricated Sponge refs)
POST /jobs/{id}/release-payments            # Demo-gated likewise
POST /jobs/{id}/proofs                      # Submit proof
```

### Webhooks (HMAC-verified, no password required)

```
POST /webhooks/agentphone            # Signed inbound SMS/voice → STOP/START → shift replies → AI auto-reply
POST /webhooks/agentmail             # Email delivery events
POST /webhooks/stripe                # Invoice paid
POST /webhooks/sponge                # Hold/release events
```

## Tests & CI

77 tests live in `backend/tests/` and run without a database or any real keys (`conftest.py` stubs the required env):

- `test_shift_logic.py` (66) — reply classification (YES/NO/MAYBE ordering rules), STOP/START exact-match compliance, phone normalization, roster CSV parsing, at-risk logic, invite/ping message text
- `test_signature.py` (6) — AgentPhone webhook HMAC verification
- `test_demo_gate.py` (5) — pilot mode 501s every simulation, demo mode allows them, app wiring (routers + middleware import cleanly)

Run the same gate CI runs, from `backend/`:

**Windows (PowerShell):**

```powershell
.venv\Scripts\ruff check app tests
.venv\Scripts\pytest
```

**macOS / Linux (bash):**

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest
```

Both pass on the current tree (`All checks passed!`, `77 passed`). GitHub Actions ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)) runs backend ruff + pytest (Python 3.11) and frontend `tsc --noEmit` (Node 22) on every PR and push to `main`. Ruff config is in [`backend/pyproject.toml`](./backend/pyproject.toml). Dev deps (`pytest`, `anyio`, `ruff`) are pinned in [`backend/requirements-dev.txt`](./backend/requirements-dev.txt); the Playwright dependency from the hackathon build was removed (the browser-import screenshot path falls back to an SVG evidence card without it).

## Seeding demo data

The seed scripts populate the demo fixtures (roster, ~130 inventory items, ~25 events across all statuses). Portrait and inventory images are **generated at seed time** via Gemini and written to `backend/app/static/` — they are not tracked in git.

```bash
cd backend
python scripts/seed_inventory.py    # inventory + images (Gemini, ~$1.50)
python scripts/seed_events.py       # demo events across statuses
python scripts/seed_contractors.py  # demo roster — pilots should use POST /api/contractors/import instead
```

To provision a real AgentPhone number and agent:

```bash
python scripts/provision_agentphone.py --area-code 415
# Writes AGENTPHONE_AGENT_ID, AGENTPHONE_NUMBER_ID, AGENTPHONE_FROM_NUMBER back into the env file
```

## Deployment

Production runs on a single VPS managed by Coolify, fronted by Traefik with auto-SSL.

| Component | Domain |
|---|---|
| API (FastAPI) | `crewloop-api.ayushojha.com` |
| Dashboard (Next.js) | `crewloop.ayushojha.com` |
| Postgres | shared `projects-db` (internal) |

Both services build from `Dockerfile`s in their respective folders. The schema is auto-applied on boot via `db.ensure_schema()` — no separate migration step. A deployed instance must set `DATABASE_URL`, `AGENTPHONE_API_KEY`, and `APP_PASSWORD`, and should leave `DEMO_MODE` unset/false.

Health probe: `GET /health` → `{"status":"ok"}` (no password required).

## Roadmap

CrewLoop is a hackathon demo being hardened for concierge pilots (June 2026). No pilots are live yet. In rough order:

- **Per-operator auth** — replaces the shared `APP_PASSWORD` gate before a second operator's roster is imported.
- **Frontend pilot surfaces** — `/shifts`, `/shifts/[id]` board, `/contractors/import`, password gate (in progress).
- **Real STT on escalation calls** — today the hosted AgentPhone voice agent handles the conversation; richer transcripts and structured outcomes are next.
- **Real vendor checkout** — replace the demo-gated `simulate_vendor_checkout` with full Browser Use checkout against a real vendor sandbox.
- **Worker pay** — v1 deliberately does not touch money; the Sponge/Stripe hold/release plumbing stays demo-gated until that changes.
- **Supermemory write/query** in the chat flow.
- Mobile-native operator app.

## License

This project is currently unlicensed — no LICENSE file is checked in, and all rights are reserved by the author until a formal license is chosen. If you want to use any of this code, please reach out first.

---

<div align="center">

Born at a hackathon. Hardened for pilots. Every pilot-loop send is a real SMS or a real call — the demo theater is behind a switch.

[Spec](./CrewLoop_Spec.md) · [CI workflow](./.github/workflows/ci.yml) · [Backend tests](./backend/tests)

</div>
