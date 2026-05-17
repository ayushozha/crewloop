# AgentPhone Integration

CrewLoop's outreach loop (SMS first, call when urgent) runs on AgentPhone. This doc covers the backend that wraps AgentPhone's API, how to provision the agent + number, and how to deploy the webhook receiver to Coolify.

## Overview

A FastAPI service exposes three things:

- `POST /api/sms/send` — outbound SMS to a contractor
- `POST /api/calls/place` — outbound call (urgent escalation)
- `POST /webhooks/agentphone` — receives `agent.message` (SMS replies + voice turns) and `agent.call_ended` events

The agent runs in **hosted voice mode** — AgentPhone handles the LLM and TTS during calls using the `systemPrompt` and `beginMessage` baked in at agent creation. The webhook receiver only fires for SMS replies and call-ended summaries; we don't drive voice turns ourselves.

## Architecture decisions

| Decision | Choice | Why |
|---|---|---|
| Stack | Python + FastAPI | Hackathon-friendly, matches AgentPhone's official Python SDK ecosystem, plays well with Gemini if we add planner agents later. |
| Voice mode | `hosted` | AgentPhone handles LLM + TTS in-call. One less moving piece for the demo; webhook receiver only handles SMS + call summaries. |
| Number country / area code | US, 415 | Matches the demo scenario (SoMa, San Francisco). |
| Webhook signing | HMAC-SHA256 over raw body; secret from AgentPhone's webhook creation response | Set on `AGENTPHONE_WEBHOOK_SECRET`. Signature verification accepts hex or base64 because AgentPhone's docs don't specify which. |
| Env loading | `.env` + `.env.local` at repo root | Single source of truth across web + backend; backend reads via pydantic-settings. |
| Deploy target | Coolify on VPS (72.62.82.57), subdomain `crewloop-api.ayushojha.com` | Production-ready webhook URL; Traefik handles TLS automatically. |

## File inventory

```
backend/
├── requirements.txt              fastapi + uvicorn + httpx
├── Dockerfile                    Coolify build target (python:3.12-slim)
├── .dockerignore
├── .env.example                  per-service env var documentation
└── app/
    ├── main.py                   FastAPI app, router wiring, /health
    ├── config.py                 Settings via pydantic-settings (reads ../.env*)
    ├── agentphone.py             Async client: send_message, place_call
    ├── signature.py              Webhook HMAC verification
    └── routes/
        ├── sms.py                POST /api/sms/send
        ├── calls.py              POST /api/calls/place
        └── webhooks.py           POST /webhooks/agentphone
backend/scripts/provision_agentphone.py   Run once after deploy
docs/agentphone-integration.md             This file
```

## API endpoints

### `POST /api/sms/send`

```json
{ "to": "+14155551234", "body": "Hi Maya — bartender shift tonight 6–10pm in SoMa, $120. Can you cover?" }
```

Returns AgentPhone's `Send Message` response: `{ id, status, channel, from_number, to_number, media_urls }`.

### `POST /api/calls/place`

```json
{
  "to": "+14155551234",
  "initial_greeting": "Hey Maya, CrewLoop here — urgent shift, do you have a sec?",
  "system_prompt": "Optional per-call override of the agent's behavior."
}
```

Returns AgentPhone's `Create Call` response (call ID + status).

### `POST /webhooks/agentphone`

Receives:

- `agent.message` channel `sms` — inbound contractor reply. Logged today; will hand off to the matching/scheduling agents next.
- `agent.message` channel `voice` — voice-turn webhook for `webhook` mode agents. Our agent is hosted mode, so this is a fallback no-op that returns a filler line.
- `agent.call_ended` — post-call summary with transcript + sentiment. Logged today; will feed reliability scoring next.

Signature: `X-Webhook-Signature` HMAC-SHA256 over the raw request body; secret from the webhook-create response.

## Setup

### 1. Local install

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The backend reads env from the repo root's `.env` and `.env.local`. `AGENTPHONE_API_KEY` is already set there; the agent/number/secret env vars are filled in by step 3.

### 2. Deploy to Coolify

The webhook URL (`https://crewloop-api.ayushojha.com/webhooks/agentphone`) must be publicly reachable *before* provisioning, because AgentPhone validates the URL when the webhook is created.

In Coolify (`https://coolify.ayushojha.com`, VPS 72.62.82.57):

1. New Resource → Application → Dockerfile.
2. Source: this repo. Base directory: `/backend`.
3. Domain: `crewloop-api.ayushojha.com`. Traefik handles TLS via Let's Encrypt.
4. Environment variables (paste in): `AGENTPHONE_API_KEY`, `AGENTPHONE_BASE_URL`, `AGENTPHONE_WEBHOOK_URL=https://crewloop-api.ayushojha.com/webhooks/agentphone`. Leave the agent/number/secret blank for now.
5. Deploy. Smoke test: `curl https://crewloop-api.ayushojha.com/health` → `{"status":"ok"}`.

### 3. Provision AgentPhone resources

Once `/health` is green:

```bash
cd backend
.venv/bin/python scripts/provision_agentphone.py
```

This will:

1. `POST /v1/agents` — creates the CrewLoop dispatcher agent in hosted voice mode.
2. `POST /v1/numbers` — rents a US +1 415 number and attaches it to the agent. **This is a recurring cost on the AgentPhone account.**
3. `POST /v1/webhooks` — registers `https://crewloop-api.ayushojha.com/webhooks/agentphone` and returns a signing secret.

The script prints the four values to add to `.env.local`:

```
AGENTPHONE_AGENT_ID=...
AGENTPHONE_NUMBER_ID=...
AGENTPHONE_FROM_NUMBER=+1415...
AGENTPHONE_WEBHOOK_SECRET=...
```

Paste them into `.env.local` and the same four into Coolify's environment, then redeploy.

### 4. End-to-end smoke test

```bash
# Outbound SMS
curl -X POST https://crewloop-api.ayushojha.com/api/sms/send \
  -H 'Content-Type: application/json' \
  -d '{"to":"+1YOURNUMBER","body":"CrewLoop test from production."}'

# Outbound call (urgent escalation)
curl -X POST https://crewloop-api.ayushojha.com/api/calls/place \
  -H 'Content-Type: application/json' \
  -d '{"to":"+1YOURNUMBER","initial_greeting":"Hey, CrewLoop here — quick test."}'
```

Reply to the SMS from your phone and watch the Coolify logs for the `inbound SMS from …` log line.

## What's NOT included (yet)

- **Contractor matching / ranking**: the SMS endpoint is dumb-pipe today. The matching agent (spec §6.2) will sit in front of it and pick the recipient.
- **Job intake parsing**: an incoming SMS from the owner doesn't yet create a Job object. The webhook handler only logs.
- **Persistence**: no database. Everything is in-memory / logs. The next module adds Postgres (per the global CLAUDE.md VPS config).
- **10DLC registration**: AgentPhone notes outbound SMS to US numbers requires 10DLC registration. The provisioning script does not handle this; outbound SMS may be rate-limited until registered with AgentPhone.
- **Signature format**: AgentPhone's docs don't specify hex vs base64. The verifier accepts both; if production webhooks fail signature verification, tighten this.

## Cost notes

- **AgentPhone phone number rental**: recurring monthly fee per provisioned number (~$1–2/mo for US local).
- **SMS / call usage**: per-message and per-minute pricing per AgentPhone's billing.
- **Coolify deploy**: runs on the existing VPS, no additional cost.
