# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Validation-first scraper pipeline — one building at a time, validate with user

## Current Position

Phase: 3 of 5 (Scheduler) — COMPLETE (2/2 plans done)
Status: Phase 03 complete. Daily batch automation operational: scrape-all --schedule fires run_batch at 2 AM Central, Scrape Status tab pushed to Google Sheet, rotating log at logs/scrape_batch.log, scrape_runs pruned at 30 days.
Last activity: 2026-02-20 - Built APScheduler cron, Sheets status push, rotating log, scrape_runs pruning (03-02).

Progress: [██████████] 78%

---

## What's Done (this session)

### SightMap scraper validated + mass reclassification
- SightMap JSON API scraper confirmed across multiple management companies (Greystar, AMLI, LMC, FLATS, Magellan)
- Discovered Funnel/SightMap hybrid pattern: 13 "funnel" buildings actually serve data via SightMap embeds
- Scanned all 361 non-SightMap buildings for SightMap embeds — found 31 more (23 RentCafe, 3 RealPage, 4 Funnel, 1 MRI)
- Scanned 66 `needs_classification` buildings — found 4 more SightMap embeds
- **SightMap now covers 58 buildings** (up from 54; +4 via api.js embed pattern: Arkadia, Hugo, MILA, Wolf Point East)
- Fixed SightMap placeholder filter: skip units with `area <= 1` (catches "TEMP" floor plans)
- Fixed SightMap embed regex to exclude `api.js` (was matching loader script instead of embed ID)
- Added `/sightmap` to SightMap discovery subpage list (Wolf Point East pattern)

### SecureCafe scraper built (NEW — biggest unlock)
- `src/moxie/scrapers/tier2/securecafe.py` — Crawl4AI two-step approach
- Step 1: Render marketing site to discover `securecafe.com/onlineleasing/` URL
- Step 2: Fetch `availableunits.aspx` and parse `tr.AvailUnitRow` elements
- Dates extracted from `data-label="Date Available"` cell OR `ApplyNowClick()` onclick fallback
- Handles `12/31/9999` as "Available Now", price ranges (normalizer takes lower)
- **Replaces broken RentCafe API credential approach entirely**
- Registered as `rentcafe` platform in both `scrape.py` and `push_availability.py`

### LLM scraper fixed (Entrata/MRI)
- Now tries explicit subpages (/floorplans, /floor-plans, /floorplans/all, /apartments) BEFORE link scoring
- Uses Crawl4AI for probing (not httpx — httpx gets 403 on these sites)
- Added `delay_before_return_html=3.0` to LLM extraction pass (Entrata React widgets need time to load)
- Added `"floor plan"` (space) to _AVAILABILITY_KEYWORDS (was only matching "floor-plan" with hyphen)
- Updated extraction instruction to accept floor plan names as unit identifiers when individual unit numbers not shown
- Exclude /Apartments/module/ paths from link scoring (Entrata portal modules)
- Confirmed: 7 of 10 Entrata buildings now find /floorplans URL. MRI mostly Cloudflare-blocked.

### AppFolio Sedgwick Properties scraper (NEW)
- `src/moxie/scrapers/tier2/appfolio.py` — rewrote with direct listings API approach
- Fetches `sedgwickproperties.appfolio.com/listings` directly (HTML is server-side rendered)
- Parses `.js-listing-item` cards: unit number from img[alt] address, price from .detail-box__value
- `building.rentcafe_api_token` = AppFolio subdomain (e.g. `sedgwickproperties`)
- `building.rentcafe_property_id` = address filter keyword (e.g. `1325 N Wells`)
- 1325 N Wells: 3 units, Arco Old Town: 4 units — both validated

### Buildings validated this session
| Building | Platform | Units | Result |
|----------|----------|-------|--------|
| Next | SightMap | 21 | Pass (placeholder #2004 filtered) |
| The Ardus | SightMap (was funnel) | 4 | Pass (reclassified) |
| Triangle Square | SightMap (was funnel) | 14 | Pass |
| Trio | SightMap | 7 | Pass |
| Melrose Shores | Groupfox | 0 | Pass (confirmed no availability) |
| AMLI West Loop | SightMap | 27 | Pass |
| 1225 Old Town | SightMap (was needs_class) | 10 | Pass |
| Hubbard Place | SightMap (was rentcafe) | 24 | Pass |
| Lake & Wells | SightMap (was realpage) | 31 | Pass |
| 8 East Huron | SecureCafe (rentcafe) | 4 | Pass |
| Fisher Building | SecureCafe (rentcafe) | 5 | Pass |
| Reside on Barry | SecureCafe (rentcafe) | 5 | Pass (date fix applied) |
| Atwater Apartments | SecureCafe (was bozzuto) | 34 | Pass (subpage discovery fix) |
| Wolf Point East | SightMap (was mri) | 46 | Pass (api.js embed fix + /sightmap subpage) |
| Arkadia | SightMap (was rentcafe) | 12 | Pass (api.js embed fix) |
| Arco Old Town | AppFolio (was needs_class) | 4 | Pass (new Sedgwick scraper) |
| 1325 N Wells | AppFolio (was needs_class) | 3 | Pass (new Sedgwick scraper) |

### Platform distribution (current)
| Platform | Buildings | Scraper Status |
|----------|-----------|---------------|
| RentCafe (SecureCafe) | 217 | **Working** (-3 reclassified to SightMap) |
| SightMap | 58 | **Working** (+4: Wolf Point East, Arkadia, Hugo, MILA) |
| needs_classification | 57 | Unscraped (-2 reclassified to AppFolio) |
| AppFolio | 20 | Partial — 2 Sedgwick buildings working; 18 others (APM Sites) broken |
| PPM | 19 | **Working** |
| Groupfox | 13 | **Working** (validated) |
| Entrata | 10 | LLM fallback — /floorplans probing works; units returned if API key set |
| RealPage | 5 | Broken — rpfp-* JS widget, AJAX loads from LeaseStar API |
| MRI | 4 | Mostly blocked — Arrive* buildings Cloudflare-protected on prospectportal.com |
| Funnel | 2 | Working (mostly 0 units) |
| Bozzuto | 1 | SSL issues on remaining building |
| dead | 1 | Skip |

**Working scraper coverage: 310 of 407 buildings (76%)**

---

## What's In Progress / Not Done

### Remaining validation
- 57 `needs_classification` buildings — most return no known platform patterns (custom sites, small properties)
- AppFolio (18) — APM Sites type (Astoria Tower, etc.) needs different URL pattern
- RealPage (5) — rpfp-* widget loads via AJAX from LeaseStar API, not scrapeable via static HTML
- Entrata (10) — LLM fallback now points at /floorplans; units expected when ANTHROPIC_API_KEY valid
- MRI (4) — Arrive buildings Cloudflare-blocked; Wolf Point East moved to SightMap
- The Marlowe — reclassified to rentcafe but SecureCafe URL only in API response JSON (not discoverable via scraper)
- Hugo, MILA — reclassified to SightMap but not yet validated (scrape spot-checked, unit counts not confirmed)

### Known issues
- Some SecureCafe templates have "Date Available" column, others hide dates in ApplyNowClick() — both handled
- Funnel scraper only works for 1 building (Imprint) — remaining 2 return 403 or 0 units
- 4 buildings matched `sightmap.com/embed/api` (Arkadia, Hugo, MILA, Sky55) — 3 now working; Sky55 (Brookfield) deferred
- Related Rentals buildings (3) — proprietary platform, no known scraping approach
- BJB Properties (3) — blocks all bots, no accessible availability data
- Entrata LLM: floor plan pages show floor plan types, not individual units — LLM instruction updated to accept floor plan names as unit identifiers

---

## Next Steps (in order)

1. **Validate Hugo and MILA** — reclassified to SightMap but not push-validated yet
2. **Test Entrata LLM with valid API key** — /floorplans probing confirmed working; need to confirm unit extraction
3. **Batch scan remaining needs_classification (57)** — run Crawl4AI check for securecafe.com/onlineleasing/ on all 57. Atwater pattern may apply to more.
4. **APM Sites AppFolio (18)** — investigate Astoria Tower and others for AppFolio-hosted listing pages
5. **Run bed type audit** — `SELECT COUNT(*) FROM units WHERE non_canonical = 1`
6. **Phase 3: Scheduler** — daily batch runner, per-platform concurrency limits

---

## Key Decisions (this session)

- [2026-02-20]: APScheduler imports deferred to --schedule branch — no import cost on immediate scrape-all runs
- [2026-02-20]: APScheduler pending jobs use job.trigger.get_next_fire_time() not job.next_run_time — latter is None before scheduler.start()
- [2026-02-20]: Sheets push failure does not crash batch — monitoring is not core function; wrapped in try/except
- [2026-02-20]: Single ws.update() call for Scrape Status tab — one API request for 349+ building rows
- [2026-02-20]: PLATFORM_SCRAPERS centralized in registry.py — eliminates duplicate dicts in scrape.py and push_availability.py
- [2026-02-20]: SQLite WAL mode + 30s busy_timeout enabled on engine connect for safe concurrent batch writes
- [2026-02-20]: Clear-on-failure semantics in batch runner — units deleted on scraper error (stale data is not real data)
- [2026-02-20]: Per-platform semaphores: browser platforms (Crawl4AI/Playwright) concurrency=1, HTTP platforms (sightmap, appfolio) concurrency=2
- [2026-02-20]: LLM scraper now uses Crawl4AI for subpage probing (not httpx — httpx gets 403 on Entrata/MRI sites)
- [2026-02-20]: LLM extraction instruction updated to accept floor plan names as unit identifiers — Entrata floor plan pages don't expose individual unit numbers; floor plan level data is still useful
- [2026-02-20]: AppFolio Sedgwick: use rentcafe_api_token for subdomain + rentcafe_property_id for address filter (avoids unique URL constraint)
- [2026-02-20]: SightMap embed regex must exclude api.js — sightmap.com/embed/api.js is a loader script, not an embed ID
- [2026-02-20]: Wolf Point East (MRI) actually has SightMap embed on /sightmap page — reclassified
- [2026-02-20]: Arkadia, Hugo, MILA had sightmap.com/embed/api.js pattern — same as Wolf Point East — now all SightMap
- [2026-02-20]: SecureCafe scraper now tries /floorplans and /floor-plans subpages — some buildings only have leasing link on floor plan page (Atwater Apartments pattern)
- [2026-02-20]: Units with rent="Call" are skipped gracefully, not errors — allows partial results where some units have no public price
- [2026-02-20]: AppFolio has two types: JS widget (Appfolio.Listing() embedded in building site) vs APM Sites (AppFolio-hosted website builder). Different scraping approach needed for each.
- [2026-02-20]: RealPage buildings use rpfp-* widget with AJAX loading from LeaseStar API (c-leasestar-api.realpage.com). propertyId in page JS. API not directly accessible without auth.
- [2026-02-19]: SightMap embeds hide behind many platforms (Funnel, RentCafe, RealPage, MRI) — reclassify to sightmap for reliable scraping
- [2026-02-19]: SecureCafe HTML scraping replaces RentCafe API credential approach — no auth needed, works across templates
- [2026-02-19]: Dates in SecureCafe come from two sources: `data-label="Date Available"` cell OR `ApplyNowClick()` onclick — parser checks both
- [2026-02-19]: Buildings with `area <= 1` in SightMap are placeholder units — filter them out
- [2026-02-18]: Sheet-wins platform model — Platform column in Google Sheet is the canonical override
- [2026-02-18]: Tier by ROI (Roxie direction) — platform scrapers first, management company scrapers second, true one-offs last

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 1 | Validation-first scraper pipeline: scrape one RentCafe building end-to-end and push results to Google Sheet Availability tab | 2026-02-19 | 2ee0ae0 | In Progress | [1-validation-first-scraper-pipeline-scrape](./quick/1-validation-first-scraper-pipeline-scrape/) |
| 2 | Validate non-PPM buildings: Funnel unit table, Groupfox two-step scraper, SightMap API scraper (10 buildings) | 2026-02-19 | pending | Completed | [2-pick-a-building-from-the-db-not-ppm-scra](./quick/2-pick-a-building-from-the-db-not-ppm-scra/) |
| 3 | SightMap reclassification, SecureCafe scraper, 12 buildings validated | 2026-02-19 | fa411cf | Completed | [3-validate-random-unvalidated-building-scr](./quick/3-validate-random-unvalidated-building-scr/) |
| 4 | Investigate remaining building groups (needs_classification, AppFolio, RealPage, Bozzuto, Entrata, MRI) | 2026-02-20 | 62510c8 | Verified | [4-validate-next-building-groups-needs-clas](./quick/4-validate-next-building-groups-needs-clas/) |
| 5 | Fix LLM scraper (Entrata/MRI floorplans probing), AppFolio Sedgwick scraper, SightMap api.js fix | 2026-02-20 | 9872665 | Completed | [5-continue-per-building-validation-pick-un](./quick/5-continue-per-building-validation-pick-un/) |

## Session Continuity

Last session: 2026-02-21
Stopped at: Phase 4 context gathered — auth, admin bootstrap, search endpoints, re-scrape workflow, deployment/CORS decisions captured.
Resume file: .planning/phases/04-api-layer/04-CONTEXT.md
