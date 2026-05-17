# Frontend (Next.js)

The CrewLoop UI lives at `/frontend` as a Next.js 16 + React 19 + Tailwind CSS v4 application. It deploys as a separate Coolify service at `crewloop.ayushojha.com`; the FastAPI backend stays at `crewloop-api.ayushojha.com`.

## Architecture decisions

| Decision | Choice | Why |
|---|---|---|
| Framework | Next.js 16.2 (App Router, Turbopack) | Latest stable as of 2026-05. App Router + Server Components match the static-by-default landing page; client components handle the interactive dashboard/dispatch/import pages. |
| Styling | Tailwind CSS v4 with `@theme` design tokens | v4's CSS-based theme block lets us declare the warm-ink palette and three fonts once, then use utility classes everywhere. No PostCSS config beyond Next's defaults. |
| Fonts | `next/font/google` for Instrument Serif, Geist, Geist Mono | Self-hosted, zero-CLS, mapped to CSS variables (`--font-instrument-serif`, etc.) that the Tailwind theme references. |
| API client | Tiny typed wrapper in `src/lib/api.ts` over `fetch` | No SDK, no extra deps. Base URL from `NEXT_PUBLIC_API_BASE_URL`. Dashboard polls every 5 s with `cache: "no-store"`. |
| Deploy | Coolify Dockerfile (multi-stage, Next standalone output) | Same VPS as the API. `output: "standalone"` in `next.config.ts` emits a minimal Node server bundle that copies cleanly into `node:22-alpine`. Build runs as non-root. |

## Page inventory

| Route | File | Mode | Source it ported |
|---|---|---|---|
| `/` | `src/app/page.tsx` | Static / Server Component | `index.html` |
| `/dashboard` | `src/app/dashboard/page.tsx` + `DashboardClient.tsx` | Client (5 s polling) | `backend/app/static/dashboard.html` |
| `/browser-import` | `src/app/browser-import/page.tsx` + `BrowserImportClient.tsx` | Client | `backend/app/static/browser-import.html` |
| `/dispatch/[jobId]` | `src/app/dispatch/[jobId]/page.tsx` + `DispatchClient.tsx` | Dynamic + Client | `backend/app/static/dispatch-room.html` |
| `/bay-events/staffing` | `src/app/bay-events/staffing/page.tsx` | Static / Server Component | `backend/app/static/bay-events-staffing.html` |

Shared building blocks live in `src/components/Brand.tsx` (logo + arrow icon) and `src/components/Nav.tsx` (sticky landing nav).

## API client

`src/lib/api.ts` exports a `request` helper and an `api` object with typed methods for every endpoint the UI touches:

- `api.listConversations()`, `api.getConversation(phone)`, `api.listCalls()`
- `api.sendSms({ to, body })`, `api.placeCall({ to, ... })`
- `api.browserImport({ source_url, force_local })`, `api.getJob(jobId)`, `api.getDispatch(jobId)`
- `api.dispatchAction(jobId, "outreach" | "accept" | "check-in" | "approve-release", body)`

Types are in `src/lib/types.ts` (conversations/messages/calls/jobs/browser sources). The `DispatchPayload` interface mirrors the parallel-session backend's `/api/dispatch/{jobId}` response shape.

## Local development

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

By default the client points at `https://crewloop-api.ayushojha.com`. Override with:

```bash
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
```

(Note the local backend lives at `:8000`. The Next dev server is `:3000`; the FastAPI CORS allow-list already includes both `localhost:3000` and `127.0.0.1:3000`.)

## CORS

`backend/app/main.py` now mounts `CORSMiddleware` with an explicit allow-list:

```python
allow_origins=[
    "https://crewloop.ayushojha.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

If you ever move the frontend to a different domain (Vercel preview, etc.), add it here and redeploy the API.

## Deploying to Coolify

1. Create a new Coolify application of type Dockerfile.
2. Source: this repo. Base directory: `/frontend`.
3. Domain: `crewloop.ayushojha.com`. Traefik handles TLS.
4. **Build argument** (not just runtime env): `NEXT_PUBLIC_API_BASE_URL=https://crewloop-api.ayushojha.com`. The value must be set at build time because Next inlines `NEXT_PUBLIC_*` vars into the client bundle.
5. Internal port: `3000` (the container's `EXPOSE`).
6. Healthcheck (optional): `GET /` returns 200 once the server is up. Don't enable Coolify's docker-level healthcheck — `node:22-alpine` doesn't ship with `curl`/`wget`; rely on external HTTPS checks instead.

Add the DNS A record `crewloop.ayushojha.com → 72.62.82.57` at Hostinger before the first deploy so Let's Encrypt can issue a cert immediately.

## What's NOT in this migration

- The static HTML pages still live in `backend/app/static/` and FastAPI still serves them at `/dashboard`, `/browser-import`, `/bay-events/staffing`. Once `crewloop.ayushojha.com` is verified working, those routes (and the static files) can be removed from the backend.
- No client-side data fetching libraries (TanStack Query, SWR). The dashboard's polling and the dispatch room's per-action refetches use plain `useEffect` + `setInterval` because the interaction patterns are tiny.
- No design system / component library yet. Components are inline in their pages; pull them out into `src/components/` when patterns repeat.
