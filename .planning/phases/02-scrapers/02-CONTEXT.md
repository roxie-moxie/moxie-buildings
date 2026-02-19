# Phase 2: Scrapers - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

All ~400 buildings covered by working scraper modules across three tiers: Tier 1 REST APIs (RentCafe/Yardi, PPM), Tier 2 platform HTML scrapers (Funnel/Nestio, RealPage/G5, Bozzuto, Groupfox, AppFolio), and Tier 3 LLM fallback (Crawl4AI + Claude Haiku for custom sites and Entrata buildings). Each module produces normalized UnitInput records that flow into the existing database layer from Phase 1.

Scheduling (Phase 3), API exposure (Phase 4), and frontend (Phase 5) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Platform Assignment

- **Hybrid strategy:** URL pattern detection fills blanks; Google Sheets Platform column value always wins on conflict
- **Sheets as source of truth:** If a Platform column exists in the sheet, sheets-sync writes the value directly to the `platform` field on the building record — same as any other sheet column
- **Detection fills blanks only:** Auto-detection only runs when `platform` is null/empty after sheets-sync. Sheets-sourced values are never overwritten by detection
- **Integrated into sheets-sync:** Platform detection is not a one-time migration — it runs as part of every sheets-sync pass, classifying any newly synced building that lacks a platform value
- **Platform strings:** Claude decides exact values (e.g., `rentcafe`, `ppm`, `funnel`, `realpage`, `bozzuto`, `groupfox`, `appfolio`, `llm`) — consistent with codebase conventions
- **Entrata:** Skip Entrata API scraper entirely. Route Entrata buildings to `llm` platform. Revisit only if LLM fallback struggles specifically with Entrata sites.

### Tier Execution Order

- **Sequential by tier:** Tier 1 first (RentCafe/Yardi + PPM), then Tier 2 platforms, then Tier 3 LLM fallback
- Each tier's implementation informs the next; interface is validated with simpler cases before layering complexity

### RentCafe / Yardi Scraper

- **Build now with stubbed API call:** Write the full Yardi/RentCafe scraper module now; stub the actual API request with a placeholder. Swap in real credentials once confirmed.
- **Public API first:** RentCafe exposes a public JSON API at predictable URLs that requires no vendor enrollment. Pursue this path exclusively — drop vendor enrollment from the plan entirely. If the public API fully covers unit data needs, vendor access is never required.

### Failure & Stale Flagging

- **Zero units = trust and delete:** When a scraper succeeds and returns zero units, delete the building's existing unit records. Showing unavailable units to agents is worse than showing nothing.
- **Consecutive zero safeguard:** Track a `consecutive_zero_count` field on the Building model. Increment on each zero-unit return; reset to 0 on any non-zero return.
- **Needs-attention threshold:** After **5 consecutive zero-unit scrapes**, flag the building for review (separate from the stale flag). This catches silent scraper failures without requiring manual monitoring.
- **`consecutive_zero_count` requires a schema migration** — new field on the buildings table.

### Claude's Discretion

- Scraper invocation style (async vs sync functions)
- Scraper input shape (Building ORM vs minimal dataclass)
- Scraper return shape (list of UnitInput vs side effects)
- Whether to use an abstract base class (ABC) or documented convention
- Exact platform string values
- HTTP error handling: immediate stale vs retry-then-stale
- Whether scrape_runs logging belongs in Phase 2 scrapers or Phase 3 scheduler

</decisions>

<specifics>
## Specific Ideas

- RentCafe public API: predictable JSON endpoints on rentcafe.com, no enrollment. Investigate URL patterns used by known RentCafe buildings in the DB.
- "Scraper Quality" column already exists in the Google Sheet — this may be related to or replaceable by the Platform column.
- Entrata: don't build a scraper. Route to `llm` platform. If Entrata sites later prove problematic for LLM, add a decimal phase (e.g., 2.1) to address them.
- consecutive_zero_count design: reset on non-zero return, not on scraper error (errors and zero-unit successes are tracked separately).

</specifics>

<deferred>
## Deferred Ideas

- Entrata API scraper — deferred indefinitely. LLM fallback handles those ~30-40 buildings. Revisit as Phase 2.x if LLM struggles.
- Vendor enrollment for Yardi — dropped entirely in favor of public RentCafe API.
- Retry logic (N retries before marking stale) — deferred to Phase 3 scheduler, which can wrap scrapers with retry behavior.

</deferred>

---

*Phase: 02-scrapers*
*Context gathered: 2026-02-18*
