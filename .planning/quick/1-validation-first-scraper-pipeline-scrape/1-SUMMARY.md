---
phase: quick-1
plan: 1
status: partial
commits: [443b7e6, 2ee0ae0]
---

## What Was Done

### Task 1: validate-building CLI + push_availability module (COMPLETE)
- Created `src/moxie/sync/push_availability.py` with `push_availability()` function and `main()` CLI
- Registered `validate-building` command in pyproject.toml
- Supports `--building`, `--save`, `--no-save`, `--sheet-only`, `--platform` flags
- Writes to "Availability" tab in Google Sheet (creates if missing)
- Commit: 443b7e6

### Bug fixes discovered during validation (COMPLETE)
- **PPM scraper**: Site redesigned from table layout to div.unit card layout. Rewrote `_parse_ppm_html()` for new DOM structure. Added punctuation-insensitive name matching (`_normalize_name`).
- **RentCafe scraper**: Stored tokens have `%3d` URL encoding. Added `unquote()` before passing to httpx to prevent double-encoding (`%253d`).
- **Normalizer**: Added PPM bed type aliases: "1 Bedroom/1Bath" -> "1BR", "Jr One Bedroom/1 Bath" -> "Convertible", "2 Bedroom/2 Bath" -> "2BR", etc.
- **validate-building**: Added `--platform` override flag for forcing scraper selection.
- Updated PPM tests for new card-based DOM. 253 tests passing.
- Commit: 2ee0ae0

### Task 2: End-to-end validation on one building (PARTIAL)
- **100 W Chestnut (PPM)**: 23 units scraped, saved to DB, pushed to Availability tab. All bed types normalized (0 non-canonical).
- **Reside on Barry (RentCafe)**: VoyagerPropertyCode extracted successfully (`resideonbarry`). API call returns 406 — marketing API token is incompatible with availability API. LLM fallback also returns 0 units (RentCafe sites load data via JS widget, not in HTML).
- **Awaiting user validation** of the Availability tab data for 100 W Chestnut.

## Key Discovery

**RentCafe marketing API token != availability API token.** The `PropertyAPIKey` from `marketingapi.rentcafe.com` does not work as the `apiToken` for `api.rentcafe.com/rentcafeapi.aspx`. The 35 Reside tokens in the DB are marketing API keys, not availability API keys. This affects the credential extraction strategy for 237 RentCafe buildings.

## What's Left

- User validates 100 W Chestnut data in Google Sheet
- Investigate correct RentCafe apiToken source (may need different extraction approach)
- Validate more buildings across other platforms (funnel, appfolio, bozzuto, etc.)
