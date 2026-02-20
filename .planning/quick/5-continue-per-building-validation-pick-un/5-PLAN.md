---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/moxie/scrapers/tier3/llm.py
  - src/moxie/scrapers/tier2/appfolio.py
  - src/moxie/scrape.py
autonomous: true
requirements: [SCRAPER-LLM-SUBPAGE, SCRAPER-APPFOLIO-LISTINGS]

must_haves:
  truths:
    - "Entrata buildings return >0 units via LLM scraper (floorplans page scraped, not homepage)"
    - "MRI buildings return >0 units via LLM scraper (floorplans page scraped, not homepage)"
    - "AppFolio Sedgwick Properties buildings return units via direct listings API"
  artifacts:
    - path: "src/moxie/scrapers/tier3/llm.py"
      provides: "LLM scraper that tries explicit floorplans subpages before link scoring"
      contains: "floorplan"
    - path: "src/moxie/scrapers/tier2/appfolio.py"
      provides: "AppFolio scraper that fetches from appfolio.com/listings directly"
      contains: "appfolio.com/listings"
  key_links:
    - from: "src/moxie/scrapers/tier3/llm.py"
      to: "Entrata/MRI building floorplans pages"
      via: "_find_availability_link tries explicit subpage URLs"
      pattern: "/floorplans|/floor-plans|/apartments"
    - from: "src/moxie/scrapers/tier2/appfolio.py"
      to: "sedgwickproperties.appfolio.com/listings"
      via: "Direct HTTP fetch of AppFolio listings API"
      pattern: "appfolio.com/listings"
---

<objective>
Fix the two highest-ROI broken scraper groups: LLM fallback (Entrata 10 + MRI 5 buildings) and AppFolio JS widget buildings (Sedgwick Properties ~3 buildings). Then validate with real buildings.

Purpose: Push coverage from 75% (306/407) toward 80%+ by unlocking 15-18 more buildings.
Output: Working LLM scraper for Entrata/MRI, working AppFolio scraper for Sedgwick Properties, validated buildings.
</objective>

<execution_context>
@C:/Users/eimil/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/eimil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/4-validate-next-building-groups-needs-clas/4-SUMMARY.md
@src/moxie/scrapers/tier3/llm.py
@src/moxie/scrapers/tier2/appfolio.py
@src/moxie/scrape.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix LLM scraper to try explicit floorplans subpages for Entrata/MRI</name>
  <files>src/moxie/scrapers/tier3/llm.py</files>
  <action>
The LLM scraper's `_find_availability_link` only follows scored internal links from the homepage. For Entrata and MRI buildings, the homepage has marketing content with no unit data, and the link scoring often fails to find the right subpage.

Fix: In `_find_availability_link`, BEFORE scoring internal links, try explicit well-known subpage URL patterns by fetching them directly. If any returns HTTP 200 and contains unit-related keywords in the HTML, use that URL as the target.

Explicit subpages to try (in order, stop at first hit):
- `{base_url}/floorplans` (Entrata standard)
- `{base_url}/floor-plans` (common alternative)
- `{base_url}/floorplans/all` (Entrata variant)
- `{base_url}/apartments` (some sites)

"Hit" means: HTTP 200 AND the page content (lowercase) contains at least one of: "available", "unit", "bed", "studio", "floor plan", "sq ft", "sqft", "move-in", "$". Use a simple httpx GET with the existing _HEADERS-style user agent and a 10-second timeout. Do NOT use Crawl4AI for this probe — plain HTTP is faster and sufficient to check if the page exists.

If an explicit subpage hits, return it immediately (skip the link scoring). If none hit, fall back to the existing internal link scoring logic.

After the fix, test with:
- `uv run scrape --building "Echelon at K Station"` (Entrata) — should find units via /floorplans
- `uv run scrape --building "Arrive LEX"` (MRI) — should find units via /floorplans or /floor-plans

If a building returns units, validate with `uv run validate-building --building "NAME"` to push to sheet. Try at least 2 Entrata and 1 MRI building.

Important: Keep the existing _find_availability_link function signature and return type unchanged. The explicit subpage check is an enhancement BEFORE the existing link scoring, not a replacement.
  </action>
  <verify>
Run `uv run scrape --building "Echelon at K Station"` — should return >0 units (was returning 0).
Run `uv run scrape --building "Arrive LEX"` — should return >0 units (was returning 0).
If either still returns 0, inspect what URL the LLM is targeting (add a print statement temporarily) and check if the subpage exists.
  </verify>
  <done>At least 2 Entrata buildings and 1 MRI building return >0 units via the LLM scraper. Results validated in Google Sheet for at least 1 building from each platform.</done>
</task>

<task type="auto">
  <name>Task 2: Fix AppFolio scraper for Sedgwick Properties direct listings</name>
  <files>src/moxie/scrapers/tier2/appfolio.py, src/moxie/scrape.py</files>
  <action>
From quick task 4 investigation: Sedgwick Properties buildings (1325 N Wells, Arco Old Town, Six Corners Lofts) embed an `Appfolio.Listing()` JS widget that loads from `sedgwickproperties.appfolio.com`. The building's own website is WordPress/Squarespace with a JS widget — hard to scrape.

Better approach: Fetch the AppFolio listings page DIRECTLY. The URL pattern is:
`https://sedgwickproperties.appfolio.com/listings`

This is a public page that lists all properties managed by Sedgwick. It may have all units across all their buildings, or it may have property-specific filters.

Step 1: Investigate the direct AppFolio listings page.
- Fetch `https://sedgwickproperties.appfolio.com/listings` with httpx
- Examine the HTML structure — look for listing cards with unit details (address, beds, rent, availability)
- Check if building names appear so we can filter to a specific building
- Print/examine the HTML to understand the DOM structure

Step 2: Based on what the listings page looks like, update `appfolio.py`:
- Instead of fetching `building.url` (the WordPress site), construct the AppFolio listings URL
- For Sedgwick buildings: use `sedgwickproperties.appfolio.com/listings`
- Parse the actual HTML structure (update `_parse_html` selectors based on real DOM)
- Filter results to only include units matching the building name/address
- If the page requires JS rendering (no unit data in static HTML), use Crawl4AI instead of httpx

Step 3: For non-Sedgwick AppFolio buildings (APM Sites type like Astoria Tower), leave them as-is for now. They need a different approach. Focus on the ~3 Sedgwick buildings.

The scraper currently fetches `building.url` which is the WordPress marketing site (returns 0 units). The fix routes Sedgwick buildings to the AppFolio listings API instead.

If AppFolio listings page requires authentication or returns no parseable data, document findings and skip — do not spend more than 20 minutes investigating.

Test with:
- `uv run scrape --building "1325 N Wells"` — Sedgwick Property, should find units
- `uv run scrape --building "Arco Old Town"` — Sedgwick Property, should find units

If working, validate 1 building with `uv run validate-building --building "NAME"`.
  </action>
  <verify>
Run `uv run scrape --building "1325 N Wells"` — should return >0 units (was returning 0).
If AppFolio listings page is not parseable, document what was found (JS-only, auth required, etc.) in the summary.
  </verify>
  <done>Either: (a) Sedgwick Properties AppFolio buildings return >0 units and at least 1 is validated on Google Sheet, OR (b) AppFolio direct listings approach documented as non-viable with specific reason (JS-rendered, auth-walled, etc.) and the finding is recorded for future reference.</done>
</task>

<task type="auto">
  <name>Task 3: Update STATE.md with results and new coverage numbers</name>
  <files>.planning/STATE.md</files>
  <action>
After Tasks 1 and 2, update STATE.md:

1. Update the "Platform distribution" table with new working counts
2. Add all validated buildings to the "Buildings validated this session" table
3. Update "Working scraper coverage: X of 407 buildings (Y%)"
4. Move completed items from "Next Steps" to "What's Done"
5. Update "Last activity" date
6. Add any new key decisions discovered during this task
7. Update the "Session Continuity" section with what to do next

Calculate new coverage:
- If Entrata (10) now works: +10 buildings
- If MRI (5) now works: +5 buildings
- If AppFolio Sedgwick (3) now works: +3 buildings
- Maximum potential: 306 + 18 = 324/407 (80%)
- Actual: based on what actually worked in Tasks 1 and 2
  </action>
  <verify>Read .planning/STATE.md and confirm coverage numbers are consistent with actual scrape results.</verify>
  <done>STATE.md reflects current coverage accurately with all validated buildings listed and next steps updated.</done>
</task>

</tasks>

<verification>
- At least 2 Entrata buildings return >0 units via LLM scraper with floorplans subpage fix
- At least 1 MRI building returns >0 units via LLM scraper with floorplans subpage fix
- AppFolio Sedgwick approach either working or documented as non-viable
- Coverage number updated in STATE.md
- All changes committed
</verification>

<success_criteria>
Coverage increases from 75% (306/407) toward 80%. LLM scraper reliably finds availability data for Entrata and MRI buildings by trying explicit floorplans subpages. AppFolio Sedgwick approach investigated and either working or ruled out with documented reason.
</success_criteria>

<output>
After completion, create `.planning/quick/5-continue-per-building-validation-pick-un/5-SUMMARY.md`
</output>
