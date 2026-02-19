---
phase: 02-scrapers
verified: 2026-02-18T00:00:00Z
status: gaps_found
score: 3/5 success criteria verified
gaps:
  - truth: "Running any individual scraper module against its target buildings produces normalized unit records in the database"
    status: partial
    reason: "RentCafe scraper (covering ~220 buildings, 55% of total) always raises NotImplementedError from _fetch_units() — it cannot produce unit records under any circumstances. The scraper structure and error-handling are complete; the actual API call is an intentional stub awaiting credential confirmation. All other scrapers (PPM, Funnel, AppFolio, Bozzuto, RealPage, Groupfox, LLM) have functional scrape() implementations."
    artifacts:
      - path: "src/moxie/scrapers/tier1/rentcafe.py"
        issue: "_fetch_units() always raises NotImplementedError — the module cannot produce units for any building"
    missing:
      - "Either replace _fetch_units() stub with real httpx call using confirmed credentials/endpoint, OR explicitly acknowledge in SC1 that RentCafe is a planned stub and adjust the success criterion to exclude it"

  - truth: "The Yardi/RentCafe scraper has a confirmed access method documented before any Yardi scraper code is merged — not assumed, confirmed"
    status: failed
    reason: "RESEARCH.md documents that the RentCafe API requires per-property apiToken/companyCode/propertyCode credentials embedded in building JavaScript pages. RESEARCH.md explicitly labels this as requiring a 'spike task to confirm the credential extraction pattern' before full implementation. The access method is described as needing investigation — it is NOT confirmed. The rentcafe.py stub was merged with this open question unresolved."
    artifacts:
      - path: "src/moxie/scrapers/tier1/rentcafe.py"
        issue: "Stub merged before access method was confirmed; _fetch_units raises NotImplementedError"
      - path: ".planning/phases/02-scrapers/02-RESEARCH.md"
        issue: "SCRAP-01 row explicitly states 'Investigation task required before full implementation' — credential extraction pattern not confirmed"
    missing:
      - "Run the RentCafe credential spike: fetch 2-3 known RentCafe building URLs, extract apiToken/companyCode/propertyCode from HTML/JS, hit the real endpoint, document exact field names and confirm requestType=apartmentavailability works"
      - "Document the confirmed access method in RESEARCH.md or a dedicated spike doc before considering this criterion met"

  - truth: "A post-scrape audit query run after each tier's scrapers confirms zero units in the database carry non-canonical bed type values"
    status: failed
    reason: "The infrastructure for detecting non-canonical bed types exists: normalizer.py sets non_canonical=True on the Unit record when bed_type is not in CANONICAL_BED_TYPES. However, no post-scrape audit query was documented as having been run in Phase 2. No audit script exists. No SUMMARY.md references running such a query against the live database. The mechanism is in place but the audit itself was not performed."
    artifacts:
      - path: "src/moxie/normalizer.py"
        issue: "non_canonical flag exists on Unit but no audit query was run to confirm zero non-canonical units in the DB"
    missing:
      - "Run: sqlite3 moxie.db \"SELECT COUNT(*) FROM units WHERE non_canonical = 1;\" after scraper execution and document the result"
      - "Alternatively, create scripts/audit_bed_types.py that queries the DB and asserts zero non-canonical values, run it, and document results in a SUMMARY"

human_verification:
  - test: "Confirm RentCafe credential spike is the intended next action"
    expected: "The team has a plan to extract apiToken from RentCafe building HTML/JS pages and replace the _fetch_units() stub"
    why_human: "Cannot determine from codebase whether a spike was done out-of-band and not documented, or whether it is genuinely pending"
---

# Phase 2: Scrapers Verification Report

**Phase Goal:** All ~400 buildings are covered by working scraper modules across three tiers — Tier 1 REST APIs, Tier 2 platform HTML scrapers, and Tier 3 LLM fallback — with each module validated against real data and normalized output confirmed.
**Verified:** 2026-02-18
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running any individual scraper module against its target buildings produces normalized unit records in the database | PARTIAL | PPM/Funnel/AppFolio/Bozzuto/RealPage/Groupfox/LLM scrapers have functional scrape() → list[dict] → save_scrape_result() → normalize() → DB pipeline. RentCafe raises NotImplementedError — cannot produce records. |
| 2 | A building whose scrape returns zero units or an HTTP error is marked stale and retains its previous unit records | VERIFIED | save_scrape_result() with scrape_succeeded=False retains units (no delete) and sets last_scrape_status='failed'. 26 behavioral tests confirm all paths including unit retention on failure. |
| 3 | The Yardi/RentCafe scraper has a confirmed access method documented before any Yardi scraper code is merged | FAILED | RESEARCH.md explicitly says credential extraction "must be confirmed via a spike task" — the access method was NOT confirmed before rentcafe.py was merged. The stub was intentionally committed with an open spike. |
| 4 | The LLM fallback scraper has been benchmarked against at least 5 representative long-tail sites and the per-site token cost confirms the monthly projection is within 20% of $120 | VERIFIED | 02-LLM-BENCHMARK.md: 5 sites, $8.51/month projection (93% below $120 target). Human-verify checkpoint passed. At least one Entrata building included. |
| 5 | A post-scrape audit query run after each tier's scrapers confirms zero units in the database carry non-canonical bed type values | FAILED | non_canonical field exists on Unit model and normalizer sets it correctly, but no audit query was run or documented in any Phase 2 SUMMARY. No audit script exists. |

**Score: 3/5 success criteria verified** (1 partial, 2 failed)

---

## Required Artifacts

### Tier 1 Scrapers

| Artifact | Status | Details |
|----------|--------|---------|
| `src/moxie/scrapers/base.py` | VERIFIED | ScraperProtocol, save_scrape_result(), CONSECUTIVE_ZERO_THRESHOLD=5. Imports from normalizer.py (line 11). Calls normalize() inside save_scrape_result() (line 55). Calls building.consecutive_zero_count (lines 57, 60). Full implementation, 79 lines. |
| `src/moxie/scrapers/platform_detect.py` | VERIFIED | detect_platform() functional. 9 PLATFORM_PATTERNS covering 8 known platforms. Returns None for unknown. 61 lines. |
| `src/moxie/scrapers/tier1/rentcafe.py` | STUB | _fetch_units() always raises NotImplementedError. scrape() structure complete; credential guard and Error:1020 guard work. But cannot produce unit records for any building. |
| `src/moxie/scrapers/tier1/ppm.py` | VERIFIED | AsyncWebCrawler + BeautifulSoup. Case-insensitive partial name matching. 102 lines, substantive. |
| `alembic/versions/3522f8b6e283_add_consecutive_zero_count.py` | VERIFIED | Migration file exists, consistent with Building model field. |
| `src/moxie/db/models.py` | VERIFIED | consecutive_zero_count: Mapped[int] with server_default="0". non_canonical: Mapped[bool] on Unit. |

### Tier 2 Scrapers

| Artifact | Status | Details |
|----------|--------|---------|
| `src/moxie/scrapers/tier2/funnel.py` | VERIFIED | httpx + BeautifulSoup. HTTP error raises FunnelScraperError. CSS selectors documented as requiring real-page verification (expected per plan). 101 lines. |
| `src/moxie/scrapers/tier2/appfolio.py` | VERIFIED | httpx + BeautifulSoup. AppFolioScraperError on non-2xx. 107 lines. |
| `src/moxie/scrapers/tier2/bozzuto.py` | VERIFIED | httpx + BeautifulSoup. Bot-detection statuses (403/429/503) raise BozzutoScraperError with Crawl4AI upgrade note. 198 lines. |
| `src/moxie/scrapers/tier2/realpage.py` | VERIFIED | Crawl4AI AsyncWebCrawler for JS rendering. RealPageScraperError on empty HTML. 165 lines. |
| `src/moxie/scrapers/tier2/groupfox.py` | VERIFIED | Crawl4AI for bot bypass. _normalize_floorplans_url() appends /floorplans. GroupfoxScraperError on empty HTML. 317 lines. |

### Tier 3 Scraper

| Artifact | Status | Details |
|----------|--------|---------|
| `src/moxie/scrapers/tier3/llm.py` | VERIFIED | Crawl4AI LLMExtractionStrategy with claude-3-haiku-20240307. ANTHROPIC_API_KEY read from os.environ (line 74). Malformed JSON returns [] (lines 101-103). Non-list JSON returns [] (lines 105-107). All 7 required fields in _UnitRecord schema. 130 lines. |

### Supporting Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `src/moxie/sync/sheets.py` | VERIFIED | detect_platform() imported (line 22) and called after flush (line 145). Fills blanks only — existing non-null platform values not overwritten (filter on Building.platform.is_(None)). |
| `scripts/llm_benchmark.py` | VERIFIED | Imports llm.scrape() (line 71). Queries platform='llm' buildings from live DB. Estimates cost and writes 02-LLM-BENCHMARK.md. 184 lines. |
| `.planning/phases/02-scrapers/02-LLM-BENCHMARK.md` | VERIFIED | 5 sites tested. $8.51/month projection. PASS status on both target rows. Entrata building included. |

### Tests

| Artifact | Status | Lines | Details |
|----------|--------|-------|---------|
| `tests/test_platform_detect.py` | VERIFIED | 40+ | Imports from moxie.scrapers.platform_detect (confirmed). |
| `tests/test_save_scrape_result.py` | VERIFIED | 400 | All 4 paths: success+units, success+zero, threshold, failure. In-memory SQLite. Real normalize() used. |
| `tests/test_scraper_rentcafe.py` | VERIFIED | 30+ | Credential error, Error:1020 guard, NotImplementedError stub. |
| `tests/test_scraper_ppm.py` | VERIFIED | 30+ | Pure parsing and matching logic, monkeypatched _fetch_all_ppm_units. |
| `tests/test_scraper_funnel.py` | VERIFIED | 30+ | Static HTML fixture, pytest-httpx mocks. |
| `tests/test_scraper_appfolio.py` | VERIFIED | 25+ | Same pattern as funnel. |
| `tests/test_scraper_bozzuto.py` | VERIFIED | 25+ | Bot detection 403 test, generic 500 test. |
| `tests/test_scraper_realpage.py` | VERIFIED | 25+ | Empty HTML raises RealPageScraperError. |
| `tests/test_scraper_groupfox.py` | VERIFIED | 30+ | URL normalization tests, Crawl4AI monkeypatched. |
| `tests/test_scraper_llm.py` | VERIFIED | 238 | EnvironmentError on missing key, malformed JSON → [], non-list JSON → [], field filtering. AsyncWebCrawler mocked. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scrapers/base.py` | `moxie/normalizer.py` | `from moxie.normalizer import normalize` | WIRED | Line 11 import confirmed. normalize() called line 55 inside save_scrape_result(). |
| `scrapers/base.py` | `db/models.py` | `building.consecutive_zero_count` | WIRED | Lines 57, 60 access confirmed. |
| `sync/sheets.py` | `scrapers/platform_detect.py` | `from moxie.scrapers.platform_detect import detect_platform` | WIRED | Line 22 import confirmed. Line 145 call inside sheets_sync() confirmed. |
| `scrapers/tier1/rentcafe.py` | `db/models.py` | `building.rentcafe_property_id / rentcafe_api_token` | WIRED | Lines 95, 103, 104 access confirmed. |
| `scrapers/tier1/ppm.py` | `crawl4ai` | `AsyncWebCrawler` | WIRED | Line 18 import, line 36 async usage inside _fetch_ppm_html() confirmed. |
| `scrapers/tier2/funnel.py` | `httpx` | `httpx.Client.get()` | WIRED | Line 36 confirmed. |
| `scrapers/tier2/appfolio.py` | `httpx` | `httpx.Client.get()` | WIRED | Line 258 confirmed. |
| `scrapers/tier2/realpage.py` | `crawl4ai` | `AsyncWebCrawler` | WIRED | Line 109 confirmed. |
| `scrapers/tier2/groupfox.py` | `crawl4ai` | `AsyncWebCrawler` | WIRED | Line 258 confirmed. |
| `scrapers/tier3/llm.py` | `crawl4ai` | `LLMExtractionStrategy` | WIRED | Line 32 import, line 81 usage inside _scrape_with_llm() confirmed. |
| `scrapers/tier3/llm.py` | `ANTHROPIC_API_KEY` | `os.environ.get("ANTHROPIC_API_KEY")` | WIRED | Line 74 confirmed. Not hardcoded. |
| `scripts/llm_benchmark.py` | `scrapers/tier3/llm.py` | `from moxie.scrapers.tier3 import llm as llm_scraper` | WIRED | Line 71 import, line 73 scrape() call confirmed. |
| `02-LLM-BENCHMARK.md` | `scripts/llm_benchmark.py` | Results produced by running the script | WIRED | BENCHMARK.md header references llm_benchmark.py; content matches script output format. |

---

## Requirements Coverage

| Requirement | Description | Plans | Status | Evidence |
|-------------|-------------|-------|--------|---------|
| INFRA-03 | On scrape failure, last known unit data is retained; building marked stale | 02-01, 02-02 | SATISFIED | save_scrape_result(scrape_succeeded=False) retains units, sets last_scrape_status='failed'. 26 behavioral tests confirm. |
| SCRAP-01 | Yardi/RentCafe buildings scraped via API | 02-04 | PARTIAL | rentcafe.py exists with credential guard and Error:1020 guard. _fetch_units() is a confirmed stub — NotImplementedError. API call not implemented. |
| SCRAP-02 | Entrata buildings scraped | 02-08 | SATISFIED (via re-routing) | CONTEXT.md decision: Entrata routed to platform='llm'. LLM scraper covers ~30-40 Entrata buildings. Benchmark confirmed at least one Entrata building processed. REQUIREMENTS.md marks SCRAP-02 complete (re-routing decision accepted). |
| SCRAP-03 | PPM buildings via ppmapartments.com/availability | 02-04 | SATISFIED | ppm.py functional: Crawl4AI renders JS, BeautifulSoup parses table, case-insensitive partial name matching covers all 18 PPM buildings. |
| SCRAP-04 | Funnel/Nestio buildings scraped | 02-05 | SATISFIED | funnel.py functional: httpx + BeautifulSoup. CSS selectors heuristic (documented as requiring real-page verification). |
| SCRAP-05 | RealPage/G5 buildings scraped | 02-07 | SATISFIED | realpage.py functional: Crawl4AI AsyncWebCrawler + BeautifulSoup. Error on empty HTML. |
| SCRAP-06 | Bozzuto buildings scraped | 02-06 | SATISFIED | bozzuto.py functional: httpx + BeautifulSoup, bot-detection guard with Crawl4AI upgrade path. |
| SCRAP-07 | Groupfox buildings via /floorplans | 02-07 | SATISFIED | groupfox.py functional: URL normalization to /floorplans, Crawl4AI for 403 bypass. |
| SCRAP-08 | AppFolio buildings scraped | 02-05 | SATISFIED | appfolio.py functional: httpx + BeautifulSoup. |
| SCRAP-09 | Long-tail custom sites via Crawl4AI + Claude Haiku | 02-08, 02-09 | SATISFIED | llm.py functional with LLMExtractionStrategy. Benchmark: 5 sites, $8.51/month, PASS. Human-verify checkpoint passed. |

---

## Anti-Pattern Scan

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src/moxie/scrapers/tier1/rentcafe.py` line 49 | `raise NotImplementedError(...)` inside `_fetch_units()` | Blocker (for SC1, SC3) | RentCafe covers ~220 buildings (55% of total). No unit records can be produced for any RentCafe building until this stub is replaced. This is an intentional, documented stub — but it prevents the phase goal of "all ~400 buildings covered by working scraper modules" from being fully achieved. |
| `src/moxie/scrapers/tier2/funnel.py` | "SELECTOR VERIFICATION REQUIRED" comment in _parse_html() | Warning | CSS selectors are heuristic. Parser will return empty list on real Funnel pages if selectors don't match. Requires manual verification against a live Funnel URL before production use. Same warning applies to appfolio.py, bozzuto.py, realpage.py, groupfox.py. |
| `.planning/phases/02-scrapers/02-LLM-BENCHMARK.md` | "Token counts are estimated from output JSON length" | Info | Token cost projection uses estimated (not actual) token counts. The 10K input token assumption is not validated against real API usage headers. Cost could be 2-3x higher if pages are larger. Still passes $144 band even at 10x estimate error. |

---

## Human Verification Required

### 1. RentCafe Credential Spike Status

**Test:** Confirm whether the RentCafe credential spike was attempted out-of-band (not in a Phase 2 plan) or is genuinely pending.
**Expected:** Team has a plan to: (1) fetch 2-3 known RentCafe building URLs from the DB, (2) inspect HTML/JS for companyCode/propertyCode/apiToken, (3) hit `api.rentcafe.com/rentcafeapi.aspx` with requestType=apartmentavailability, (4) document exact field names.
**Why human:** Cannot determine from codebase whether a spike was done and undocumented or is still pending.

### 2. Real Funnel/AppFolio/Bozzuto/RealPage/Groupfox scraper validation

**Test:** Run each Tier 2 scraper against one real building URL from the live DB for its platform. Check whether units_found > 0.
**Expected:** At least 1 unit returned per platform (confirms CSS selectors match real page structure).
**Why human:** CSS selectors in all 5 Tier 2 scrapers are documented as heuristic and unverified against real pages. Automated check cannot confirm the selectors work without live HTTP calls.

### 3. Post-scrape bed type audit

**Test:** After running scrapers: `sqlite3 moxie.db "SELECT COUNT(*) FROM units WHERE non_canonical = 1;"`
**Expected:** 0 rows (all bed types normalized to canonical values).
**Why human:** No audit script exists. Query must be run against live DB after actual scrapes have populated units.

---

## Gaps Summary

Three gaps prevent full goal achievement:

**Gap 1 (SC1 + SC3): RentCafe stub not replaced.** The RentCafe scraper covers ~220 buildings (55% of total). `_fetch_units()` in `src/moxie/scrapers/tier1/rentcafe.py` always raises `NotImplementedError`. This was an intentional design choice — the plan documents that credentials must be confirmed via a spike before the real API call can be written. The spike has not been completed. Until `_fetch_units()` is replaced with a real `httpx` call using confirmed credentials, 55% of the building portfolio cannot be scraped. SC1 requires "running any individual scraper module against its target buildings produces normalized unit records" — this is false for RentCafe.

**Gap 2 (SC3): Confirmed access method pre-merge criterion not met.** SC3 requires "confirmed access method documented before any Yardi scraper code is merged — not assumed, confirmed." The RESEARCH.md explicitly states the RentCafe credential extraction pattern requires a spike investigation. The stub was merged before that confirmation. The credential access method (extracting apiToken/companyCode from building page JavaScript) is documented as a hypothesis, not a confirmed finding with a working proof.

**Gap 3 (SC5): Post-scrape bed type audit not performed.** SC5 requires "a post-scrape audit query run after each tier's scrapers confirms zero units in the database carry non-canonical bed type values." The `non_canonical` field exists on the Unit model and `normalizer.py` sets it correctly. However, no SUMMARY or PLAN documents that this audit query was run against the live database. No audit script exists in the codebase. The mechanism is in place; the required verification step was skipped.

**What is working well:** The scraper infrastructure (save_scrape_result, detect_platform, consecutive_zero_count), all Tier 2 platform scrapers (5 platforms), the Tier 3 LLM scraper, the sheets_sync platform detection integration, the benchmark script and cost projection, and the behavioral test suite are all substantive and properly wired. The failure-retention behavior (SC2) is fully verified. The LLM cost benchmark (SC4) is verified.

---

_Verified: 2026-02-18_
_Verifier: Claude (gsd-verifier)_
