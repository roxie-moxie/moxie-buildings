# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Validation-first scraper pipeline — one building at a time, validate with user

## Current Position

Phase: 2 of 5 (Scrapers) — IN PROGRESS (gap closure)
Status: Platform group investigation complete. SecureCafe fixed to check subpages. Atwater Apartments (Bozzuto) working. Patterns mapped for AppFolio/RealPage/Entrata/MRI.
Last activity: 2026-02-20 - Investigated 20+ buildings across all remaining groups. Fixed 2 SecureCafe bugs. Atwater 34 units working. Management company patterns documented.

Progress: [█████████░] 75%

---

## What's Done (this session)

### SightMap scraper validated + mass reclassification
- SightMap JSON API scraper confirmed across multiple management companies (Greystar, AMLI, LMC, FLATS, Magellan)
- Discovered Funnel/SightMap hybrid pattern: 13 "funnel" buildings actually serve data via SightMap embeds
- Scanned all 361 non-SightMap buildings for SightMap embeds — found 31 more (23 RentCafe, 3 RealPage, 4 Funnel, 1 MRI)
- Scanned 66 `needs_classification` buildings — found 4 more SightMap embeds
- **SightMap now covers 54 buildings** (up from 10 original)
- Fixed SightMap placeholder filter: skip units with `area <= 1` (catches "TEMP" floor plans)

### SecureCafe scraper built (NEW — biggest unlock)
- `src/moxie/scrapers/tier2/securecafe.py` — Crawl4AI two-step approach
- Step 1: Render marketing site to discover `securecafe.com/onlineleasing/` URL
- Step 2: Fetch `availableunits.aspx` and parse `tr.AvailUnitRow` elements
- Dates extracted from `data-label="Date Available"` cell OR `ApplyNowClick()` onclick fallback
- Handles `12/31/9999` as "Available Now", price ranges (normalizer takes lower)
- **Replaces broken RentCafe API credential approach entirely**
- Registered as `rentcafe` platform in both `scrape.py` and `push_availability.py`

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

### Platform distribution (current)
| Platform | Buildings | Scraper Status |
|----------|-----------|---------------|
| RentCafe (SecureCafe) | 220 | **Working** (Atwater + Marlowe added) |
| needs_classification | 59 | Unscraped (-2 reclassified) |
| SightMap | 54 | **Working** (validated) |
| PPM | 19 | **Working** |
| AppFolio | 18 | Broken — 2 types: JS widget (Sedgwick Prop) vs APM Sites |
| Groupfox | 13 | **Working** (validated) |
| Entrata | 10 | LLM fallback — 0 units (LLM sees homepage, not availability page) |
| RealPage | 5 | Broken — rpfp-* JS widget, AJAX loads from LeaseStar API |
| MRI | 5 | LLM fallback — 0 units (same issue as Entrata) |
| Funnel | 2 | Working (mostly 0 units) |
| Bozzuto | 1 | SSL issues on remaining building |

**Working scraper coverage: 306 of 407 buildings (75%)**

---

## What's In Progress / Not Done

### Remaining validation
- 59 `needs_classification` buildings — most return no known platform patterns (custom sites, small properties)
- AppFolio (18) — two types discovered: JS widget type (Sedgwick Properties) could work; APM Sites type needs different URL
- RealPage (5) — rpfp-* widget loads via AJAX from LeaseStar API, not scrapeable via static HTML
- Entrata (10) + MRI (5) — LLM fallback runs on homepage, returns 0 units; need to point at floorplans page
- The Marlowe — reclassified to rentcafe but SecureCafe URL only in API response JSON (not discoverable via scraper)

### Known issues
- Some SecureCafe templates have "Date Available" column, others hide dates in ApplyNowClick() — both handled
- Funnel scraper only works for 1 building (Imprint) — remaining 2 return 403 or 0 units
- 4 buildings matched `sightmap.com/embed/api` (Arkadia, Hugo, MILA, Sky55) — deferred, different URL pattern
- Related Rentals buildings (3) — proprietary platform, no known scraping approach
- BJB Properties (3) — blocks all bots, no accessible availability data

---

## Next Steps (in order)

1. **Fix AppFolio JS widget scraper** — Sedgwick Properties buildings (1325 N Wells, Arco Old Town) use Appfolio.Listing() widget. Try calling sedgwickproperties.appfolio.com/listings directly via API.
2. **Fix LLM scraper to try floorplans subpage** — Entrata (10) + MRI (5) LLM sees homepage, not units. Point at /floorplans.
3. **Batch scan remaining needs_classification (59)** — run Crawl4AI check for securecafe.com/onlineleasing/ on all 59. Atwater pattern may apply to more.
4. **Run bed type audit** — `SELECT COUNT(*) FROM units WHERE non_canonical = 1`
5. **Phase 3: Scheduler** — daily batch runner, per-platform concurrency limits

---

## Key Decisions (this session)

- [2026-02-20]: SecureCafe scraper now tries /floorplans and /floor-plans subpages — some buildings only have leasing link on floor plan page (Atwater Apartments pattern)
- [2026-02-20]: Units with rent="Call" are skipped gracefully, not errors — allows partial results where some units have no public price
- [2026-02-20]: AppFolio has two types: JS widget (Appfolio.Listing() embedded in building site) vs APM Sites (AppFolio-hosted website builder). Different scraping approach needed for each.
- [2026-02-20]: RealPage buildings use rpfp-* widget with AJAX loading from LeaseStar API (c-leasestar-api.realpage.com). propertyId in page JS. API not directly accessible without auth.
- [2026-02-20]: Entrata/MRI LLM fallback returns 0 because it scrapes homepage. Fix: pass /floorplans URL to LLM scraper.
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
| 4 | Investigate remaining building groups (needs_classification, AppFolio, RealPage, Bozzuto, Entrata, MRI) | 2026-02-20 | 62510c8 | Completed | [4-validate-next-building-groups-needs-clas](./quick/4-validate-next-building-groups-needs-clas/) |

## Session Continuity

Last session: 2026-02-20
Stopped at: Platform group investigation complete. Atwater Apartments (Bozzuto) reclassified to rentcafe and working (34 units). SecureCafe scraper fixed to check floorplan subpages. Management company patterns documented. 75% coverage maintained. Next: fix AppFolio JS widget scraper, fix LLM to try floorplans page, batch scan remaining needs_classification for SecureCafe.
Resume file: .planning/phases/02-scrapers/.continue-here.md
