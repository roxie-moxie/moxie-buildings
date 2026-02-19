---
phase: quick-3
plan: 01
subsystem: scrapers
tags: [sightmap, greystar, validation, scraper]
dependency_graph:
  requires: []
  provides: [sightmap-greystar-validated]
  affects: [moxie.db, google-sheet-availability]
tech_stack:
  added: []
  patterns: [sightmap-api-discovery]
key_files:
  created: []
  modified: [moxie.db]
decisions:
  - "SightMap scraper confirmed working for Greystar-managed buildings (Next, River North)"
metrics:
  duration_minutes: 2
  completed_date: "2026-02-19"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Quick Task 3: Validate Next (SightMap / Greystar) Summary

**One-liner:** SightMap scraper confirmed for Greystar's Next building — 22 units scraped and pushed to Google Sheet in one pass.

## Result

| Field | Value |
|-------|-------|
| Building | Next |
| Platform | SightMap |
| Management Company | Greystar |
| Neighborhood | River North |
| URL | https://www.nextapts.com/ |
| Units Scraped | 22 |
| Units in DB | 22 |
| Sheet Updated | Yes (22 rows written) |
| Verdict | PASS |

## Full CLI Output

```
Building:  Next
Platform:  sightmap
URL:       https://www.nextapts.com/
Units scraped: 22
Saved to database.
Pushed 22 unit(s) to Availability tab.

--- Validation Summary ---
Building:     Next
Platform:     sightmap
Units scraped: 22
Units in sheet: 22
DB status:    saved
```

## SightMap Scraper Verdict

CONFIRMED WORKING for a Greystar-managed building.

The SightMap discovery + API pattern (fetch building site, find sightmap.com embed, parse `__APP_CONFIG__`, call public JSON API) worked without modification against a third distinct management company. Prior validations were EMME and AMLI 900 (both different operators).

SightMap scraper status: 3 buildings verified across 3 management companies, 10 buildings total in the platform group.

## Deviations from Plan

None — plan executed exactly as written.
