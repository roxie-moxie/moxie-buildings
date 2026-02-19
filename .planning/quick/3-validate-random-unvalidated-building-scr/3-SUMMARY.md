---
phase: quick-3
plan: 01
subsystem: scrapers
tags: [sightmap, funnel, validation, platform-reclassification]
dependency_graph:
  requires: []
  provides: [sightmap-placeholder-filter, funnel-sightmap-discovery]
  affects: [moxie.db, google-sheet-availability, sightmap.py]
tech_stack:
  added: []
  patterns: [sightmap-placeholder-filter, funnel-sightmap-hybrid]
key_files:
  created: []
  modified: [src/moxie/scrapers/tier2/sightmap.py, moxie.db]
decisions:
  - "SightMap units with area <= 1 are placeholder entries — filter them out"
  - "Many Funnel buildings (especially FLATS-managed livethe*.com) use SightMap embeds for availability data"
  - "The Ardus reclassified from funnel to sightmap — scraped 4 units successfully"
metrics:
  duration_minutes: 10
  completed_date: "2026-02-19"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Quick Task 3: Validate Random Buildings Summary

**One-liner:** Fixed SightMap placeholder filter, discovered Funnel/SightMap hybrid pattern — many "funnel" buildings actually serve availability via SightMap embeds.

## Buildings Validated

### Next (SightMap / Greystar / River North)

| Field | Value |
|-------|-------|
| Platform | SightMap |
| Units Scraped | 21 (was 22, placeholder #2004 filtered) |
| Verdict | PASS (after fix) |

**Fix applied:** Unit #2004 had floor plan "TEMP", no bed/bath, area=1 sqft. Added filter: skip units where `area <= 1`. Committed as `1d91385`.

### The Ardus (SightMap via Funnel / FLATS / River North)

| Field | Value |
|-------|-------|
| Original Platform | funnel (0 units) |
| Actual Platform | sightmap (4 units) |
| Units Scraped | 4 |
| Verdict | PASS (after platform reclassification) |

Units found:
- #225 Studio, 1 Bath, 504sqft, $2,100, Available Now
- #425 Studio, 1 Bath, 369sqft, $1,850, 3/5/2026
- #615 1BR, 1 Bath, 629sqft, $2,695, Available Now
- #702 3BR+, 2 Bath, 1,383sqft, $5,525, 4/2/2026

## Key Discovery: Funnel/SightMap Hybrid Pattern

17 of 18 Funnel buildings return 0 units. Investigation revealed many have SightMap embeds on their `/floorplans` page:

| Building | URL Pattern | SightMap Embed? |
|----------|-------------|----------------|
| The Ardus | livetheardus.com | Yes (confirmed, reclassified) |
| The Rosie | livetherosie.com | Yes (sightmap.com/embed/z40vl9olvle) |
| The Duncan | livetheduncan.com | Yes (sightmap.com/embed/l27vqox9pox) |
| Coeval | coevalchicago.com | No embed found |
| AM 1980 | liveam1980.com | Redirects to livetheweyland.com |

Many `livethe*.com` buildings (FLATS management company) are Funnel marketing sites with SightMap/Engrain embeds for availability. The Funnel scraper correctly returns 0 because the unit data isn't in Funnel's HTML — it's in the SightMap widget.

**Implication:** These buildings should be reclassified to platform=sightmap. This could convert many 0-unit Funnel buildings into working scrapers.

## Deviations from Plan

- Plan was single-building (Next). Extended to also validate The Ardus after user feedback on missing units.
- Discovered platform misclassification pattern not anticipated in plan.
