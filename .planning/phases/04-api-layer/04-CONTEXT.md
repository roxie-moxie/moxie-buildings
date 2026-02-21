# Phase 4: API Layer - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticated FastAPI endpoints exposing unit search with all filter parameters, admin account management (create/disable agents), and admin scrape controls (trigger re-scrape, view buildings). The API is the backend contract that Phase 5's frontend will consume. No frontend work in this phase.

</domain>

<decisions>
## Implementation Decisions

### Auth & token behavior
- JWT access tokens with 8-hour lifetime (one login per work shift)
- No refresh tokens — agents re-login when token expires
- No lockout on failed login — return 401, no attempt tracking
- Check `is_active` on every authenticated request — disabling an account immediately revokes access (existing JWTs rejected)

### Admin bootstrap & role model
- Single `users` table with a `role` column (admin / agent)
- First admin created via CLI seed command (e.g., `uv run create-admin --email ... --password ...`)
- Single admin expected (just Alex) — no multi-admin promotion flow needed
- Admin is the only role that can access /admin/* endpoints

### Search endpoint design
- GET /units with query params for all filters (beds, rent_min, rent_max, available_before, neighborhood)
- No pagination — return all matching units in a single response (dataset is ~2-5K units total)
- Each unit in the response includes `last_scraped` timestamp from its building — frontend uses this for green/yellow/red freshness indicator
- Flat error messages: `{"detail": "rent_max must be positive"}` — no per-field breakdown

### Re-scrape workflow
- Async with polling: POST /admin/rescrape/{building_id} returns a job ID
- Poll GET /admin/rescrape/{job_id} for status
- Completion response includes status + unit count + duration (not full scrape log)
- One re-scrape at a time per building — 409 Conflict if already running
- Admin-only endpoint — agents cannot trigger re-scrapes

### Deployment & infrastructure
- Hosting decision deferred — build host-agnostic API
- No rate limiting — 7 agents, internal tool, not worth the complexity now
- CORS origins configured via environment variable (CORS_ORIGINS), defaults to localhost

### Claude's Discretion
- Password complexity rules (reasonable defaults for an internal tool)
- Exact API route naming conventions
- Response envelope structure (bare list vs wrapped object)
- JWT signing algorithm and secret management approach
- Re-scrape job storage mechanism (in-memory vs database)

</decisions>

<specifics>
## Specific Ideas

- Search response must include `last_scraped` per building from day one — the Phase 5 freshness indicator (AGENT-07) depends on this field being in the API contract
- CORS_ORIGINS env var pattern — production sets the real frontend origin, dev defaults to localhost
- CLI seed command follows existing `uv run` pattern (consistent with validate-building, scrape, etc.)

</specifics>

<deferred>
## Deferred Ideas

- **Stale data handling change** — Currently scrapers delete unit data on failure. User wants to change this: keep last successful scrape data on failure, mark building as stale via timestamp, only replace data on success. Reasoning: stale data with a warning is better than no data. Should be addressed before or during Phase 5 when the freshness indicator becomes visible to agents.
- **Rate limiting** — Noted as cheap insurance (60 req/min per user) but deferred. Revisit if the API becomes externally accessible or team grows.

</deferred>

---

*Phase: 04-api-layer*
*Context gathered: 2026-02-21*
