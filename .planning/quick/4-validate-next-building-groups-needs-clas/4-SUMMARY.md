---
phase: quick-4
plan: 01
subsystem: scrapers
tags: [securecafe, appfolio, realpage, bozzuto, entrata, mri, needs_classification, investigation]

requires:
  - phase: quick-3
    provides: "SecureCafe scraper, SightMap validation, 75% coverage"

provides:
  - "Investigation of 20+ buildings across needs_classification, AppFolio, RealPage, Bozzuto, Entrata, MRI groups"
  - "SecureCafe scraper enhanced to discover URL from floorplans subpages"
  - "Normalizer handles non-numeric rent values (Call, N/A, Contact)"
  - "save_scrape_result skips individual invalid units instead of crashing"
  - "Atwater Apartments (Bozzuto) reclassified and working: 34 units"
  - "Left Bank reclassified to entrata (Entrata powered)"
  - "The Marlowe reclassified to rentcafe (RentCafe API variant)"
  - "Management company pattern map for needs_classification buildings"

affects: [scrapers, coverage, needs_classification, bozzuto, realpage, appfolio, entrata, mri]

tech-stack:
  added: []
  patterns:
    - "SecureCafe discovery: try homepage + /floorplans + /floor-plans before failing"
    - "Normalizer: reject non-numeric rent placeholders (Call, N/A, TBD) instead of crashing"
    - "save_scrape_result: per-unit error isolation — ValidationError skips unit, doesn't abort batch"
    - "RealPage sites: use /Floor-plans.aspx or /floor-plans.aspx URL pattern, load data via rpfp-* JS widget"
    - "AppFolio sites: two types — JS widget (Appfolio.Listing on /floor-plans) and AppFolio Property Sites (no listing widget)"

key-files:
  created: []
  modified:
    - "src/moxie/scrapers/tier2/securecafe.py"
    - "src/moxie/scrapers/base.py"
    - "src/moxie/normalizer.py"

key-decisions:
  - "SecureCafe scraper now tries /floorplans and /floor-plans subpages to discover leasing URL — fixes Atwater Apartments and other buildings where SecureCafe link only appears on floor plan subpage"
  - "Units with rent=Call are skipped (not errors) — enables partial scraping of buildings where some units have no public price"
  - "RealPage buildings (5): all use rpfp-* JS widget that loads via AJAX from LeaseStar API — not scrapeable without API credentials or browser automation with longer wait"
  - "AppFolio buildings: two distinct types — JS widget type (works via Crawl4AI with enough wait) and APM Sites type (builds website, no JS listing widget discoverable)"
  - "Entrata/MRI LLM fallback runs on homepage, which has no unit data — both returned 0 units; LLM needs to be pointed at the actual floorplans/availability page"
  - "Left Bank confirmed Entrata powered (has residentportal.com + qburst-entrata plugin)"
  - "Atwater Apartments (Bozzuto) is actually SecureCafe powered — floor-plans page contains onlineleasing link, not homepage"

requirements-completed: [SCRAPER-REMAINING-PLATFORMS]

duration: 90min
completed: 2026-02-20
---

# Quick Task 4: Building Group Investigation Summary

**Diagnosed 20+ buildings across all remaining unscraped groups; fixed SecureCafe to discover leasing URLs from subpages; unlocked Atwater Apartments (34 units); mapped management company patterns for needs_classification**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-02-20T00:00:00Z
- **Completed:** 2026-02-20T02:00:00Z
- **Tasks:** 3 of 3 completed
- **Files modified:** 3 code files, moxie.db

## Accomplishments

- Fixed SecureCafe scraper to check /floorplans and /floor-plans subpages, unlocking Atwater Apartments (34 units scraped, 33 pushed to sheet)
- Fixed normalizer to handle "Call" rent values gracefully (skip unit, not crash)
- Fixed save_scrape_result to isolate per-unit validation errors
- Investigated 20+ buildings across all remaining groups to map management company patterns
- Diagnosed AppFolio (JS widget vs APM Sites), RealPage (LeaseStar JS widget), Bozzuto (SecureCafe reuse confirmed), Entrata/MRI (LLM sees homepage not availability page)
- Reclassified Left Bank → entrata, The Marlowe → rentcafe, Atwater → rentcafe
- needs_classification went from 61 → 59

## Task Commits

1. **Task 1+2+3: Investigation + bug fixes** - `62510c8` (fix)

## Building-by-Building Investigation Results

### needs_classification Buildings Investigated

| Building | Original Platform | Discovered Source | Action Taken | Result |
|----------|-------------------|-------------------|--------------|--------|
| 1325 N Wells | needs_classification | AppFolio (sedgwickproperties.appfolio.com, "1325 N Wells - Website") | No action — AppFolio JS widget needs Crawl4AI with wait | Pattern: Sedgwick Properties manages via AppFolio |
| The Bachelor | needs_classification | 403 blocked (FLATS/livethe*.com) | No action | Cannot access |
| 1471 N Milwaukee | needs_classification | 404 — site dead | No action | Dead site |
| 3141 N Sheffield (BJB) | needs_classification | Connection refused | No action | BJB Properties blocks bots |
| Left Bank | needs_classification | Entrata (residentportal.com + qburst-entrata plugin) | Reclassified → entrata | In LLM fallback queue |
| The Marlowe | needs_classification | RentCafe API (api.rentcafe.com with token ee5f203d) | Reclassified → rentcafe | Scraper fails — RentCafe API variant, SecureCafe URL only in API response JSON |
| Arco Old Town | needs_classification | AppFolio (sedgwickproperties.appfolio.com, "Arco Old Town - Website") | No action | Same management as 1325 N Wells |
| Six Corners Lofts | needs_classification | AppFolio plugin (listings-for-appfolio WP plugin) | No action | AppFolio JS widget type |
| River North Lofts | needs_classification | Funnel (funnelleasing.com reference) | No action | Funnel buildings often return 0 units |
| The Porter | needs_classification | SecureCafe resident portal (highrisepeakproperties.securecafenet.com) | Tried rentcafe, reverted — no onlineleasing URL found | No accessible leasing portal |
| 2317 N Clark | needs_classification | RentCafe staging domain (rcmvctest.com) — 403 | No action | Site not publicly accessible |
| 73 E Lake | needs_classification | SquareSpace website | No action | No known platform pattern |
| No. 508 | needs_classification | SightMap JS calculator widget (jd-fp-sightmap-calculator-wrap) | No action | Embed ID not in HTML, needs different discovery |
| The Streeter | needs_classification | WordPress + iframe to ste-sightmap-final.tempurl.host | No action | Custom domain, not standard sightmap.com/embed |
| The Porter | needs_classification | SecureCafe resident portal only | Reverted to needs_classification | No leasing portal |
| 500 Lake Shore Drive | needs_classification | Related Rentals custom platform | No action | No known scraping approach |
| The Row Fulton Market | needs_classification | Related Rentals custom platform | No action | No known scraping approach |
| One Bennett Park | needs_classification | Related Rentals custom platform | No action | No known scraping approach |

### Broken Platform Scrapers Diagnosed (Task 2)

| Building | Platform | Diagnosis | Recommendation |
|----------|----------|-----------|----------------|
| Atwater Apartments | bozzuto → rentcafe | Floor-plans page has securecafe.com/onlineleasing/ link. Scraper only checked homepage. Fixed. | DONE — 34 units working |
| Logan Apartments | bozzuto | SSL error on all subpages | Try LLM fallback |
| Luxe on Chicago | realpage | Uses rpfp-* JS widget that loads unit data via AJAX from LeaseStar API. No static HTML. propertyId=6500005 | Need API credentials or extended JS wait |
| All 5 RealPage buildings | realpage | Same pattern — rpfp-* widget, AJAX-loaded | Consider LLM fallback or skip |
| Astoria Tower | appfolio | Uses AppFolio Property Sites (APM Sites) website builder — has APM logo but no Appfolio.Listing widget | Wrong scraper type — these use different listing URL |

### AppFolio Pattern Discovery

Two distinct types of AppFolio buildings:

**Type 1: AppFolio JS Widget** (Sedgwick Properties managed: 1325 N Wells, Arco Old Town, Six Corners Lofts)
- Building's own WordPress/Squarespace site
- Embeds Appfolio.Listing() JS widget on /floor-plans page
- sedgwickproperties.appfolio.com property groups
- Widget loads from external JS — needs Crawl4AI + long wait time
- Approx 3 buildings confirmed

**Type 2: AppFolio Property Sites (APM Sites)**
- Entire website hosted by AppFolio
- Has AppFolio footer logo but no embedded listing widget
- Unit listings at a different URL (appfolio.com/listings or property-specific)
- Astoria Tower is this type — URL: astoriatowerchicago.com (APM Sites built)
- DLG Chicago Rentals, Monroe Laflin Place also likely this type

### Entrata/MRI LLM Fallback Results (Task 3)

| Building | Platform | LLM Result | Issue |
|----------|----------|------------|-------|
| Echelon at K Station | entrata | 0 units | LLM ran on homepage, no unit data there |
| Arrive LEX | mri | 0 units | LLM ran on homepage, no unit data there |

**Root cause:** LLM scraper uses `building.url` (homepage) which shows marketing content, not unit listings. Entrata units are typically at `/floorplans` or a dedicated leasing portal. Fix needed: LLM scraper should try floorplans subpage.

## Management Company Pattern Map

| Management Company | Platform Pattern | Example Buildings |
|-------------------|-----------------|-------------------|
| Sedgwick Properties | AppFolio JS Widget (sedgwickproperties.appfolio.com) | 1325 N Wells, Arco Old Town |
| Related Rentals | Proprietary (relatedrentals.com) | 500 Lake Shore Drive, The Row Fulton Market, One Bennett Park |
| BJB Properties | BJB property pages (blocks bots) | 3141 N Sheffield, 320 N Michigan, 424 Diversey |
| Morguard/Alta | 403 blocked | Alta, others |
| HighRise Peak Properties | SecureCafe resident portal only (no public leasing URL) | The Porter |
| FLATS (livethe*.com) | 403 blocked | The Bachelor |
| Trinity | Renew Waterside 403 blocked | Renew Waterside |

## Updated Coverage

| Platform | Buildings | Status |
|----------|-----------|--------|
| RentCafe (SecureCafe) | 220 | Working |
| SightMap | 54 | Working |
| PPM | 19 | Working |
| Groupfox | 13 | Working |
| **Working total** | **306/407 (75%)** | |
| needs_classification | 59 (was 61) | -2 reclassified |
| AppFolio | 18 | Broken (0 units returned) |
| Entrata | 10 (was 9, +Left Bank) | LLM fallback, 0 units |
| MRI | 5 | LLM fallback, 0 units |
| RealPage | 5 | Broken (rpfp JS widget, AJAX) |
| Bozzuto | 1 (was 2) | Broken/SSL |
| Funnel | 2 | Mostly broken |
| Dead | 1 | - |

## Prioritized Next Steps

1. **Fix AppFolio JS widget scraper** — 3 confirmed buildings (Sedgwick Properties) use `Appfolio.Listing()` widget. Can likely scrape by: calling `sedgwickproperties.appfolio.com/listings?property_group=NAME` directly. High ROI.

2. **Fix LLM scraper to try floorplans subpage** — Entrata (10) and MRI (5) buildings. LLM currently runs on homepage with no unit data. Try `/floorplans` or `/floor-plans` subpage first. Could unlock 15 buildings.

3. **Batch test remaining needs_classification** — 59 buildings still unclassified. Many may use SecureCafe (like Atwater). Run Crawl4AI check on all 59 for `securecafe.com/onlineleasing/` pattern. Potential: 10-20 more buildings.

4. **RealPage API investigation** — 5 buildings. The rpfp widget calls LeaseStar API with propertyId. Need to intercept XHR or find public API endpoint. Lower priority.

5. **Related Rentals scraper** — 3 buildings (500 Lake Shore, The Row, One Bennett Park). All on relatedrentals.com. Shared platform means one scraper works for all 3.

6. **AppFolio Property Sites** — Different from JS widget. Need to find the listings URL pattern for APM-Sites hosted properties.

## Files Created/Modified

- `src/moxie/scrapers/tier2/securecafe.py` - Try /floorplans and /floor-plans subpages for SecureCafe URL discovery
- `src/moxie/scrapers/base.py` - Per-unit error isolation (skip invalid units, don't crash save)
- `src/moxie/normalizer.py` - Reject non-numeric rent placeholders (Call, N/A, Contact, TBD)
- `moxie.db` - Reclassified: Atwater Apartments → rentcafe, Left Bank → entrata, The Marlowe → rentcafe

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SecureCafe scraper only checked homepage for leasing URL**
- **Found during:** Task 1 (investigating Atwater Apartments / Bozzuto)
- **Issue:** SecureCafe scraper rendered only `building.url` (homepage) to discover the `securecafe.com/onlineleasing/` URL. Atwater Apartments has the link on `/floor-plans`, not the homepage.
- **Fix:** Added loop to try homepage, /floorplans, and /floor-plans pages in sequence
- **Files modified:** `src/moxie/scrapers/tier2/securecafe.py`
- **Verification:** Atwater Apartments now scrapes 34 units successfully
- **Committed in:** `62510c8`

**2. [Rule 1 - Bug] Normalizer crashed on rent="Call" (no public price)**
- **Found during:** Task 2 (Atwater Apartments validation returned 34 units but crashed on save)
- **Issue:** Some SecureCafe units have rent="Call" (price by phone only). Normalizer raised ValueError, aborting the entire save of 34 units.
- **Fix:** Added explicit rejection list for non-numeric placeholders (Call, N/A, Contact, TBD, Inquire) in normalizer; fixed save_scrape_result to catch per-unit ValidationError and skip that unit
- **Files modified:** `src/moxie/normalizer.py`, `src/moxie/scrapers/base.py`
- **Verification:** Atwater saves 33/34 units (1 "Call" unit skipped gracefully)
- **Committed in:** `62510c8`

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes essential for correctness. The SecureCafe subpage fix is a significant enhancement that applies to any building where leasing links appear on the floor plans page rather than the homepage.

## Self-Check

- `src/moxie/scrapers/tier2/securecafe.py` - FOUND (modified)
- `src/moxie/scrapers/base.py` - FOUND (modified)
- `src/moxie/normalizer.py` - FOUND (modified)
- Commit `62510c8` - FOUND in git log

## Self-Check: PASSED

---
*Phase: quick-4*
*Completed: 2026-02-20*
