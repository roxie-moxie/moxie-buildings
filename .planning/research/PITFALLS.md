# Pitfalls Research

**Domain:** Large-scale web scraping aggregator (400+ rental building sites)
**Researched:** 2026-02-17
**Confidence:** MEDIUM — Core pitfalls verified across multiple sources; platform-specific details (Yardi auth, Entrata quirks) require hands-on investigation.

---

## Critical Pitfalls

### Pitfall 1: Yardi RentCafe API Access Is Not Self-Service

**What goes wrong:**
The project spec marks Yardi/RentCafe access as "unconfirmed" — and that is the correct instinct. The RentCafe API is a formal vendor program with an annual license fee, per-interface billing, and transaction-count caps. Many developers assume the public-facing `api.rentcafe.com` endpoint (used for property websites) is freely accessible because it is technically unauthenticated for certain endpoints. This is misleading. Calling it at scale without agreement violates Yardi's RC API Terms of Use, and Yardi actively monitors for unauthorized use. Projects that build the entire scraping pipeline assuming API access is free later discover they are either blocked or legally exposed.

**Why it happens:**
The public RentCafe property search pages call `api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability` in their frontend JS with no visible authentication. Developers inspect network traffic, see the endpoint, and build scrapers against it without reading the ToU. Some properties serve data without auth tokens — because that property's owner already paid for API access and the token is embedded in the page. Calling it as a third party without a license is not the same as having authorized access.

**How to avoid:**
Treat Yardi API access as a procurement item, not a technical one. Determine in Phase 1 which of these three paths applies: (a) client buildings already grant API access to authorized vendors; (b) obtain Yardi Interfaces Program membership; (c) scrape the RentCafe website HTML directly using standard scraping (no API). Do not build the 220-site Yardi layer until the access method is confirmed. The Groupfox path (RentCafe `/floorplans` page scraping) is a different pattern — HTML scraping, not API — and can proceed independently.

**Warning signs:**
- Getting HTTP 403 or empty responses after initial success
- Responses that return data for some buildings but 401 for others (auth token varies by property)
- Legal notice from Yardi

**Phase to address:**
Phase 1 (Infrastructure / Spike) — Resolve before any Yardi scraper code is written.

---

### Pitfall 2: Silent Scrape Failures Masquerading as Success

**What goes wrong:**
A scraper that returns HTTP 200 and parses zero units is indistinguishable from a building that genuinely has zero availability — unless you explicitly check for it. This is the most dangerous failure mode at scale. Anti-bot systems frequently return honeypot HTML (a challenge page, a redirect, or a CAPTCHA wrapper) with a 200 status code. The scraper records 0 units for the building, the stale data flag is never triggered (because the scrape "succeeded"), and the admin sees a green status. Agents never see those buildings' listings again.

**Why it happens:**
Scrapers check HTTP status codes for failure detection. 200 OK reads as success. But Cloudflare Turnstile, Incapsula, and DataDome all return 200 with challenge HTML — not the actual property page. The scraper extracts no units from the CAPTCHA page and records an empty result with no error raised.

**How to avoid:**
Implement semantic success validation at every scraper tier:
- For API scrapers: require `response.units.length > 0` OR log an explicit "building has no available units" signal separate from a failed extraction.
- For HTML scrapers: assert that expected DOM elements (floor plan containers, unit rows) are present before declaring success. If key selectors are absent, treat as failure regardless of HTTP status.
- For LLM scrapers: validate that the returned JSON matches the expected schema and that at least one field is non-null.
- Add a "zero units" alert rule: if a building that had units last run now returns zero, flag for admin review.

**Warning signs:**
- A building that previously had 10+ units now consistently shows 0
- Admin dashboard shows 100% success rate but listings counts drop
- CAPTCHA-related HTML tokens (`cf_chl`, `__cf_bm`) appearing in scraper logs

**Phase to address:**
Phase 1 (Infrastructure) — Build into the scrape result contract from day one. Cannot be bolted on later.

---

### Pitfall 3: LLM Token Cost Explodes on Raw HTML

**What goes wrong:**
The $120/month estimate for LLM fallback scraping is achievable, but only with deliberate HTML preprocessing. If Crawl4AI sends raw HTML to Claude Haiku without stripping scripts, stylesheets, nav, footer, and hidden metadata, a single page can consume 15,000–30,000 tokens. At Haiku's pricing, scraping 65 buildings daily with raw HTML will cost 10–20x the estimate. The project is greenfield and the estimate was formed with preprocessing in mind — but the implementation must enforce it.

**Why it happens:**
HTML pages for modern apartment websites average 200–500KB of raw HTML. The actual unit availability content is typically 2–5KB of that. Developers copy-paste LLM scraping patterns that work in demos where the page is small, then never stress-test with full-size production pages.

**How to avoid:**
Use Crawl4AI's markdown extraction (`result.markdown`) rather than `result.html` — it strips scripts, styles, and navigation automatically. Additionally:
- Strip elements that are never needed: `<script>`, `<style>`, `<svg>`, `<iframe>`, `<head>`, nav, footer, cookie banners
- Use CSS-selector targeting to extract only the section of the page that contains unit listings (e.g., `#availability`, `.floor-plans`)
- Implement a token budget guard: if cleaned content exceeds 8,000 tokens, truncate and log a warning
- Benchmark each new site on first scrape and record typical token usage

**Warning signs:**
- LLM API spend exceeds $15/day during testing
- Haiku response times over 10 seconds (large prompt)
- Crawl4AI returning `result.html` instead of `result.markdown` in your code

**Phase to address:**
Phase 2 (LLM fallback scraper) — Enforce preprocessing before any volume testing.

---

### Pitfall 4: Data Normalization Fails Across Heterogeneous Sources

**What goes wrong:**
Each scraping tier returns data in a different shape. Yardi API returns beds as integers (`0` for studio). Entrata may return `"Studio"` or `"0BR"`. LLM extraction returns whatever the page says (`"Studio"`, `"Convertible"`, `"Alcove"`, `"Jr. 1BR"`). The canonical model requires a unified bed type enum. If normalization logic is scattered across individual scrapers rather than enforced at a central ingestion layer, the bed type field becomes inconsistent and search/filter breaks silently. An agent filtering for "Studio" misses buildings that stored `"0BR"`.

**Why it happens:**
Developers build each platform scraper independently to ship faster, each with inline normalization. Conventions diverge. The Entrata scraper normalizes `"Studio"` to `"studio"`. The LLM scraper returns `"Studio"` with a capital S. The Yardi scraper returns integer `0`. None of these break individually — but they break search queries that expect a consistent enum value.

**How to avoid:**
Design a canonical `UnitData` interface before writing any scraper. All scrapers must produce output conforming to this interface. Normalization logic (bed type mapping, rent parsing, date parsing) lives in a shared `normalize.ts` module, not in individual scrapers. Each scraper's output is validated against a Zod schema before writing to the database. Validation failures are logged and flagged, not silently discarded.

Specific normalizations to define up front:
- Bed type: `studio | convertible | 1br | 1br_den | 2br | 3br | 4br_plus`
- Rent: always stored as integer cents, never string with `$` or commas
- Availability: always stored as `YYYY-MM-DD` ISO string; handle `"Available Now"`, `"Immediate"`, `"Call for pricing"` as explicit enum values
- Floor plan name: nullable string, not required

**Warning signs:**
- Search filter for "Studio" returns different counts on different days
- Rent range filter misses buildings because rent is stored as `"$2,500/mo"` string
- Any scraper that returns raw strings without a validation step

**Phase to address:**
Phase 1 (Data model design) — Define the canonical schema and shared normalization module before any scraper is written.

---

### Pitfall 5: Schema Drift Goes Undetected Until Agents Complain

**What goes wrong:**
A building's website redesigns. The CSS selector `.floor-plan-card .price` no longer exists. The scraper either throws a caught exception (returns empty result, triggers stale flag — correct behavior) or silently returns a partial result (e.g., gets the unit name but not the price, stores `null` for rent — incorrect behavior). Over time, 15–20% of scrapers silently break from schema drift without triggering any alert.

**Why it happens:**
Property management platforms push UI updates without notice. Entrata and AppFolio both have SaaS products where the property owner's admin panel can change templates. Bozzuto runs a custom platform that has been redesigned at least twice. Scrapers hardcode selectors against a specific version of the HTML structure with no drift detection.

**How to avoid:**
- **Required field assertion**: If rent or beds is null after extraction, treat as scrape failure regardless of HTTP status.
- **Fingerprint hashing**: Store an MD5 of the key content section (not the full page) on first successful scrape. On subsequent runs, compare hashes. If the hash changes by more than a threshold (meaning page structure changed materially), log a schema-change event even if data still extracts successfully.
- **Field-level success rate monitoring**: Track per-building, per-field extraction success rates over rolling 7-day window. A field that was 100% populated dropping to 60% is a schema drift signal before total failure.

**Warning signs:**
- Rent field suddenly showing high null rate in the database
- A specific building consistently passes HTTP status check but units count is suspiciously low
- Platform (Entrata, AppFolio) announces a UI release

**Phase to address:**
Phase 2 (per-platform scrapers) — Build assertions in as each scraper ships. Phase 3 (admin dashboard) — surface field-level health metrics.

---

### Pitfall 6: No Rate Limiting = IP Blocks That Kill Entire Platform Tiers

**What goes wrong:**
Sending 220 Yardi API requests in parallel, or even in rapid sequence from the same IP, will get that IP blocked. When the IP is blocked, all 220 Yardi buildings fail simultaneously. The same applies to Entrata (35 buildings from the same origin), AppFolio, and any platform where multiple buildings share the same CDN or API gateway. A single block event disables an entire scraping tier.

**Why it happens:**
Developers test scrapers one building at a time successfully, then enable the daily scheduler with concurrency=50 and immediately saturate the rate limits of shared infrastructure. Even if each site has its own domain, shared CDN vendors (Cloudflare, Akamai, Fastly) rate-limit by originating IP across all customer sites they serve.

**How to avoid:**
- Set per-domain concurrency limits at the scraper orchestration level, not just total concurrency.
- For API-based tiers (Yardi, Entrata): use sequential requests with 2–3 second delay between buildings. 220 buildings at 2s intervals = 7 minutes total — well within a daily schedule.
- For HTML scrapers: implement exponential backoff on 429 responses, with automatic proxy rotation if available.
- Never share an IP between the API tier and HTML scraping tiers. If using a server, each tier should use a distinct outgoing IP or proxy pool.
- Implement per-platform circuit breakers: if >3 consecutive failures on the same platform, pause that tier and alert admin rather than hammering further.

**Warning signs:**
- HTTP 429 responses in scraper logs
- Sudden simultaneous failure of all buildings on one platform
- Scraper succeeds when run manually but fails on schedule (volume effect)

**Phase to address:**
Phase 1 (scheduler architecture) — Concurrency limits and circuit breakers must be built into the scheduler, not bolted on after blocking events.

---

### Pitfall 7: Google Sheets Sync Becomes a Reliability Bottleneck

**What goes wrong:**
Google Sheets API has rate limits (300 requests per 60 seconds, 60 requests per 60 seconds per user). If the daily scheduler triggers a full building list sync at the same time as admin UI actions on the sheet, or if the sync retries aggressively on transient errors, the application can exhaust its quota and fail to get the building list at all — causing the entire scrape run to abort with no buildings to process.

Additionally, if the Sheets sync fails silently (returns cached stale data or an empty array), the scraper may operate on a zero-length building list and "successfully" scrape nothing.

**Why it happens:**
Google Sheets is used as a living document, not a database. Developers treat the sync as a simple HTTP call that always works. No one thinks to validate that the returned building list has a reasonable number of rows (>300) or implements retry-with-backoff for the sync step.

**How to avoid:**
- Cache the building list locally after each successful sync. Use the cached version if the live sync fails — do not abort the scrape run due to a Sheets API error.
- Validate the sync result: if returned row count drops below a threshold (e.g., 200 buildings), log an error and use the cached version. A dramatically shorter list is a data integrity signal, not just a performance concern.
- Rate-limit the Sheets API calls from the application: sync once per day on schedule, not on every web request. Never call Sheets API from a user-facing request handler.
- Handle the case where the Sheets tab is renamed, columns are reordered, or a header row is missing — parse by column name, not column index.

**Warning signs:**
- Scrape run shows 0 buildings processed with no errors
- Google Sheets API quota exceeded errors in logs
- Column mapping breaks when someone renames a Sheets header

**Phase to address:**
Phase 1 (Google Sheets sync) — Build the caching layer and validation checks into the initial sync implementation.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inline normalization per scraper | Faster to ship each scraper | Inconsistent enums break search; debt compounds with each new scraper | Never — use shared normalization module from day one |
| Skip zero-unit validation ("success if HTTP 200") | Simpler scraper code | Silent data gaps; admin never knows buildings are missing | Never |
| Raw HTML to LLM (no preprocessing) | Less code to write | 10–20x token cost overrun; exceeds budget | Only for testing one building manually |
| Hardcoded column indices for Sheets parsing | Faster implementation | Breaks if team reorders columns | Never — parse by column name |
| Single global concurrency limit | Simple scheduler config | IP blocks kill entire platform tiers simultaneously | Only during single-site development testing |
| Store rent as string (e.g., "$2,500/mo") | No parsing work needed | Range filter queries fail; comparisons break | Never — always store as integer cents |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Yardi RentCafe API | Calling `api.rentcafe.com` without verifying access rights, assuming public endpoints are freely accessible | Confirm access method (vendor program vs. HTML scraping) in a spike before any pipeline code is written |
| Entrata API | Using the legacy API gateway (deprecated April 15, 2025) | Target only the modernized gateway; verify correct base URL and auth method in Phase 1 |
| Crawl4AI + Claude Haiku | Sending `result.html` (raw HTML) to the LLM | Use `result.markdown` and apply selector-targeted extraction to reduce token count by 80–90% |
| Google Sheets API | Calling the API on every page load or per-request | Sync once per day on schedule; cache locally; never call from request handlers |
| AppFolio | AppFolio uses tenant-specific subdomains (`{property}.appfolio.com`) — scraper must construct URL per building | Store the full URL in Sheets; do not attempt to derive AppFolio subdomain from building name |
| Bozzuto | Custom platform with history of redesigns; selector-based scrapers have short shelf life | Implement required-field assertions so redesigns trigger alerts immediately rather than silently |
| Funnel/Nestio | FLATS brand sites have unique URL patterns; "Nestio" may have been rebranded | Verify current brand/platform name before building scraper; do not assume marketing names are stable |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No per-platform concurrency limits | All buildings on one platform fail simultaneously when IP is blocked | Set per-platform max concurrency (2–5 for HTML scrapers, sequential for API tiers) | First full daily run with all 400 buildings |
| LLM calls without preprocessing | Token costs 10–20x estimates; rate limits from Anthropic API | Strip scripts/styles/nav before every LLM call; enforce token budget guard | First production run with 65+ buildings |
| No circuit breaker on platform failures | Scheduler retries failing platform 220 times, consuming all retry budget and extending run time | Circuit breaker: pause tier after 3 consecutive failures, alert admin | When one platform has an outage |
| Synchronous sequential scraping of all 400 buildings | Daily scrape takes 4–6 hours, cutting into the next day's window | Use per-platform parallelism (platforms run in parallel; buildings within a platform run sequentially or with low concurrency) | When building count grows or a platform is slow to respond |
| LLM extraction without output schema validation | Hallucinated fields silently corrupt database | Use Zod schema validation on every LLM response; treat validation failure as scrape failure | When LLM returns partial or malformed JSON |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Yardi/Entrata API credentials in code or unencrypted env files | Credential leak exposes vendor API access; violates API ToU; potential contract termination | Use environment variables with secrets management (Railway/Fly secrets, not committed `.env`) |
| Exposing the admin scrape dashboard to unauthenticated requests | Admin can see building list, scrape credentials, and health data | Require same auth as agent login for admin routes; add role-based access (admin vs. agent) |
| Logging full HTTP response bodies | Logs may capture sensitive property data (pricing before public release) or PII | Log only status codes, timestamps, and field-level success metrics — not full response content |
| Using scraped data in a public-facing API | Legal exposure from aggregating and resurfacing proprietary rental data | Keep the system internal-only (login required); do not expose a public API or allow public indexing |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing "last scraped" timestamp without staleness context | Agent doesn't know if "last scraped 3 days ago" is normal or a failure | Show staleness state: "Current (scraped today)", "Stale (1 day old)", "Alert (3+ days — failed)" with visual indicators |
| Exposing raw scrape errors in the agent interface | Agents see confusing technical messages | Errors appear only in admin dashboard; agents see "data temporarily unavailable" |
| No indication that zero-unit results may be a scrape failure vs. genuine zero availability | Agent believes a building has no units when the scraper silently failed | Flag zero-unit buildings that previously had units; show "data may be incomplete" warning |
| Export format that requires post-processing | Agents spend time reformatting before sharing with clients | Export should produce a clean, client-ready output (clear column names, human-readable bed types, formatted rent) |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Scraper "success" state:** Verify that HTTP 200 + zero units triggers a failure flag, not a success record — check your scrape result contract handles both "no units returned" and "extraction failed" as distinct states.
- [ ] **LLM fallback cost:** Verify token preprocessing is active before any volume run — benchmark token counts on 3 representative sites before running all 65.
- [ ] **Yardi API access:** Verify the auth method works for all 220 buildings, not just the 1–2 tested in development — some properties may require different credentials or have opted out of API access.
- [ ] **Normalization coverage:** Verify that bed type, rent, and availability date are normalized for all 9 scraping tiers, not just the ones built first — run a post-scrape audit query counting distinct values in each field.
- [ ] **Sheets sync cache:** Verify that the scraper scheduler runs successfully even when Google Sheets API is unavailable — test by temporarily revoking the API key.
- [ ] **Schema drift alerts:** Verify that a required-field null (e.g., rent = null) triggers an admin flag — test by deliberately breaking a selector in a dev environment.
- [ ] **Rate limiting enforcement:** Verify that the scheduler respects per-platform concurrency limits under full load (all 400 buildings) — test with a full dry run before enabling production schedule.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Yardi API access blocked/revoked | HIGH | Switch Yardi tier to HTML scraping of RentCafe property pages (feasible but requires new selectors for 220 buildings); investigate fallback to LLM for a subset |
| Mass schema drift (platform redesign) | MEDIUM | Identify new selectors using browser devtools on 2–3 representative buildings; update shared selector config; validate against all buildings in that tier before re-enabling |
| LLM cost overrun (over budget) | MEDIUM | Switch to smaller extraction prompt targeting only the units section; reduce buildings using LLM fallback by moving any findable-structured-API buildings out of the fallback tier |
| Google Sheets API access failure | LOW | Use locally cached building list; restore Sheets access via Google Cloud Console; re-sync once access restored |
| Silent data corruption discovered | HIGH | Roll back database to last verified-clean snapshot; rerun scraper for affected buildings with verbose logging; implement missing validation rules before re-enabling scheduler |
| IP blocked across multiple platforms | MEDIUM | Switch outgoing IP (new server, proxy); implement request delays and circuit breakers before re-enabling; stagger platform schedules to reduce burst traffic |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Yardi API access unconfirmed | Phase 1 (Infrastructure spike) | API access confirmed and tested against 5+ buildings before pipeline is built |
| Silent scrape failures | Phase 1 (Data model + scrape result contract) | Integration test: a page returning CAPTCHA HTML is classified as failure, not zero-unit success |
| LLM token cost overrun | Phase 2 (LLM fallback scraper) | Benchmark token counts on 5 representative sites; monthly cost projection within 20% of $120 target |
| Data normalization inconsistency | Phase 1 (Canonical data model) | All 9 tiers produce identical shape output; Zod validation passes on sample data from each platform |
| Schema drift undetected | Phase 2 (per-platform scrapers) + Phase 3 (admin dashboard) | Breaking a selector in dev triggers admin flag within one scrape run |
| IP blocking from rate overruns | Phase 1 (Scheduler architecture) | Full 400-building dry run completes without 429 errors; per-platform circuit breakers tested |
| Google Sheets sync failure | Phase 1 (Sheets sync implementation) | Scraper runs successfully with Sheets API unavailable, using cached list |
| Zero-unit buildings silently accepted | Phase 1 (Scrape result contract) | Automated test: scraping a building known to have units produces a failure flag if zero units returned |

---

## Sources

- [Yardi RC API Terms of Use](https://resources.yardi.com/legal/rc-api-tou/) — MEDIUM confidence (official ToU, confirms access is licensed)
- [Yardi RentCafe API Reference (UnitMap)](https://developers.unitmap.com/docs/references-api-yardi-rentcafe) — MEDIUM confidence (third-party developer docs showing API shape)
- [Entrata Enhanced API Program announcement (PR Newswire, 2024)](https://www.prnewswire.com/news-releases/entrata-introduces-its-enhanced-api-program-and-doubles-down-on-commitment-to-building-the-best-partner-ecosystem-in-the-industry-302107516.html) — MEDIUM confidence (confirms legacy API deprecated April 2025)
- [WebScraping.AI: LLM Cost Optimization](https://webscraping.ai/faq/scraping-with-llms/how-can-i-optimize-llm-costs-when-scraping-large-amounts-of-data) — MEDIUM confidence (practical cost data, preprocessing strategies)
- [Webscraping.pro: Scalability Cliff (Open Source Tools at Enterprise Volume)](https://webscraping.pro/%F0%9F%93%88-the-scalability-cliff-why-open-source-web-scraping-tools-fail-at-enterprise-volume/) — MEDIUM confidence (verified by cross-referencing with Grepsr and ScrapingBee findings)
- [ScrapingBee: Web Scraping without getting blocked (2026)](https://www.scrapingbee.com/blog/web-scraping-without-getting-blocked/) — MEDIUM confidence (anti-bot patterns confirmed across multiple sources)
- [Grepsr: Orchestrating Data Workflows / Scheduling](https://www.grepsr.com/blog/orchestrating-data-workflows-scheduling-and-monitoring-web-scraping-jobs/) — MEDIUM confidence (production scheduler patterns)
- [ScrapingAnt: LLM-Powered Data Normalization](https://scrapingant.com/blog/llm-powered-data-normalization-cleaning-scraped-data) — MEDIUM confidence (normalization problem patterns)
- [ZenRows: Bypass Rate Limit](https://www.zenrows.com/blog/web-scraping-rate-limit) — MEDIUM confidence (rate limiting mechanics)
- [Firecrawl: 10 Common Web-Scraping Mistakes](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes) — MEDIUM confidence (cross-checked against other sources)
- [Google Sheets API rate limits](https://developers.google.com/sheets/api/limits) — HIGH confidence when verified against official Google docs

---
*Pitfalls research for: Moxie Building Aggregator (MBA) — large-scale rental scraping aggregator*
*Researched: 2026-02-17*
