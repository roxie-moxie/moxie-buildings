---
phase: quick-2
plan: 1
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: false
requirements: [QUICK-2]

must_haves:
  truths:
    - "A non-PPM building is scraped and its units appear in the Google Sheet Availability tab"
    - "The Availability tab is cleared before the new data is written"
    - "User can see unit rows with building name, beds, rent, availability date in the sheet"
  artifacts: []
  key_links:
    - from: "validate-building CLI"
      to: "Google Sheet Availability tab"
      via: "push_availability()"
      pattern: "ws.clear.*ws.update"
---

<objective>
Pick a non-PPM building from the DB, scrape it with validate-building, and push results to the Google Sheet Availability tab for user validation.

Purpose: Validate that the scraper pipeline works for non-PPM buildings (the first validated building was PPM). This tests either the LLM scraper or a Tier 2 platform scraper against a real building.
Output: Units from one non-PPM building visible in the Availability tab of the Google Sheet.
</objective>

<execution_context>
@C:/Users/eimil/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/eimil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/moxie/sync/push_availability.py
@src/moxie/scrapers/tier3/llm.py
@src/moxie/scrapers/platform_detect.py
@.planning/quick/1-validation-first-scraper-pipeline-scrape/1-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pick a non-PPM building and run validate-building</name>
  <files></files>
  <action>
1. Query the DB for non-PPM buildings. Pick a `needs_classification` building that likely has an availability page. Good candidates (from DB inspection):
   - "Lincoln Park Plaza" (https://lincolnparkplaza.com/) -- classic apartment website, likely has availability subpage
   - "Verdant Apartments" (https://verdantapts.com/) -- standalone site
   - "SCIO Chicago" (https://www.sciochicago.com/) -- standalone site

   Start with "Lincoln Park Plaza" as the first attempt. If it fails (LLM returns 0 units), try "Verdant Apartments", then "SCIO Chicago".

2. Before running, verify ANTHROPIC_API_KEY is set and looks valid (should be ~100+ chars, starts with "sk-ant-"). The key showed as 13 chars which may be a placeholder. If invalid, STOP and tell the user to set it in .env.

3. Run the validate-building command (which clears the sheet, scrapes, saves to DB, pushes to sheet):
   ```
   export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8
   uv run validate-building --building "Lincoln Park Plaza"
   ```

   The building has platform=needs_classification, so `detect_platform()` will return None, which means it will route to `llm` scraper (Crawl4AI + Claude Haiku). This is the desired behavior.

4. If the first building returns 0 units, try the next candidate. The LLM scraper does two-pass crawling (finds availability subpage first), so it should work on most standard apartment websites.

5. If validate-building fails with an error, capture the full error output. Common failure modes:
   - ANTHROPIC_API_KEY not set or invalid -> tell user
   - Google Sheets auth error -> check google-credentials.json
   - Crawl4AI timeout -> try a different building
   - 0 units returned -> try next candidate or try with `--platform llm` explicit override

6. On success, note the building name, number of units scraped, and number pushed to sheet.
  </action>
  <verify>
   - Command output shows "Units scraped: N" where N > 0
   - Command output shows "Pushed N unit(s) to Availability tab" where N > 0
   - No ERROR lines in output
  </verify>
  <done>At least one non-PPM building has been scraped, saved to DB, and pushed to the Availability sheet tab with N > 0 units.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: User validates building data in Google Sheet</name>
  <what-built>Scraped a non-PPM building and pushed unit data to the Google Sheet Availability tab. The sheet should now show units from the scraped building with columns: Building Name, Neighborhood, Unit #, Beds, Rent, Available Date, Floor Plan, Baths, SqFt, Management Company, Scraped At, URL.</what-built>
  <how-to-verify>
    1. Open the Google Sheet: https://docs.google.com/spreadsheets/d/1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI
    2. Go to the "Availability" tab
    3. Verify the data looks correct:
       - Building name matches the scraped building
       - Unit numbers look like real apartment numbers (not floor plan names)
       - Rents are in reasonable range ($1,000-$5,000 for Chicago apartments)
       - Bed types are recognizable (Studio, 1BR, 2BR, etc.)
       - Available dates are present and reasonable
    4. Cross-check a few units against the building's actual website to confirm accuracy
    5. Note any issues: missing units, wrong rents, bad unit numbers, etc.
  </how-to-verify>
  <resume-signal>Type "approved" if the data looks correct, or describe any issues you see.</resume-signal>
</task>

</tasks>

<verification>
- Non-PPM building scraped successfully (not PPM platform)
- Availability tab in Google Sheet populated with unit data
- User has reviewed and validated (or flagged issues with) the data
</verification>

<success_criteria>
- One non-PPM building scraped end-to-end with validate-building
- Google Sheet Availability tab shows the building's units
- User has validated or provided feedback on data quality
</success_criteria>

<output>
After completion, create `.planning/quick/2-pick-a-building-from-the-db-not-ppm-scra/2-SUMMARY.md`
</output>
