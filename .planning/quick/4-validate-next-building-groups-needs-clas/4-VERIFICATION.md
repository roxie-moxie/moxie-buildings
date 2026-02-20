---
phase: quick-4
verified: 2026-02-20T08:30:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Quick Task 4: Building Group Investigation — Verification Report

**Task Goal:** Validate next building groups: needs_classification, AppFolio, RealPage, Bozzuto — one building at a time, discover patterns
**Verified:** 2026-02-20T08:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | At least 5 needs_classification buildings are investigated and either reclassified to a working platform or documented as requiring a new approach | VERIFIED | SUMMARY table lists 18 needs_classification buildings investigated. 2 reclassified (Left Bank → entrata, The Marlowe → rentcafe). needs_classification count dropped 61 → 59 confirmed in DB. |
| 2 | At least one building from each broken platform (AppFolio, RealPage, Bozzuto) is tested and the failure mode is diagnosed | VERIFIED | SUMMARY documents: Astoria Tower (AppFolio) → APM Sites type, no listing widget. Luxe on Chicago (RealPage) → rpfp-* JS widget, AJAX from LeaseStar API. Atwater Apartments (Bozzuto) → SecureCafe on /floor-plans subpage — reclassified and working (33 units in DB). |
| 3 | At least one Entrata and one MRI building is tested via LLM fallback | VERIFIED | Echelon at K Station (entrata): status=success, 0 units — LLM ran on homepage. Arrive LEX (mri): status=success, 0 units — same root cause documented. Both scraped (confirmed by DB status=success) and failure mode identified: LLM sees homepage not availability page. |
| 4 | Findings are documented with clear patterns: which management companies map to which actual data sources | VERIFIED | SUMMARY.md contains: Management Company Pattern Map table (Sedgwick Properties → AppFolio JS widget, Related Rentals → proprietary, BJB Properties → blocks bots, etc.), AppFolio pattern discovery (Type 1 JS widget vs Type 2 APM Sites), RealPage diagnosis (rpfp-* widget + LeaseStar API), Entrata/MRI LLM root cause. STATE.md updated with all findings and prioritized next steps. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `moxie.db` | Reclassified buildings and newly scraped units | VERIFIED | Atwater Apartments: platform=rentcafe, 33 units, status=success. Left Bank: platform=entrata. The Marlowe: platform=rentcafe. needs_classification: 59 (was 61). bozzuto: 1 (was 2). |
| `.planning/quick/4-validate-next-building-groups-needs-clas/4-SUMMARY.md` | Documented findings, patterns, and next steps | VERIFIED | File exists, 230 lines. Contains building-by-building results table (18 needs_classification + 5 broken platform entries), platform distribution table, management company pattern map, prioritized next steps. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| needs_classification investigation | SightMap/SecureCafe reclassification | Checking building websites for sightmap.com/embed or securecafe.com links | PARTIAL | Investigation ran on 18 buildings. Atwater Apartments (Bozzuto, not needs_classification) was reclassified to rentcafe via SecureCafe subpage discovery. Of needs_classification: The Marlowe → rentcafe (API variant not scrapeable), Left Bank → entrata. Most others: dead sites, 403 blocks, no known pattern. No SightMap embeds found in needs_classification sample. |
| broken scraper diagnosis | scraper fix or platform reclassification | Running validate-building, inspecting HTML, checking for alternative data sources | VERIFIED | Atwater: reclassified + working. SecureCafe scraper fixed to try /floorplans and /floor-plans subpages (commit 62510c8, confirmed in securecafe.py lines 185-197). Normalizer fixed for rent="Call" (normalizer.py lines 116-119). base.py per-unit error isolation added (base.py lines 56-63). |

### Code Artifact Verification

| File | Level 1: Exists | Level 2: Substantive | Level 3: Wired | Notes |
|------|-----------------|----------------------|----------------|-------|
| `src/moxie/scrapers/tier2/securecafe.py` | YES (214 lines) | YES — candidate_urls loop (lines 185-197), tries /floorplans and /floor-plans | YES — wired through scrape.py (pre-existing platform routing) | Commit 62510c8 changed 29 lines. Discovery loop confirmed in file. |
| `src/moxie/normalizer.py` | YES (199 lines) | YES — rejection list at lines 116-119: `("call", "n/a", "contact", "tbd", "inquire", "", "0")` | YES — called by base.py save_scrape_result | ValueError raised for non-numeric placeholders. |
| `src/moxie/scrapers/base.py` | YES (94 lines) | YES — try/except ValidationError/ValueError at lines 57-63 skips invalid units | YES — used by all scrapers on save | Per-unit isolation prevents full batch abort on Call-priced units. |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| SCRAPER-REMAINING-PLATFORMS | Investigate and diagnose remaining platform groups beyond 75% coverage | SATISFIED | 20+ buildings investigated across needs_classification, AppFolio, RealPage, Bozzuto, Entrata, MRI. Failure modes documented for all 4 broken platforms. Management company patterns mapped. STATE.md updated. |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `moxie.db` — The Marlowe | Reclassified to rentcafe but scraper cannot find SecureCafe URL (only in API response JSON) | WARNING | The Marlowe will fail on next scrape run — reclassification is documented as non-functional in SUMMARY.md. Not a code defect; a known limitation documented for follow-up. |

No code-level stubs, TODO placeholders, or empty implementations found in the three modified files.

### Human Verification Required

None required. All verification is fully automated:
- DB platform counts confirmed via Python query
- Unit counts verified (Atwater: 33 units, expected 33-34)
- Code changes verified via git diff and direct file read
- Scrape run statuses (Echelon at K Station: success/0 units, Arrive LEX: success/0 units) confirm LLM fallback ran

## Summary

All four must-have truths are verified. The task goal was investigation and pattern discovery — not 100% scraper fixes — and that goal was achieved:

1. 18 needs_classification buildings investigated; 2 reclassified
2. All three broken platforms (AppFolio, RealPage, Bozzuto) have documented failure modes with specific technical details
3. Both Entrata and MRI LLM fallback tested; root cause identified (homepage vs availability page)
4. Three code fixes ship with commit 62510c8: SecureCafe subpage discovery, normalizer Call-rent handling, per-unit error isolation
5. Atwater Apartments (Bozzuto → rentcafe) is the one concrete scraper unlock: 33 units, status=success

Coverage remains 75% (306/407) — no net new buildings scraped beyond Atwater, which is consistent with the investigation focus. The Marlowe reclassification is documented as non-functional (cannot discover SecureCafe URL), which is an honest finding rather than an error.

---
_Verified: 2026-02-20T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
