---
phase: quick-1
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/moxie/sync/push_availability.py
  - pyproject.toml
autonomous: false
requirements: [SCRAP-01, SCRAP-03]

must_haves:
  truths:
    - "At least one RentCafe building has both rentcafe_property_id and rentcafe_api_token in the DB"
    - "Running the scraper for that building returns normalized unit records saved to the units table"
    - "A new 'Availability' tab exists in the Google Sheet with unit data from the scraped building"
    - "User can see building name, unit numbers, bed types, rents, and availability dates in the sheet"
  artifacts:
    - path: "src/moxie/sync/push_availability.py"
      provides: "Google Sheets writer for scraped availability data"
      exports: ["push_availability", "main"]
    - path: "pyproject.toml"
      provides: "CLI entrypoint for validate-building command"
      contains: "validate-building"
  key_links:
    - from: "src/moxie/sync/push_availability.py"
      to: "gspread"
      via: "service_account + open_by_key + worksheet"
      pattern: "gc\\.open_by_key.*worksheet"
    - from: "src/moxie/sync/push_availability.py"
      to: "src/moxie/db/models.py"
      via: "queries Unit joined with Building"
      pattern: "db\\.query\\(Unit\\)"
    - from: "src/moxie/sync/push_availability.py"
      to: "src/moxie/scrape.py"
      via: "validate-building calls scrape + save + push"
      pattern: "save_scrape_result.*push_availability"
---

<objective>
End-to-end validation pipeline: pick one RentCafe building that already has credentials (or can get them quickly), scrape it, save to DB, and push results to a new "Availability" tab in the Google Sheet so the user can visually validate real scraped data.

Purpose: Close the feedback loop between scraper output and user validation. Until the user can see actual scraped units in the sheet, there is no way to confirm data quality at a glance.

Output: A `validate-building` CLI command that scrapes a single building, saves to DB, and writes an "Availability" tab to the Google Sheet. One building validated end-to-end.
</objective>

<execution_context>
@C:/Users/eimil/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/eimil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/moxie/scrapers/tier1/rentcafe.py
@src/moxie/scrape.py
@src/moxie/sync/sheets.py
@src/moxie/db/models.py
@src/moxie/db/session.py
@src/moxie/scrapers/base.py
@src/moxie/normalizer.py
@src/moxie/config.py
@pyproject.toml
@scripts/extract_rentcafe_credentials.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create push_availability module and validate-building CLI</name>
  <files>
    src/moxie/sync/push_availability.py
    pyproject.toml
  </files>
  <action>
Create `src/moxie/sync/push_availability.py` with two public functions:

**`push_availability(db: Session, building_ids: list[int] | None = None) -> int`**
- Queries the `units` table joined with `buildings` to get all scraped unit data
- If `building_ids` is provided, filters to only those buildings
- Authenticates to Google Sheets using `gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)` and `gc.open_by_key(GOOGLE_SHEETS_ID)` (same pattern as sheets.py)
- Creates or gets the "Availability" worksheet tab (use `sh.worksheet("Availability")` in a try/except, falling back to `sh.add_worksheet(title="Availability", rows=1000, cols=12)`)
- Clears the worksheet, then writes a header row and all unit data
- Header columns: Building Name, Neighborhood, Unit #, Beds, Rent, Available Date, Floor Plan, Baths, SqFt, Management Company, Scraped At, URL
- Rent formatting: convert `rent_cents` to dollar string (e.g., 150000 -> "$1,500")
- Sort rows by building name then unit number
- Returns the number of rows written (excluding header)

**`main()` — the `validate-building` CLI entrypoint**
- Accepts `--building NAME` (required) — partial name match, same pattern as scrape.py
- Accepts `--save` flag (default True, since the whole point is to validate end-to-end)
- Accepts `--sheet-only` flag — skip scraping, just push existing DB data to the sheet
- Flow when not `--sheet-only`:
  1. Look up building by name (same lookup logic as scrape.py)
  2. Determine platform (same as scrape.py: building.platform, fall back to detect_platform, then "llm")
  3. Import and call the correct scraper module (same PLATFORM_SCRAPERS dict)
  4. Call `save_scrape_result(db, building, raw_units, scrape_succeeded=True)` and commit
  5. Call `push_availability(db, building_ids=[building.id])`
  6. Print summary: building name, units scraped, units pushed to sheet
- Flow when `--sheet-only`:
  1. Look up building by name
  2. Call `push_availability(db, building_ids=[building.id])`
  3. Print summary

Import patterns to follow (from sheets.py and scrape.py):
- `from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH`
- `from moxie.db.models import Building, Unit`
- `from moxie.db.session import get_db`
- `from moxie.scrapers.base import save_scrape_result`
- `from moxie.scrapers.platform_detect import detect_platform`
- `import gspread`
- `import importlib`

Register CLI in pyproject.toml `[project.scripts]`:
```
validate-building = "moxie.sync.push_availability:main"
```

Use the exact same PLATFORM_SCRAPERS dict from scrape.py (copy it — do NOT import from scrape.py to avoid circular dependency risk). Add a comment: "# Duplicated from scrape.py — keep in sync".
  </action>
  <verify>
Run `uv run python -c "from moxie.sync.push_availability import push_availability, main; print('imports OK')"` — must print "imports OK" with no errors.

Run `uv run validate-building --help` — must show usage with --building, --save, --sheet-only flags.
  </verify>
  <done>
`push_availability` function exists and is importable. `validate-building` CLI is registered and shows help. The module reads from the units/buildings tables and writes to a Google Sheets "Availability" tab using gspread.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Run end-to-end validation on one RentCafe building</name>
  <files>moxie.db</files>
  <action>
Ensure one building has BOTH credentials, then run the full validate-building pipeline.

Step 1 — Check which buildings are ready:
```
uv run python -c "
from moxie.db.session import SessionLocal
from moxie.db.models import Building
db = SessionLocal()
ready = db.query(Building).filter(
    Building.rentcafe_property_id.isnot(None),
    Building.rentcafe_api_token.isnot(None)
).all()
print(f'{len(ready)} buildings ready')
for b in ready[:5]:
    print(f'  {b.name} -- code={b.rentcafe_property_id}, token={b.rentcafe_api_token[:8]}...')
db.close()
"
```

Step 2 — If none ready, find a Reside building with a token and extract its code:
```
uv run python -c "
from moxie.db.session import SessionLocal
from moxie.db.models import Building
db = SessionLocal()
has_token = db.query(Building).filter(Building.rentcafe_api_token.isnot(None), Building.rentcafe_property_id.is_(None)).first()
if has_token: print(f'Use: {has_token.name}')
else: print('No building with token found')
db.close()
"
```
Then: `uv run rentcafe-creds extract-codes --building "BUILDING_NAME"`

Step 3 — Run the full pipeline:
```
uv run validate-building --building "BUILDING_NAME"
```

The executor should adapt the BUILDING_NAME based on what the DB queries return.
  </action>
  <verify>
Terminal output shows building name, platform=rentcafe, unit count > 0, and confirmation that rows were pushed to the Availability tab.
  </verify>
  <done>
At least one building has been scraped end-to-end: units exist in the DB and rows appear in the Google Sheets Availability tab. User has visually confirmed the data.
  </done>
  <what-built>
The validate-building CLI and push_availability module from Task 1. This checkpoint runs the full pipeline on a real building and asks the user to verify the Availability tab in Google Sheets.

Before running validate-building, we need a building with BOTH credentials. The current state:
- 35 Reside buildings have `rentcafe_api_token` but NO `rentcafe_property_id`
- Fisher Building has `rentcafe_property_id='fisherbuildingchicago'` but NO token

Fastest path: pick a Reside building with a token, run `extract-codes --building NAME` to get its VoyagerPropertyCode, then validate.
  </what-built>
  <how-to-verify>
1. Check terminal output — should show building name, platform, unit count, and "pushed to Availability tab"
2. Open Google Sheets: https://docs.google.com/spreadsheets/d/1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI
3. Look for the "Availability" tab at the bottom
4. Verify the data looks reasonable:
   - Building name matches the one you scraped
   - Unit numbers look like real apartment numbers (not floor plan names)
   - Bed types are canonical (Studio, 1BR, 2BR, etc.)
   - Rents are in dollar format and look reasonable for Chicago ($1,000-$5,000 range)
   - Availability dates are real dates (YYYY-MM-DD format)
   - No obviously garbage data
5. Count units in sheet vs what the terminal reported — should match
  </how-to-verify>
  <resume-signal>Type "approved" if the Availability tab data looks correct, or describe any issues (wrong data, missing columns, formatting problems, etc.)</resume-signal>
</task>

</tasks>

<verification>
- `src/moxie/sync/push_availability.py` exists and contains `push_availability()` and `main()`
- `validate-building` CLI is registered in pyproject.toml and runs
- At least one building has been scraped end-to-end (units in DB + rows in Availability sheet tab)
- User has visually confirmed the Availability tab data in Google Sheets
</verification>

<success_criteria>
The user can run `uv run validate-building --building "NAME"` for any building with credentials, and see the scraped availability data appear in the Google Sheets "Availability" tab within seconds. The data is accurate, well-formatted, and matches what the scraper returned.
</success_criteria>

<output>
After completion, create `.planning/quick/1-validation-first-scraper-pipeline-scrape/1-SUMMARY.md`
</output>
