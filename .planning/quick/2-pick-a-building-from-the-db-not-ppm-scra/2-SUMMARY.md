---
phase: quick-2
plan: 1
subsystem: scrapers
tags: [funnel, scraper, validation, normalizer]
dependency_graph:
  requires: [quick-1]
  provides: [funnel-scraper-verified, normalizer-funnel-formats]
  affects: [validate-building, push_availability, normalizer]
tech_stack:
  added: []
  patterns:
    - "Funnel /floorplans/ page: div[data-beds] elements, data-price=-1 for unavailable"
    - "Normalizer: strip 'Starting at' rent prefix, strip 'Available ' date prefix"
key_files:
  created: []
  modified:
    - src/moxie/scrapers/tier2/funnel.py
    - src/moxie/normalizer.py
    - tests/test_scraper_funnel.py
decisions:
  - "Use data-price=-1 as availability filter (not available-units text) — more reliable"
  - "Floor plan name used as unit_number for Funnel buildings (no individual unit listings on main page)"
  - "Chose Imprint (Funnel) over needs_classification buildings to avoid LLM dependency with placeholder API key"
metrics:
  duration: "~30 minutes"
  completed_date: "2026-02-19"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 3
---

# Phase quick-2 Plan 1: Pick a Non-PPM Building and Scrape Summary

**One-liner:** Fixed Funnel scraper selectors against real Greystar/Funnel site (imprintapts.com), fixed normalizer for "Starting at $X" rent and "Available MM/DD/YYYY" date formats, scraped Imprint (12 floor plans) end-to-end to Google Sheet.

## What Was Built

### Task 1: Pick a non-PPM building and run validate-building (COMPLETE)

Selected **Imprint** (`https://imprintapts.com/`) — a Funnel-platform building — instead of `needs_classification` buildings, because:
- The ANTHROPIC_API_KEY in `.env` is a placeholder (`your_key_here`) — LLM scraper would fail
- Funnel buildings use Tier 2 CSS scraping (no API key needed)
- Imprint's Funnel-powered `/floorplans/` page has verifiable HTML structure

**Scrape result:**
- Platform: `funnel`
- Units scraped: **12** available floor plans
- Saved to DB: yes
- Pushed to Availability tab: **12 units**
- Building data verified end-to-end

### Task 2: User validates building data in Google Sheet (PENDING)

**Status:** Awaiting user validation. The Availability tab has been populated with Imprint's 12 available floor plans. See checkpoint below for verification steps.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Funnel scraper had unverified, non-functional CSS selectors**
- **Found during:** Task 1 (running validate-building)
- **Issue:** Scraper looked for `[class*='unit-listing'], [class*='unit-row'], [class*='floorplan-row']` — none of which exist in real Funnel HTML. Real structure uses `div[data-beds]` with `data-price`, `data-baths`, `data-first-available-date` attributes.
- **Fix:** Rewrote `_parse_html()` to use verified selectors. Added `_normalize_floorplans_url()` to resolve building URL to `/floorplans/`. Used `data-price=-1` as the unavailability filter.
- **Files modified:** `src/moxie/scrapers/tier2/funnel.py`, `tests/test_scraper_funnel.py`
- **Commit:** a56c2cf

**2. [Rule 1 - Bug] Normalizer could not parse "Starting at $X" rent format**
- **Found during:** Task 1 (validate-building error after scraper fixed)
- **Issue:** `normalize_rent` stripped `$`, `,`, `/mo` but not the "Starting at" prefix common in Funnel floor plan pricing.
- **Fix:** Added prefix strip for "starting at" before the numeric parse.
- **Files modified:** `src/moxie/normalizer.py`
- **Commit:** a56c2cf

**3. [Rule 1 - Bug] Normalizer could not parse "Available MM/DD/YYYY" date format**
- **Found during:** Task 1 (tested full normalize pipeline)
- **Issue:** `normalize_date` handled "available now" but not "Available 03/25/2026" style dates common in Funnel output.
- **Fix:** Added strip for "available " prefix before dateutil parse.
- **Files modified:** `src/moxie/normalizer.py`
- **Commit:** a56c2cf

**4. [Rule 2 - Missing Aliases] Bed type aliases missing for Funnel formats**
- **Found during:** Task 1 (testing full pipeline)
- **Issue:** Aliases for "2 beds", "3 beds", "4 beds", "loft studio", "convertible deluxe" were absent; these would be flagged non_canonical=True.
- **Fix:** Added aliases: `2 beds->2BR`, `3 beds->3BR+`, `4 beds->3BR+`, `4 bed->3BR+`, `loft studio->Studio`, `convertible deluxe->Convertible`.
- **Files modified:** `src/moxie/normalizer.py`
- **Commit:** a56c2cf

### Scope Change

**Building choice:** The plan suggested `needs_classification` buildings (Lincoln Park Plaza, Verdant Apartments, SCIO Chicago) but those route to the LLM scraper. Since ANTHROPIC_API_KEY is a placeholder, those would fail. Switched to **Imprint** (Funnel platform) — a Tier 2 CSS scraper that works without an API key.

## Checkpoint: User Validation Pending

**Google Sheet:** https://docs.google.com/spreadsheets/d/1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI

**Availability tab should show 12 rows for Imprint with columns:**
Building Name, Neighborhood, Unit #, Beds, Rent, Available Date, Floor Plan, Baths, SqFt, Management Company, Scraped At, URL

**Expected data quality:**
- Building Name: "Imprint"
- Unit # / Floor Plan: Names like "One Bedroom E", "Studio C", "Convertible D"
- Beds: "Studio", "1BR", "Convertible" (after normalization)
- Rent: "$1,976" to "$2,881" (Chicago mid-range, reasonable)
- Available Date: "2026-02-19" (Available Now) or future dates like "2026-03-25"
- URL: "https://imprintapts.com/"

**Note:** These are floor plan starting prices, not individual unit listings. Imprint's public website doesn't expose individual unit numbers — only floor plan types with "starting at" prices. This is a Funnel platform limitation.

## Commits

| Hash | Description |
|------|-------------|
| a56c2cf | feat(quick-2): scrape Imprint (Funnel) end-to-end - 12 units to sheet |

## Self-Check: PASSED

Files modified exist:
- src/moxie/scrapers/tier2/funnel.py - FOUND
- src/moxie/normalizer.py - FOUND
- tests/test_scraper_funnel.py - FOUND

Commit a56c2cf exists in git log.

Test suite: 256 passed, 0 failed.
