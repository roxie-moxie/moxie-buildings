# Buildings Scraper — Progress Notes

## Last Updated: 2026-02-16

## Platform Types Identified

### ✅ Groupfox / RentCafe (Horizon, Willow Bridge, Habitat, etc.)
- **Scraper:** `scrape-groupfox.mjs`
- **Pattern:** `/floorplans` page with subpage links per floor plan type (e.g. `/floorplans/studio`, `/floorplans/one-bedroom`)
- **Data format:** Two variants:
  1. **Table format:** `#UNIT \t SqFt \t $RENT \t Date \t Apply Now` (e.g. 215 West)
  2. **Card format:** `Apartment: # XX-XXXX \n Starting at: $X,XXX` (e.g. Kingsbury Plaza, 901 Argyle)
- **Quirks:**
  - Some Groupfox sites show "Call for details" with no pricing (Melrose Shores, The Chatelaine) — these are dead ends
  - Availability dates often hidden behind the Apply flow — we mark these as "Unsure"
  - Unit numbers can be hyphenated (e.g. "01-4403" at Kingsbury) — scraper updated to handle this
  - Some sites show sqft in table columns, others don't
  - "Sq" was being captured as a false unit number — filtered out
  - "or" was captured as a unit number from "Starting at $X or..." text — needs min-length/numeric filter
- **Buildings validated:** Axis (BLD-0031), 901 Argyle (BLD-0409), 215 West (BLD-0120), 2555 N Clark (BLD-0297), Kingsbury Plaza (BLD-0219), 525 Oakdale (BLD-0273)

### ✅ PPM (Planned Property Management)
- **Scraper:** Text parsing from centralized availability page
- **Pattern:** `ppmapartments.com/availability/` — single page with ALL PPM buildings
- **Data format:** Repeating blocks: Neighborhood, Building, Unit, Availability, UnitType, Floorplan, Features, Price
- **Quirks:** Data is JS-loaded but text extraction works. 206 units across ~30 buildings in one page!
- **Buildings validated:** 2756 N Pine Grove (BLD-0020)

### ✅ Cross Street (via Wix iframe)
- **Scraper:** Manual iframe extraction (needs dedicated scraper)
- **Pattern:** Wix site with `yourcrossstreet.com` iframe containing floor plan widget
- **Data format:** Clean div structure: `.fp-content-single-unit-name`, `.fp-content-single-unit-rent`, `.fp-content-single-unit-size`, `.fp-content-single-unit-available`
- **Quirks:** Must click the arrow/accordion to expand unit details. Data is very clean once expanded.
- **Buildings validated:** The Porter (BLD-0167)

### ✅ Custom Sites (Draper & Kramer, etc.)
- **Scraper:** Per-site extraction
- **Pattern:** `/available-residences/` page with floor plan cards showing unit details
- **Data format:** Unit #, Sq Ft, Rent Range, Available Date in table rows
- **Buildings validated:** 61 Bank St (BLD-0250)

### ❌ Dead Ends
- **No data on site:** River North Lofts (BLD-0405), The Porter initially (BLD-0167 — actually had iframe)
- **Call for details only:** Melrose Shores (BLD-0400), The Chatelaine (BLD-0341), 713 N Milwaukee (BLD-0333), Arco Old Town (BLD-0192 — "Inquire" only)
- **Fully leased:** No. 508 (BLD-0300)

## Standardized Size Categories (Column E)
- Studio
- Convertible
- One Bed
- One Bed + Den
- Two Bed
- Three Bed
- Four Bed+

## Scraper Quality Labels (Column P in Buildings sheet)
- ✅ Validated — scraped and human-verified
- 🔍 Needs Validation — scraped, awaiting review
- ⏳ Fully leased / no availability — untested, try again later
- ❌ No data / Call for details — can't scrape

## Business Rules
- **"Call for pricing" = skip** — means the unit is not actually coming available. Do not include in output.
- **When testing a new building, clear the Availability sheet first** — Alex wants to see each building alone during validation.
- **Avail Date format: MM/DD or MM/DD/YYYY** — standardize all dates. "Now" stays as "Now". Convert "Mar. 07" → "3/7", "Apr 05" → "4/5", etc.

## Process Rules
- **After every validated building:** Update column P (Scraper Quality) in the Buildings sheet. Don't skip this.
- **Dynamic column detection:** Scraper code should resolve column letters by reading header row at runtime, not hardcoding positions. Prevents breakage if Alex reorganizes the sheet.

## Known Bugs / TODO
- [ ] Add minimum length + numeric check to unit number regex (filter out "or", "Sq", etc.)
- [ ] Build dedicated Cross Street iframe scraper for reuse
- [ ] Build PPM batch scraper (scrape one page, populate all PPM buildings at once)
- [ ] Floor Plan Sqft lookup table — static sqft per floor plan that never changes
- [ ] Handle "Available Now" vs "Unsure" more precisely across platforms
- [ ] Concession/specials extraction (some sites flag "Specials Available" but no dollar amount)
- [ ] Set up VPN before running automated daily scrapes (bot detection risk)
- [ ] GitHub repo for version control

## Aggregator Sites Investigated
- **RentWrk** — has API (`api.rentwrktemp.com/v1/building`) but auth-gated for detail data. ~250 Chicago buildings. Not viable for scraping.
- **AptAmigo** — map-based UI, building summaries only. Detail pages 404'd. Competitor tool, not viable.

## Architecture
- All scrapers in: `/workspace/scraper-poc/scrapers/`
- Sheets API tools in: `/workspace/tools/sheets/`
- Target sheet: "Moxie Buildings 2.0 beta" (`1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI`)
- Availability tab: unit-level data (cleared between validation runs)
- Buildings tab: column P = Scraper Quality
