# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Validation-first scraper pipeline — one building at a time, validate with user

## Current Position

Phase: 2 of 5 (Scrapers) — IN PROGRESS (gap closure)
Status: All 9 scraper plans built and passing tests. Post-verification gap work underway.
Last activity: 2026-02-19 - Completed quick task 1: validate-building CLI + PPM scraper fix + first building validated end-to-end (100 W Chestnut, 23 units)

Progress: [████████░░] 60%

---

## What's Done (this session)

### Scraper validation tooling
- `scrape` CLI command — spot-check any building by name or URL, prints unit table, optional `--save` flag
- Registered as `uv run scrape` in pyproject.toml

### LLM scraper improvements (from Fisher Building + AMLI 808 validation)
- Two-pass crawl: Pass 1 scans internal links for availability subpage (no LLM cost); Pass 2 runs extraction on the best URL found
- Strengthened extraction prompt: rejects floor plan names as unit_number, requires actual listed rent
- Stronger post-extraction filter: rejects placeholder rent values ("Call for pricing", "TBD", etc.)

### Platform classification workflow
- `sheets_sync` reads optional "Platform" column from sheet — sheet value wins over auto-detection
- Unknown URLs now get `needs_classification` sentinel instead of silently routing to `llm`
- `export-platforms` command (`uv run export-platforms`) — one-time bootstrap to seed DB platform values into the sheet's Platform column
- `scrape` CLI treats `needs_classification` as "fall through to LLM" for spot-checking (not an error)

### RentCafe credential spike (completed)
- Confirmed API endpoint and all field names from a live 338-unit response
- Endpoint: `api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability&VoyagerPropertyCode=CODE&apiToken=TOKEN&showallunit=1`
- Confirmed fields: `ApartmentName` (unit#), `Beds` (int), `MinimumRent` (formatted string), `AvailableDate` (M/D/YYYY or ""), `FloorplanName`, `Baths`, `SQFT`
- `companyCode` is NOT required — only VoyagerPropertyCode + apiToken
- Availability filter: `AvailableDate` non-empty = listed for rent

### RentCafe scraper — stub replaced
- `_fetch_units()` is now a real httpx call with confirmed parameters
- `_map_unit()` updated to confirmed field names
- `_is_available()` filter added — only units with non-empty AvailableDate returned
- 23 tests passing (credential validation, error guard, availability filter, full flow with httpx_mock)

### RentCafe credential extraction script
- `scripts/extract_rentcafe_credentials.py` — fetches each rentcafe.com building page via Crawl4AI, extracts VoyagerPropertyCode + apiToken from rendered HTML
- Targets buildings by URL pattern (`ILIKE '%rentcafe.com%'`) — works before platform column is filled
- Two extraction strategies: (1) parse rentcafeapi.aspx URLs from rendered HTML, (2) regex for JS variable patterns
- Flags: `--dry-run`, `--force`, `--building NAME`, `--concurrency N`
- MISS buildings get DevTools instructions for manual fallback

---

## What's In Progress / Not Done

### Operational setup (blocking full validation)
- `.env` file not created on this machine yet — needed for `sheets-sync` and all commands
- Google service account credentials JSON not set up — needed to read/write the sheet
- `sheets-sync` not yet run — DB has only 3 seed buildings, not the real ~400
- `export-platforms` not yet run — Platform column not seeded in sheet
- `extract_rentcafe_credentials.py` not yet run — no credentials in DB for any building

### Validation gaps (from Phase 2 verification report, score 3/5)
- SC1/SC3: RentCafe scraper stub is now replaced, but credentials still need to be extracted and populated before any RentCafe building can actually be scraped
- SC5: Post-scrape bed type audit not yet run (`SELECT COUNT(*) FROM units WHERE non_canonical = 1`)
- Tier 2 CSS selectors (Funnel, AppFolio, Bozzuto, RealPage, Groupfox) marked SELECTOR VERIFICATION REQUIRED — not validated against live pages yet

### LLM scraper validation (pending re-run)
- Fisher Building and AMLI 808 were validated and found failing (floor plan names, no rents, wrong page)
- LLM scraper was fixed (link-following + prompt) but not yet re-validated against real sites

---

## Next Steps (in order)

1. **Set up .env + Google credentials** (operational prerequisite for everything below)
2. **Run `sheets-sync`** — populate DB with real ~400 buildings
3. **Run `export-platforms`** — seed Platform column in sheet from DB
4. **Run `extract_rentcafe_credentials.py`** — auto-extract VoyagerPropertyCode + apiToken for all rentcafe.com buildings
5. **Re-validate Fisher Building + AMLI 808** with `uv run scrape` — confirm LLM link-following fix works
6. **Alex reviews Platform column** — corrects `needs_classification` buildings in sheet
7. **Run bed type audit** — `SELECT COUNT(*) FROM units WHERE non_canonical = 1` (close SC5)
8. **Phase 3: Scheduler** — daily batch runner, APScheduler, per-platform concurrency limits

---

## Key Decisions (this session)

- [2026-02-18]: Sheet-wins platform model — Platform column in Google Sheet is the canonical override; auto-detection fills blanks only; sheet value propagates to DB on every sync
- [2026-02-18]: `needs_classification` sentinel replaces silent `llm` fallback — unrecognized URLs are flagged for Alex to review rather than silently routed to LLM tier
- [2026-02-18]: RentCafe credential spike confirmed — `VoyagerPropertyCode` + `apiToken` only (no `companyCode`); `ApartmentName` is the unit number field (not `UnitNumber`); `AvailableDate` non-empty is the availability filter
- [2026-02-18]: Credential extraction targets `url ILIKE '%rentcafe.com%'` not `platform='rentcafe'` — platform column not yet populated for most buildings
- [2026-02-18]: Tier by ROI (Roxie direction) — platform scrapers first, management company scrapers second, true one-offs last

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 1 | Validation-first scraper pipeline: scrape one RentCafe building end-to-end and push results to Google Sheet Availability tab | 2026-02-19 | 2ee0ae0 | In Progress | [1-validation-first-scraper-pipeline-scrape](./quick/1-validation-first-scraper-pipeline-scrape/) |
| 2 | Pick a non-PPM building from DB and scrape end-to-end to Google Sheet Availability tab | 2026-02-19 | a56c2cf | Awaiting Validation | [2-pick-a-building-from-the-db-not-ppm-scra](./quick/2-pick-a-building-from-the-db-not-ppm-scra/) |

## Key Decisions (this session)

- [2026-02-19]: Funnel scraper selectors verified against real Greystar/Funnel site — use div[data-beds] with data-price=-1 as unavailability filter; floor plan name used as unit_number
- [2026-02-19]: Normalizer extended for Funnel rent format ("Starting at $X") and date format ("Available MM/DD/YYYY")
- [2026-02-19]: Skip needs_classification buildings when ANTHROPIC_API_KEY is placeholder — use Tier 2 scraper buildings instead

## Session Continuity

Last session: 2026-02-19
Stopped at: Quick task 2 in progress — Imprint (Funnel) scraped, 12 floor plans in Availability sheet tab (a56c2cf). Awaiting user validation at checkpoint:human-verify.
Resume file: .planning/phases/02-scrapers/.continue-here.md
