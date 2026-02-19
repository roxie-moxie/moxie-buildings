---
phase: quick-2
plan: 1
subsystem: scrapers
tags: [funnel, groupfox, sightmap, scraper, validation, normalizer]
dependency_graph:
  requires: [quick-1]
  provides: [funnel-unit-table, groupfox-two-step, sightmap-scraper, normalizer-rent-ranges]
  affects: [validate-building, push_availability, normalizer]
tech_stack:
  added: [sightmap.py]
  patterns:
    - "Funnel: table#apartments tr.unit for individual APT# rows, fallback to div.floor-plan cards"
    - "Groupfox: /floorplans index -> follow sub-pages -> tr.unit-container rows"
    - "SightMap: embed ID -> __APP_CONFIG__ -> JSON API with all unit data"
key_files:
  created:
    - src/moxie/scrapers/tier2/sightmap.py
  modified:
    - src/moxie/scrapers/tier2/funnel.py
    - src/moxie/scrapers/tier2/groupfox.py
    - src/moxie/normalizer.py
    - src/moxie/scrape.py
    - src/moxie/sync/push_availability.py
    - tests/test_scraper_groupfox.py
metrics:
  completed_date: "2026-02-19"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
  buildings_validated: 4
  total_units_scraped: 91
---

# Quick Task 2: Validate Non-PPM Buildings

## What Was Built

### Funnel scraper — unit table parser
- Added `_parse_unit_table()` for `table#apartments tr.unit` rows with real APT# numbers
- Falls back to `_parse_floorplan_cards()` when no unit table present
- Validated on **Imprint** — 15 individual units with real apartment numbers

### Groupfox scraper — full rewrite
- Two-step scrape: fetch `/floorplans` index → follow each floor plan sub-page
- Parses `tr.unit-container` rows for individual APT#, rent, availability date
- Skips "Contact Us" floor plans (no availability)
- Validated on **Axis** — 34 units across 8 floor plan types

### SightMap scraper — new platform (10 buildings)
- Discovered SightMap widget (`sightmap.com/embed/<ID>`) on 10 buildings
- Built `sightmap.py`: extract embed ID → resolve API URL from `__APP_CONFIG__` → fetch JSON
- Clean API returns unit_number, floor_plan, beds, baths, sqft, rent, availability date
- Updated DB platform to `sightmap` for all 10 buildings (AMLI, LUXE, EMME, Trio, Next)
- Validated on **EMME** (9 units) and **AMLI 900** (33 units)

### Normalizer fixes
- Rent ranges: "$2,211 – $2,799" → takes lower value ($2,211)
- Bare "Available" (without "Now") → treated as available today

## Buildings Validated

| Building | Platform | Units | Status |
|----------|----------|-------|--------|
| Imprint | funnel | 15 | Approved |
| Axis | groupfox | 34 | Approved |
| EMME | sightmap | 9 | Approved |
| AMLI 900 | sightmap | 33 | Approved |

## Tests

260 passing (all existing + 24 rewritten Groupfox tests)
