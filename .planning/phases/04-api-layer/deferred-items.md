# Deferred Items — Phase 04

## Pre-existing Test Failures (discovered during 04-03)

These failures existed before 04-03 work and are out of scope for this plan.

### 1. tests/test_scraper_appfolio.py — ImportError

`_parse_html` and `_fetch_html` functions were removed when the AppFolio scraper was
rewritten in commit `9872665` (quick-5). The old test expects the original function
signatures which no longer exist.

**Fix needed:** Update `tests/test_scraper_appfolio.py` to match the new Sedgwick
scraper API (direct listings page approach).

### 2. tests/test_scraper_llm.py — 7 failures

The LLM scraper was updated in quick-5 to use Crawl4AI for subpage probing
(`_find_availability_link`). The FakeResult mock objects used in tests don't have
a `success` attribute, which the updated code now checks.

**Fix needed:** Add `success=True` and `status_code=200` attributes to FakeResult
in `tests/test_scraper_llm.py`.
