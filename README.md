<div align="center">

# CrewLoop

**AI ops dispatcher for event businesses.**
Turn a messy client text into a staffed, stocked, invoiced, and payment-ready job — in one chat.

[![Production API](https://img.shields.io/badge/api-crewloop--api.ayushojha.com-0a7cff?style=flat-square)](https://crewloop-api.ayushojha.com/health)
[![Dashboard](https://img.shields.io/badge/dashboard-crewloop.ayushojha.com-111?style=flat-square)](https://crewloop.ayushojha.com)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Postgres](https://img.shields.io/badge/Postgres-17-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

</div>

---

## Table of contents

- [What is CrewLoop?](#what-is-crewloop)
- [Why it exists](#why-it-exists)
- [The 14-step fulfillment loop](#the-14-step-fulfillment-loop)
- [Live demo](#live-demo)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Sponsor integrations](#sponsor-integrations)
- [Repository layout](#repository-layout)
- [Quickstart](#quickstart)
- [Environment variables](#environment-variables)
- [Data model](#data-model)
- [API reference](#api-reference)
- [Voice & SMS demo](#voice--sms-demo)
- [Seeding demo data](#seeding-demo-data)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [License](#license)

---

## What is CrewLoop?

CrewLoop is an **AI operations dispatcher for event businesses** — catering, event staffing, venue ops, cleaning crews, photographers, hospitality, security, field service. The pitch is one sentence:

> Tell CrewLoop about an event, and it finds the right crew, confirms availability, buys required supplies, invoices the client, and holds worker pay until the job is completed.

The product is built around **one unified workflow: fulfill this event.** Staffing, supplies, invoicing, and worker pay are not separate products — they are steps inside the same fulfillment loop, all coordinated from a single chat thread and a single dispatch room.

## Why it exists

Event businesses run on messy operational threads: client texts, contractor rosters, vendor websites, supply runs, invoices, and conditional worker pay. Today the owner manually asks follow-up questions, infers crew, checks contractor availability and reliability, texts and calls workers, fills gaps with backups, creates a schedule, buys supplies, prepares the invoice, holds worker pay, collects proof of work, and finally releases payment.

CrewLoop collapses that into a guided AI workflow that starts in chat, asks only the minimum clarifying questions, uses real browser automation when source evidence is needed, and orchestrates everything else through sponsor APIs.

## The 14-step fulfillment loop

1. Owner texts CrewLoop about an event.
2. CrewLoop asks **3 structured questions**: event type, timing, infer-roles vs. owner-specified.
3. Infers the staffing plan and responsibilities.
4. Creates a recommended crew plan with labor-cost estimate.
5. Shortlists contractors using reliability, distance, history, no-show risk.
6. Asks owner approval before contacting workers.
7. Sends SMS to most contractors, **places a live phone call** to urgent/key roles.
8. Fills open roles with backups when someone declines.
9. Creates the event schedule and sends contractor confirmations.
10. Infers a short supply list and asks owner approval before purchase.
11. Uses **Browser Use Cloud** to check or simulate vendor checkout with live evidence.
12. Prepares and sends the client invoice.
13. Creates **conditional worker pay holds** (Sponge / Stripe MPP).
14. Collects proof of check-in and completion, then releases worker pay.

## Live demo

| Surface | URL |
|---|---|
| **Owner dashboard (Next.js)** | https://crewloop.ayushojha.com |
| **API + Swagger docs** | https://crewloop-api.ayushojha.com/docs |
| **API landing page** | https://crewloop-api.ayushojha.com |
| **Health probe** | https://crewloop-api.ayushojha.com/health |
| **SMS number (AgentPhone, US 415)** | `+1 (415) 992-9589` |

The chat-first intake lives at [`/chat`](https://crewloop.ayushojha.com/chat). The Event Fulfillment Room (all 9 spec §8 panels) lives at [`/dispatch/{jobId}`](https://crewloop.ayushojha.com/dispatch).

## Features

### Chat-first event intake
Multimodal Gemini-powered chat with **structured action chips** (event type, timing, infer roles, approve shortlist, send outreach, view invoice). Every chat message returns a typed envelope (`event_plan`, `event_draft`, `action_chips`, `shortlist`, `bulk_outreach`, `invoice_email`) so the UI can render rich cards inline instead of plain text.

### Contractor roster with portraits
37 contractors across 8 roles (bartender, server, setup, event lead, cleanup, photographer, security, captain) with **Gemini-generated portraits**, reliability scores, hourly rates, response-time stats, and Moss-style memory hooks.

### Inventory & supplies panel
130+ inventory items (also Gemini-imaged) covering bar, glassware, garnish, linens, tables, ice. Gemini grounds supply recommendations against the live inventory rows. The supplies UI runs **real Browser Use Cloud parallel sessions** with embedded `live_url` iframes — the owner literally watches the agent shop in real time, then confirms the cart with **Sponge** or **Stripe MPP**.

### Real SMS + voice
AgentPhone Cloud wires both inbound and outbound. Inbound SMS auto-replies through Gemini 3 Flash. Outbound voice calls run a **9-turn scripted shift-offer flow** where every owner line is synthesized through **ElevenLabs** in a cloned voice and stored as static MP3s the dashboard plays back in sequence.

### Event Fulfillment Room
A single `/dispatch/{jobId}` page consolidates the 9 spec §8 panels:
1. Event Request Card
2. Live Timeline
3. Crew Plan
4. Supply Panel
5. Invoice Panel
6. Worker Payment Panel (conditional holds + release)
7. Proof Panel
8. Owner Summary
9. Web Source Panel

### Conditional worker payment
Each accepted contractor gets a **payment hold** with five release rules: accepted assignment, check-in, shift complete, proof submitted, owner approval. Backed by Sponge (`spg_*`) or Stripe MPP (`pi_*`) references.

### Postgres persistence
Every SMS, call, voice turn, chat message, event plan, schedule, invoice, payment, and proof is durably stored in Postgres — no JSON-on-disk hacks in production.

## Architecture

```
                          ┌──────────────────────────────┐
                          │     Owner / Bay Events Co.   │
                          └──────────────┬───────────────┘
                                         │ chat • SMS • call
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │  Next.js 16 dashboard (crewloop.ayushojha)   │
                  │  /chat • /dispatch • /contractors • /events  │
                  └──────────────┬───────────────────────────────┘
                                 │ HTTPS / CORS
                                 ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │            FastAPI 0.115 (crewloop-api.ayushojha.com)               │
   │                                                                     │
   │  /api/chat   /api/sms   /api/calls   /api/voice-call   /api/events  │
   │  /api/contractors  /api/inventory  /jobs/*  /webhooks/*  /api/...   │
   └───┬───────────┬────────────┬────────────┬─────────────┬─────────────┘
       │           │            │            │             │
       ▼           ▼            ▼            ▼             ▼
   ┌────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐
   │Postgres│ │AgentPhone│ │ElevenLabs│ │Browser   │ │Gemini 3.1-pro / │
   │  17    │ │SMS+Voice │ │  TTS     │ │Use Cloud │ │ Flash + image   │
   └────────┘ └─────────┘ └──────────┘ └──────────┘ └─────────────────┘
       │
       └──► AgentMail • Stripe MPP • Sponge • Moss / Supermemory
```

The frontend never holds secrets — every external API is fronted by the FastAPI service. The Next.js client only talks to `crewloop-api.ayushojha.com`.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI 0.115 + uvicorn** on **Python 3.12** | Async-first, OpenAPI-by-default, plays well with `asyncpg` |
| Database | **PostgreSQL 17** (shared `projects-db`) | Single source of truth for SMS, calls, jobs, payments, proofs |
| DB driver | **asyncpg** | Fastest Python Postgres driver, native pool |
| LLM | **Gemini 3.1-pro-preview** + **3-flash-preview** | Pro for plan inference & voice replies, Flash for SMS auto-reply |
| Image gen | **Gemini 3.1-flash-image-preview** | Contractor portraits + inventory imagery |
| Voice TTS | **ElevenLabs `eleven_turbo_v2_5`** | Sub-second cloned-voice synthesis |
| SMS + Voice transport | **AgentPhone Cloud** | One US 415 number, hosted voice mode, signed webhooks |
| Browser automation | **Browser Use Cloud `/api/v3/sessions`** | Embeddable `live_url` iframes, parallel sessions |
| Payments | **Sponge** + **Stripe MPP** | Conditional holds + invoice payment links |
| Memory | **Supermemory** (`crewloop:owner:ayush` container) | Per-owner long-term roster + client memory |
| Email | **AgentMail** | Invoices, owner summaries, final job reports |
| Frontend | **Next.js 16 + React 19 + Tailwind v4 + Turbopack** | App Router, server components, instant HMR |
| Deploy | **Coolify** on bare-metal VPS, **Traefik** + auto-SSL | Self-hosted, single-command rebuilds |

## Sponsor integrations

| Sponsor | Used for | Status |
|---|---|---|
| **AgentPhone** | SMS + outbound voice (`+1 415-992-9589`, agent `cmpa98n3x0dd7jz00wunzjz7a`) | Live, signed webhooks |
| **AgentMail** | Client invoice email, owner summary, final job report | Wired (simulated send) |
| **Browser Use** | Live `live_url` sessions for vendor checkout & roster import | Live, parallel sessions |
| **Sponge** | Conditional worker pay holds with release rules | Wired |
| **Stripe / MPP** | Client invoice payment links | Wired |
| **Moss / Supermemory** | Per-owner long-term contractor + client memory | Wired client, write/query stubbed |
| **Gemini (Google)** | Plan inference, chat envelopes, SMS reply, voice replies, image gen | Live |
| **ElevenLabs** | Cloned-voice TTS for the live demo call | Live |

## Repository layout

```
.
├── CrewLoop_Spec.md            # Product spec (sections §1–§15)
├── README.md                   # ← you are here
├── docs/                       # Implementation notes (per module)
│   ├── agentphone-integration.md
│   └── frontend-nextjs.md
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app + lifespan + CORS + static mount
│   │   ├── db.py               # asyncpg pool + INIT_SQL (auto-applied on boot)
│   │   ├── config.py           # Pydantic settings (all sponsor keys)
│   │   ├── repo.py             # Storage helpers (Postgres + local JSON fallback)
│   │   ├── ai.py               # Gemini wrappers (SMS, voice, chat actions, JSON mode)
│   │   ├── agentphone.py       # AgentPhone REST client
│   │   ├── elevenlabs_client.py# ElevenLabs TTS wrapper
│   │   ├── browser_use_cloud.py# Browser Use /v3/sessions wrapper
│   │   ├── voice_call.py       # 9-turn scripted shift-offer orchestrator
│   │   ├── supplies.py         # Inventory grounding + parallel browse + payment
│   │   ├── fulfillment.py      # Spec §9 / §10: plans, schedules, invoices, holds
│   │   ├── event_plan.py       # Event plan inference (Gemini JSON schema)
│   │   ├── bulk_outreach.py    # Multi-contractor SMS fan-out
│   │   ├── invoice_email.py    # Invoice draft + AgentMail send
│   │   ├── dispatch_room.py    # Aggregated state for the fulfillment room
│   │   ├── supermemory_client.py
│   │   ├── workflow.py
│   │   ├── signature.py        # AgentPhone webhook signature verifier
│   │   ├── sponsors.py         # Sponge + Stripe wrappers
│   │   ├── routes/
│   │   │   ├── sms.py          # /api/sms/*
│   │   │   ├── calls.py        # /api/calls/*
│   │   │   ├── voice_call.py   # /api/voice-call/* (demo TTS calls)
│   │   │   ├── chat.py         # /api/chat
│   │   │   ├── contractors.py  # /api/contractors
│   │   │   ├── inventory.py    # /api/inventory
│   │   │   ├── events.py       # /api/events/*
│   │   │   ├── jobs.py         # /jobs/* lifecycle (spec §10)
│   │   │   ├── conversations.py# Dashboard read endpoints
│   │   │   ├── dispatch.py     # Event Fulfillment Room snapshots
│   │   │   ├── browser.py      # Browser Use roster import
│   │   │   └── webhooks.py     # /webhooks/{agentphone,agentmail,stripe,sponge}
│   │   └── static/             # Portraits, inventory images, voice-call MP3s
│   ├── scripts/
│   │   ├── init_db.sql         # Canonical schema
│   │   ├── provision_agentphone.py  # Buys US-415 number, creates agent
│   │   ├── seed_contractors.py # Roster + portraits (not committed)
│   │   ├── seed_inventory.py   # 130 items + portraits
│   │   └── seed_events.py      # 25 demo events across all statuses
│   ├── .env.example
│   ├── pyproject.toml
│   └── Dockerfile
└── frontend/
    └── src/app/
        ├── page.tsx            # Landing page (design handoff)
        ├── chat/               # Chat-first intake
        ├── dispatch/[jobId]/   # Event Fulfillment Room (9 panels)
        ├── contractors/        # Roster page
        ├── events/             # Events list + supplies sub-page
        ├── dashboard/          # SMS + call dashboard
        ├── conversations/      # Per-thread SMS/voice transcript
        ├── home/               # Owner home (Dashboard.html handoff)
        ├── browser-import/     # Browser-use roster import
        └── bay-events/         # Demo staffing scenario page
```

## Quickstart

### Prerequisites

- Python **3.12+** and [`uv`](https://docs.astral.sh/uv/) or `pip`
- Node.js **20+** and `npm`
- PostgreSQL **17** running locally **or** an SSH tunnel to the shared `projects-db` container
- (Optional) Real API keys for AgentPhone, Gemini, ElevenLabs, Browser Use — without them, the service starts cleanly and stubs out external calls

### 1. Clone

```bash
git clone https://github.com/ayushozha/crewloop.git
cd crewloop
```

### 2. Backend

```bash
cd backend
cp .env.example .env.local
# fill in GEMINI_API_KEY, AGENTPHONE_API_KEY, etc. (see `.env.example`)

pip install -e .
# or: uv sync

# If using the shared projects-db over SSH, open the tunnel first:
# ssh -L 5433:127.0.0.1:5433 ayush@72.62.82.57 -N

# Schema is auto-applied on startup via db.ensure_schema().
uvicorn app.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000` with Swagger at `/docs`.

### 3. Frontend

```bash
cd ../frontend
npm install
npm run dev  # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` if you want the local dashboard to talk to your local API instead of production.

### 4. Seed demo data

```bash
cd backend
python scripts/seed_inventory.py    # 130 inventory items with images (Gemini, ~$1.50)
python scripts/seed_events.py       # 25 events across 6 statuses
# (seed_contractors.py is private — use your own roster)
```

### 5. Provision AgentPhone (optional)

```bash
python scripts/provision_agentphone.py --area-code 415
# Writes AGENTPHONE_AGENT_ID, AGENTPHONE_NUMBER_ID, AGENTPHONE_FROM_NUMBER
# back into .env.local
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Plan inference, chat, SMS replies, image gen |
| `GEMINI_MODEL_FAST` | no | Default `gemini-3-flash-preview` |
| `GEMINI_MODEL_PRO` | no | Default `gemini-3.1-pro-preview` |
| `DATABASE_URL` | yes | `postgres://…/crewloop?sslmode=disable` |
| `AGENTPHONE_API_KEY` | yes (live SMS/call) | AgentPhone Cloud token |
| `AGENTPHONE_BASE_URL` | no | Default `https://api.agentphone.ai/v1` |
| `AGENTPHONE_AGENT_ID` | yes | Populated by provision script |
| `AGENTPHONE_NUMBER_ID` | yes | Populated by provision script |
| `AGENTPHONE_FROM_NUMBER` | yes | E.164 number used to send |
| `AGENTPHONE_WEBHOOK_SECRET` | yes | HMAC secret for inbound webhooks |
| `AGENTPHONE_WEBHOOK_URL` | yes | Public webhook endpoint |
| `AGENTMAIL_API_KEY` / `AGENTMAIL_BASE_URL` / `AGENTMAIL_INBOX_NAME` | optional | Invoice + summary email |
| `BROWSER_USE_API_KEY` | optional | Real `live_url` sessions; falls back to `sim_*` stubs |
| `ELEVENLABS_API_KEY` | optional | TTS for the voice-call demo |
| `ELEVENLABS_VOICE_ID` | optional | Default cloned-voice id |
| `ELEVENLABS_MODEL_ID` | optional | Default `eleven_turbo_v2_5` |
| `SPONGE_API_KEY` / `SPONGE_MCP_API_KEY` / `SPONGE_MCP_URL` | optional | Worker pay holds |
| `STRIPE_API_KEY` | optional | Client invoice payment links |
| `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` | optional | Moss memory |
| `SUPERMEMORY_API_KEY` / `SUPERMEMORY_CONTAINER_TAG` | optional | Long-term owner memory |

**Secrets policy:** Real credentials live in `.env.local` only. `.env.example` documents the names and shape, never values. The committed `.env.example` is the canonical source of truth for env-var names.

## Data model

All tables live in the `crewloop` Postgres database. `db.ensure_schema()` runs on startup and is idempotent.

| Table | Purpose |
|---|---|
| `conversations` | One row per E.164 contractor phone number |
| `messages` | SMS + system messages, threaded by `conversation_id` |
| `calls` | Outbound voice call records (transport-level) |
| `voice_calls` | High-level scripted demo calls (one per session) |
| `voice_call_turns` | Per-turn role + text + MP3 path + audio bytes |
| `contractors` | Roster: name, role, reliability, rate, response time, portrait URL |
| `contractor_skills` | Many-to-many skill tags per contractor |
| `jobs` | Event/job lifecycle: drafting → shortlisting → outreach → accepted → completed |
| `inventory_items` | 130-item bar inventory with image URLs |
| `event_supplies` | Per-event supply recommendation + approval + receipt |
| `browser_sources` | Browser Use evidence: `live_url`, status, screenshots |
| `event_plans` | Spec §9 inferred plans (crew + responsibilities + labor cost) |
| `schedules` | Spec §10 schedule rows per job |
| `client_invoices` | Invoice + Stripe MPP reference + send state |
| `worker_payments` | Per-contractor pay hold + release-rule checklist |
| `proofs` | Check-in + completion proof (photo, geolocation, signature) |
| `chat_threads` / `chat_messages` | Per-owner chat history with structured envelopes |

## API reference

The full machine-readable spec lives at [`/openapi.json`](https://crewloop-api.ayushojha.com/openapi.json) and the interactive Swagger at [`/docs`](https://crewloop-api.ayushojha.com/docs). Highlights:

### Chat (intake)
```
POST /api/chat                       # Owner message → structured envelope
```

### Conversations & SMS
```
POST /api/sms/send                   # Outbound SMS via AgentPhone
GET  /api/conversations              # All threads with last-message preview
GET  /api/conversations/{phone}      # Full SMS + call thread for one number
```

### Voice
```
POST /api/calls/place                # Outbound transport-level voice call
POST /api/voice-call/demo            # Full 9-turn scripted ElevenLabs call
GET  /api/voice-call/{id}            # Transcript + MP3 paths for the player
GET  /api/voice-call                 # Recent demo calls
```

### Contractors & inventory
```
GET  /api/contractors                # Roster + skills + reliability
GET  /api/inventory                  # Bar inventory items + images
```

### Events + supplies
```
GET  /api/events                     # All events with status
POST /api/events/{id}/supplies/recommend
POST /api/events/{id}/supplies/approve
POST /api/events/{id}/supplies/browse  # Starts parallel Browser Use sessions
POST /api/events/{id}/supplies/pay     # Sponge or Stripe MPP checkout
```

### Jobs lifecycle (spec §10)
```
POST /jobs                                  # Create job
POST /jobs/{id}/infer-event-plan            # Gemini-inferred crew plan
POST /jobs/{id}/schedule                    # Schedule rows
POST /jobs/{id}/invoice                     # Draft client invoice
POST /jobs/{id}/send-invoice                # AgentMail send
POST /jobs/{id}/payment-holds               # Sponge/Stripe holds
POST /jobs/{id}/release-payments            # Conditional release
POST /jobs/{id}/proofs                      # Submit proof
POST /jobs/{id}/recommend-supplies
POST /jobs/{id}/approve-supplies
```

### Webhooks
```
POST /webhooks/agentphone            # Signed inbound SMS/voice
POST /webhooks/agentmail             # Email delivery events
POST /webhooks/stripe                # Invoice paid
POST /webhooks/sponge                # Hold/release events
```

## Voice & SMS demo

The voice call is the most visible piece of the demo. Triggering it is a single curl:

```bash
curl -X POST https://crewloop-api.ayushojha.com/api/voice-call/demo \
     -H 'Content-Type: application/json' \
     -d '{}'
```

The server picks the most recent **Saturday** bartender shift + the **highest-reliability bartender** in the roster, then runs a 9-turn shift-offer conversation. Every owner line is synthesized through ElevenLabs in a cloned voice; every contractor line is scripted. MP3s are persisted to `backend/app/static/voice-calls/{call_id}/{turn:02d}.mp3` and exposed via `/static/voice-calls/...`.

The opening line is fixed:

> *"Hi this is Ayush, I'm calling on behalf of CrewLoop for {business}. Hey {first_name}, got a sec for a quick shift question?"*

To send a real SMS to the owner phone:

```bash
curl -X POST https://crewloop-api.ayushojha.com/api/sms/send \
     -H 'Content-Type: application/json' \
     -d '{"to":"+1XXXXXXXXXX","body":"Hey, can you cover bar Saturday 6–11pm in SoMa? $135 flat."}'
```

Inbound replies hit `/webhooks/agentphone`, get signature-verified, persisted, and auto-replied through Gemini 3 Flash.

## Seeding demo data

```bash
python backend/scripts/seed_inventory.py
python backend/scripts/seed_events.py
```

Current production fixtures:

- **37** contractors across 8 roles, each with a portrait
- **131** inventory items with imagery
- **26** events spanning backlog → drafting → shortlisting → outreach_sent → accepted → completed

## Deployment

Production runs on a single VPS (`72.62.82.57`) managed by Coolify, fronted by Traefik with auto-SSL.

| Component | Coolify UUID | Domain |
|---|---|---|
| API (FastAPI) | `lhf9laa1v9jpm6kvvm8uxwnt` | `crewloop-api.ayushojha.com` |
| Dashboard (Next.js) | — | `crewloop.ayushojha.com` |
| Postgres | shared `projects-db` | internal `projects-db:5432` |

Both services build from `Dockerfile`s in their respective folders, no docker-compose required. The Postgres schema is auto-applied on every boot via `db.ensure_schema()` — no separate migration step.

Health probe: `GET /health` → `{"status":"ok"}`.

## Roadmap

Things explicitly out of scope for the hackathon build but interesting to come back to:

- Real STT for the live voice call (today the contractor side is scripted; the architecture leaves a hook for streaming STT to replace it).
- Supermemory write/query against the owner container — the client is wired, the chat flow doesn't write yet.
- Replace the `simulate_vendor_checkout` fallback with full Browser Use checkout against a real vendor sandbox.
- Per-owner authentication (today the dashboard is open).
- Mobile-native owner app.

## License

This project is currently unlicensed — all rights reserved by the author until a formal license is chosen. If you want to use any of this code, please reach out first.

---

<div align="center">

Built for the hackathon. Real APIs. Real number. Real cloned voice.

[Spec](./CrewLoop_Spec.md) · [API docs](https://crewloop-api.ayushojha.com/docs) · [Dashboard](https://crewloop.ayushojha.com)

</div>
