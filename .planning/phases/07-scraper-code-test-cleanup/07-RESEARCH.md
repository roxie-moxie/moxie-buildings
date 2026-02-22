# Phase 7: Scraper Code & Test Cleanup - Research

**Researched:** 2026-02-22
**Domain:** Python test maintenance, dead code removal, pytest configuration
**Confidence:** HIGH — all findings verified by direct code inspection and live test run

## Summary

Phase 7 is a cleanup phase with three discrete tasks: remove the orphaned `tier1/rentcafe.py` scraper
and its test file, fix broken tests in `test_scraper_llm.py` and `test_scraper_appfolio.py`, and add
`"sightmap"` to `KNOWN_PLATFORMS` in `platform_detect.py`. All findings come from direct inspection
of the codebase and a live `pytest` run — no external library research needed.

The current state: running `pytest tests/` without ignore flags produces **1 collection error** and
**7 test failures** (8 total broken items). The broken tests are in `test_scraper_appfolio.py` (import
error — test imports symbols that were renamed when appfolio.py was rewritten) and `test_scraper_llm.py`
(FakeResult mock missing `.success` attribute — `_probe_subpage` was updated to check `result.success`
after the test was written). The tier1 `rentcafe.py` and its 14 tests all currently pass but are dead
code: `registry.py` maps `"rentcafe"` to `securecafe`, not `tier1/rentcafe`.

**Primary recommendation:** Delete `tier1/rentcafe.py` and `test_scraper_rentcafe.py`, fix the two
broken test files, then add `"sightmap"` to `KNOWN_PLATFORMS`. After those four changes `pytest tests/`
runs clean with no ignore flags.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCRAP-01 | Yardi/RentCafe buildings scraped via API — spike completed, superseded by SecureCafe HTML approach. Phase 7 formally closes by deleting the orphaned tier1 stub and its tests. | tier1/rentcafe.py confirmed dead (not in registry); SecureCafe confirmed as sole rentcafe implementation; test file confirmed all-passing but testing dead code. |
</phase_requirements>

---

## Exact Current State (verified by live test run 2026-02-22)

### Test run baseline

```
pytest tests/                         # 1 collection error + 7 failures
pytest tests/ --ignore=tests/test_scraper_appfolio.py   # 7 failures
pytest tests/ --ignore=tests/test_scraper_appfolio.py --ignore=tests/test_scraper_llm.py  # all pass
```

292 tests collected when ignoring appfolio; 285 pass, 7 fail.
The 71 tests from phase 6 are the API + runner + save_scrape_result tests — all still passing.

---

## Broken Item 1: test_scraper_appfolio.py — Collection Error (ImportError)

**File:** `tests/test_scraper_appfolio.py`
**Error:** `ImportError: cannot import name '_parse_html' from 'moxie.scrapers.tier2.appfolio'`

**Root cause:** The test was written for a generic HTML-scraping appfolio.py with `_parse_html(html)` and
`_fetch_html(url)` as public-ish helpers. During phase 2 work (quick task #5, 2026-02-20), `appfolio.py`
was rewritten from scratch with Sedgwick-specific logic:
- Old API: `_parse_html(html)` — generic HTML parser
- New API: `_parse_listings_html(html, address_filter=None)` — AppFolio listings-specific parser

The test file still imports `_parse_html` (old name) — hence ImportError at collection time.

**What the test expects vs. what exists:**

| Symbol test imports | Current appfolio.py | Status |
|--------------------|--------------------|---------|
| `_parse_html` | renamed to `_parse_listings_html` | BROKEN |
| `_fetch_html` | still exists, same signature | OK |
| `AppFolioScraperError` | still exists | OK |

The test HTML fixtures also use `class="listing-item"` containers and `class="bedroom-count"`,
`class="price"`, `class="available-date"`, `class="unit-number"` selectors — but `_parse_listings_html`
actually uses `.js-listing-item` containers and `detail-box__value`, `js-listing-available` selectors
from real AppFolio HTML.

**Two valid fix approaches:**

**Option A — Update tests to match current implementation:**
- Rename import `_parse_html` → `_parse_listings_html`
- Update HTML fixtures to use real AppFolio selectors (`.js-listing-item`, `.detail-box__value`, etc.)
- This makes the tests validate actual behavior

**Option B — Delete the test file:**
- The appfolio scraper (Sedgwick buildings) is validated in production; unit tests for it use the wrong
  HTML structure anyway and would not catch real regressions against actual AppFolio HTML

**Recommendation: Option A** — fix imports and update fixtures. The test covers useful ground (HTTP error
handling via `_fetch_html`, parse logic). Deleting it reduces coverage on a working scraper.

**Exact fix needed:**
1. Change import `_parse_html` → `_parse_listings_html` (line 8)
2. Update `SAMPLE_HTML`, `MULTI_UNIT_HTML`, `INCOMPLETE_HTML`, `NO_UNITS_HTML` fixtures to use AppFolio
   real selectors: container `.js-listing-item`, price via `.detail-box__value` with `$`, bed/bath
   `.detail-box__value` with `bd`/`ba`, availability `.js-listing-available`, unit number from `img[alt]`
3. Update all `TestParseHtml` test assertions to match new fixture field values

---

## Broken Item 2: test_scraper_llm.py — 7 Failures (AttributeError)

**File:** `tests/test_scraper_llm.py`
**Error:** `AttributeError: 'FakeResult' object has no attribute 'success'`

**Root cause:** The `_make_fake_crawler_ctx()` helper (lines 50-75) creates a `FakeResult` class that
only sets `.extracted_content`, `.links`, and `.html`. After the test was written, `_probe_subpage()` in
`llm.py` was updated (phase 2 work) to check `result.success` before checking `result.status_code`:

```python
# llm.py line 165 — what the code NOW checks:
if not result.success or result.status_code not in (200, 301, 302):
    return False
```

The `FakeResult` mock sets neither `.success` nor `.status_code`, so `result.success` raises
`AttributeError`.

**Which tests fail:** All 7 tests that call `asyncio.run(_scrape_with_llm(...))` and patch
`AsyncWebCrawler`. These tests are trying to test Pass 2 (LLM extraction) but the mock gets called
during Pass 1 (`_find_availability_link` → `_probe_subpage`) and crashes there.

**All 7 failing tests:**
- `test_scrape_with_llm_returns_empty_on_malformed_json`
- `test_scrape_with_llm_returns_empty_on_null_content`
- `test_scrape_with_llm_returns_empty_on_dict_json`
- `test_scrape_filters_incomplete_records`
- `test_unit_number_field_required`
- `test_bed_type_field_required`
- `test_scrape_with_llm_filters_and_returns_valid_records`

**Exact fix needed:** Update `FakeResult` in `_make_fake_crawler_ctx()` to also set `.success = True`
and `.status_code = 200`. Then `_probe_subpage` can proceed. However, we also need `_probe_subpage` to
return `False` (so Pass 1 falls back to original URL) — looking at `_probe_subpage` logic:

```python
content_lower = (result.markdown or "").lower()
return any(kw in content_lower for kw in _CONTENT_KEYWORDS)
```

The `FakeResult` doesn't set `.markdown`, so `result.markdown` will raise `AttributeError` too.
The fix requires: `.success = True`, `.status_code = 200`, `.markdown = ""` (empty → no content
keywords match → `_probe_subpage` returns False → Pass 1 falls through → uses original URL → Pass 2
proceeds with `extracted_content`).

**Complete `FakeResult` attributes needed:**
```python
result.extracted_content = extracted_content   # already set
result.links = {}                              # already set
result.html = ""                               # already set
result.success = True                          # MISSING — causes AttributeError
result.status_code = 200                       # MISSING — used after .success check
result.markdown = ""                           # MISSING — used in _probe_subpage content check
```

Note: the mock is called for ALL crawler.arun() calls (both Pass 1 subpage probes AND Pass 2
extraction). With `.success = True`, `.status_code = 200`, `.markdown = ""`, `_probe_subpage` will
return `False` (no content keywords in empty markdown), so all explicit subpages return False, causing
Pass 1 to fall through to link scoring. Since `result.links = {}`, link scoring finds no links and
returns `None`. `_find_availability_link` returns `None`, so `target_url = url` (original URL). Pass 2
then calls `crawler.arun` again and gets `extracted_content` from the mock — which is what the tests
intend to test.

---

## Broken Item 3: Orphaned tier1/rentcafe.py and Its Tests

**File:** `src/moxie/scrapers/tier1/rentcafe.py`
**Test file:** `tests/test_scraper_rentcafe.py`

**Status:** Both files are functional and all 14 tests pass. But this is dead code.

**Why it's orphaned:**
- `registry.py` maps `"rentcafe"` → `"moxie.scrapers.tier2.securecafe"` (not tier1)
- No other file imports from `moxie.scrapers.tier1.rentcafe`
- The RentCafe API credential approach was abandoned in favor of SecureCafe HTML scraping

**Verification that nothing imports it:**

Grep results confirm: `tier1/rentcafe.py` is imported only by `test_scraper_rentcafe.py`. No production
code references it. The `tier1/__init__.py` is empty.

**What SCRAP-01 says today vs. what it was:**
- Original: "RentCafe/Yardi ~220 buildings scraped via API — spike investigation required"
- Phase 7 closure: the spike found the API requires per-building credentials (VoyagerPropertyCode +
  apiToken) that are not centrally discoverable. SecureCafe HTML approach was adopted instead (no
  credentials needed). SCRAP-01 is "closed" by accepting SecureCafe as the implementation.

**Safe to delete:** `tier1/rentcafe.py` and `tests/test_scraper_rentcafe.py`. The `tier1/` directory
will still contain `ppm.py` and `__init__.py` — it is not emptied.

---

## Broken Item 4: sightmap Missing from KNOWN_PLATFORMS

**File:** `src/moxie/scrapers/platform_detect.py`

**Current state:**
```python
KNOWN_PLATFORMS: frozenset[str] = frozenset({
    "rentcafe", "ppm", "entrata", "mri", "funnel", "realpage", "bozzuto", "groupfox", "appfolio", "llm"
})
```

`"sightmap"` is absent from `KNOWN_PLATFORMS` but IS present in:
- `PLATFORM_PATTERNS` (line 22-36) — so URL detection works for sightmap URLs
- `registry.py` PLATFORM_SCRAPERS — the scraper dispatches correctly
- The DB: 58 buildings classified as `platform='sightmap'`

**Where KNOWN_PLATFORMS is used:** Downstream validation code (the `validate-building` workflow and any
code checking `if building.platform in KNOWN_PLATFORMS`) will fail to recognize sightmap buildings as
having a known platform. This is a silent bug — buildings get classified correctly but validation tools
may route them incorrectly.

The test `test_platform_detect.py` does NOT test `KNOWN_PLATFORMS` directly — it only tests
`detect_platform()` return values. Adding `"sightmap"` to `KNOWN_PLATFORMS` will not break any existing
tests.

**Fix:** Add `"sightmap"` to the frozenset.

---

## Standard Stack

No new libraries needed. This phase uses only what already exists in the project:

| Tool | Already in project | Purpose in this phase |
|------|-------------------|-----------------------|
| pytest | Yes | Run the test suite |
| pytest-httpx | Yes | Mock httpx in appfolio tests |
| BeautifulSoup4 | Yes | Real appfolio HTML fixture parsing |
| Python builtins | Yes | Delete files |

---

## Architecture Patterns

### Pattern 1: Test-Implementation Alignment

When an implementation is rewritten (appfolio.py was fully replaced), the corresponding test must be
updated in lockstep. The mismatch here is a classic "test drift" — implementation evolved, tests didn't.

**Pattern for fixing:** Update test imports and fixtures to match current implementation API, not the
original placeholder API.

### Pattern 2: Mock Completeness

When mocking a complex object (Crawl4AI `CrawlResult`), the mock must set ALL attributes that the
production code accesses — not just the ones the test author remembered. The `FakeResult` was
incomplete: it set `.extracted_content`, `.links`, `.html` but missed `.success`, `.status_code`,
`.markdown`.

**Pattern for fixing:** Read the production code path end-to-end from the entry point being tested, note
every attribute accessed on the mock object, and add them all to the mock.

### Pattern 3: Dead Code Removal

Removing `tier1/rentcafe.py` is safe because:
1. No production import references it (verified by grep)
2. registry.py already routes `rentcafe` to securecafe
3. The tests that cover it are also being removed

The `tier1/` directory stays (PPM scraper lives there).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML fixtures for AppFolio tests | Generate HTML programmatically | Use string literals matching real AppFolio selectors | Simpler, directly documents expected HTML structure |
| Mock Crawl4AI result | Write elaborate MagicMock with spec= | Add the 3 missing attributes to FakeResult | Minimal change, preserves existing test intent |

---

## Common Pitfalls

### Pitfall 1: Incomplete Mock Attributes
**What goes wrong:** Mock object raises AttributeError when production code path accesses an attribute
the mock doesn't define.
**Why it happens:** Test author followed the happy-path but production code added new attribute checks
after the test was written.
**How to avoid:** Add `.success = True`, `.status_code = 200`, `.markdown = ""` to `FakeResult`.
**Warning sign:** AttributeError mentioning `FakeResult` — exactly what we see.

### Pitfall 2: Importing Renamed Functions
**What goes wrong:** ImportError at collection time crashes the entire test session.
**Why it happens:** `_parse_html` was the name before appfolio.py was rewritten; new name is
`_parse_listings_html`.
**How to avoid:** Fix the import line and update all call sites in the test.
**Warning sign:** pytest says "1 error during collection" and reports ImportError.

### Pitfall 3: Over-Deleting AppFolio Test
**What goes wrong:** Deleting `test_scraper_appfolio.py` entirely removes coverage for a working
scraper.
**Why it's tempting:** The test is broken and needs substantial fixture rewriting.
**How to avoid:** Fix the test rather than delete it. The `_fetch_html` tests (TestFetchHtml class) can
be salvaged with minimal changes since `_fetch_html` signature is unchanged. Only `TestParseHtml`
needs fixture updates.

### Pitfall 4: Breaking the rentcafe Tests Before Deleting Them
**What goes wrong:** Modifying `tier1/rentcafe.py` (e.g., stripping it out gradually) breaks the tests
before they're deleted.
**How to avoid:** Delete both files in one commit. No partial removal.

---

## Code Examples

### Fix 1: FakeResult in test_scraper_llm.py

Current broken version:
```python
class FakeResult:
    pass

result = FakeResult()
result.extracted_content = extracted_content
result.links = {}
result.html = ""
```

Fixed version:
```python
class FakeResult:
    pass

result = FakeResult()
result.extracted_content = extracted_content
result.links = {}
result.html = ""
result.success = True          # _probe_subpage checks this
result.status_code = 200       # _probe_subpage checks this after .success
result.markdown = ""           # _probe_subpage checks this for content keywords
```

### Fix 2: KNOWN_PLATFORMS in platform_detect.py

Current (missing sightmap):
```python
KNOWN_PLATFORMS: frozenset[str] = frozenset({
    "rentcafe", "ppm", "entrata", "mri", "funnel", "realpage", "bozzuto", "groupfox", "appfolio", "llm"
})
```

Fixed:
```python
KNOWN_PLATFORMS: frozenset[str] = frozenset({
    "rentcafe", "ppm", "entrata", "mri", "funnel", "realpage", "bozzuto", "groupfox", "appfolio",
    "sightmap", "llm"
})
```

### Fix 3: test_scraper_appfolio.py — import line

Current (broken):
```python
from moxie.scrapers.tier2.appfolio import _parse_html, _fetch_html, AppFolioScraperError
```

Fixed:
```python
from moxie.scrapers.tier2.appfolio import _parse_listings_html, _fetch_html, AppFolioScraperError
```

And ALL calls to `_parse_html(...)` in test body must become `_parse_listings_html(...)`.

### Fix 4: AppFolio test HTML fixtures — real AppFolio selectors

The tests use imagined selectors. The real ones (verified 2026-02-20 against sedgwickproperties.appfolio.com):
- Container: `.js-listing-item`
- Price: `.detail-box__value` containing `$`
- Bed/bath: `.detail-box__value` containing `bd` or `ba`
- Availability: `.js-listing-available`
- Unit number: `img[alt]` attribute containing "Unit NNN"

Example fixture that will actually parse:
```python
SAMPLE_HTML = """
<div class="js-listing-item">
  <img alt="1325 N Wells Ave , Unit 3B, Chicago, IL 60610" />
  <div class="detail-box__value">$2,500</div>
  <div class="detail-box__value">2 bd / 1 ba</div>
  <div class="js-listing-available">April 1, 2026</div>
</div>
"""
```

---

## File-by-File Change Plan

| File | Action | Detail |
|------|--------|--------|
| `src/moxie/scrapers/tier1/rentcafe.py` | **DELETE** | Dead code — SecureCafe is sole rentcafe impl |
| `tests/test_scraper_rentcafe.py` | **DELETE** | Tests for dead code |
| `tests/test_scraper_appfolio.py` | **EDIT** | Fix import, update fixtures/assertions |
| `tests/test_scraper_llm.py` | **EDIT** | Add 3 missing attrs to FakeResult |
| `src/moxie/scrapers/platform_detect.py` | **EDIT** | Add "sightmap" to KNOWN_PLATFORMS |

**No changes needed to:**
- `registry.py` — already correct (sightmap present, rentcafe → securecafe)
- `src/moxie/scrapers/tier2/appfolio.py` — production code is correct
- `src/moxie/scrapers/tier3/llm.py` — production code is correct, tests were stale
- `src/moxie/scrapers/tier1/ppm.py` — unaffected
- `src/moxie/scrapers/tier1/__init__.py` — stays in place

---

## Expected Outcome After Changes

```
pytest tests/    # no --ignore flags
# Result: all N tests collected, all pass, 0 errors, 0 failures
```

Specific counts:
- `test_scraper_rentcafe.py` deleted: -14 tests
- `test_scraper_appfolio.py` fixed: ~12 tests collected and passing (net same count)
- `test_scraper_llm.py` fixed: +7 tests that were failing now pass
- `test_platform_detect.py` may grow by 1 test if a sightmap KNOWN_PLATFORMS test is added

---

## Open Questions

1. **Should a `test_detect_platform_known_platforms_contains_sightmap` test be added?**
   - What we know: `test_platform_detect.py` currently tests `detect_platform()` return values but NOT
     the `KNOWN_PLATFORMS` frozenset contents.
   - What's unclear: The success criteria says "sightmap is present in KNOWN_PLATFORMS" but doesn't
     specify whether a test for that membership is required.
   - Recommendation: Add a simple test — `assert "sightmap" in KNOWN_PLATFORMS` — in
     `test_platform_detect.py`. Makes the SC verifiable by pytest.

2. **How many AppFolio tests remain after fixing fixtures?**
   - What we know: `TestFetchHtml` class (5 tests) needs only import fix. `TestParseHtml` class (9
     tests) needs full fixture rewrite.
   - What's unclear: Whether all 9 `TestParseHtml` tests map cleanly to `_parse_listings_html` behavior.
   - Recommendation: Keep all 9 but rewrite fixtures. The behavior assertions (fallback unit_number,
     fallback availability_date, skip incomplete rows) are still valid for the new implementation.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/moxie/scrapers/tier1/rentcafe.py` — confirmed orphaned
- Direct code inspection: `src/moxie/scrapers/registry.py` — confirmed rentcafe → securecafe mapping
- Direct code inspection: `src/moxie/scrapers/platform_detect.py` — confirmed sightmap missing
- Direct code inspection: `src/moxie/scrapers/tier3/llm.py` line 165 — `.success` attribute access
- Direct code inspection: `tests/test_scraper_llm.py` — FakeResult missing attributes
- Direct code inspection: `tests/test_scraper_appfolio.py` — imports `_parse_html` (renamed)
- Live pytest run 2026-02-22 — confirmed exact failures and counts

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — decision history confirming SecureCafe replaced RentCafe API approach (2026-02-19)

---

## Metadata

**Confidence breakdown:**
- Which files to change: HIGH — verified by code inspection + live test run
- Exact fix for LLM tests: HIGH — root cause is clear (3 missing attrs), fix is mechanical
- Exact fix for AppFolio tests: HIGH for imports, MEDIUM for fixtures (real AppFolio selectors verified
  by STATE.md but not re-tested here)
- Pitfalls: HIGH — all derived from actual errors observed

**Research date:** 2026-02-22
**Valid until:** Until any of the 5 affected files are modified (stable — no external dependencies)
