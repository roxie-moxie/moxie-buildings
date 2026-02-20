# Deferred Items - Phase 03

## Pre-existing Test Failures (out of scope for 03-01)

### 1. test_scraper_appfolio.py - stale test for rewritten scraper
- **Discovered during:** Task 1 test verification
- **Issue:** `tests/test_scraper_appfolio.py` imports `_parse_html` from `moxie.scrapers.tier2.appfolio`, but the scraper was rewritten in session 5 (quick-5) to use `_parse_listings_html`. The test fixture HTML also uses old CSS selectors (`.listing-item`, `.bedroom-count`, `.price`) that don't match the new `.js-listing-item` / `.detail-box__value` selectors.
- **Status:** Pre-existing before this plan. Appfolio scraper rewrite happened in phase 02.
- **Action needed:** Update test to match new `_parse_listings_html` API and Sedgwick-style HTML fixture.

### 2. test_scraper_llm.py - FakeResult missing `success` attribute
- **Discovered during:** Task 1 test verification
- **Issue:** `tests/test_scraper_llm.py::test_scrape_with_llm_returns_empty_on_malformed_json` fails because `_probe_subpage()` was updated in session 5 to check `result.success` but the test's `FakeResult` mock object doesn't have this attribute.
- **Status:** Pre-existing before this plan. LLM scraper update happened in phase 02.
- **Action needed:** Add `success = True` and appropriate `status_code` to the `FakeResult` class in the test.
