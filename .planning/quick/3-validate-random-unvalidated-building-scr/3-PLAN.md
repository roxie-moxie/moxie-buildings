---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: true
requirements: [SCRAPER-SIGHTMAP]

must_haves:
  truths:
    - "validate-building command runs to completion without crashing"
    - "Google Sheet Availability tab is updated (cleared and rewritten) with whatever results were found"
    - "User receives a clear report of how many units were scraped and whether the scraper succeeded or failed"
  artifacts:
    - path: "moxie.db"
      provides: "Unit records for Next (if scrape succeeded)"
      contains: "availability rows for building 'Next'"
  key_links:
    - from: "validate-building CLI"
      to: "SightMap API scraper"
      via: "platform dispatch in scraper registry"
      pattern: "sightmap"
    - from: "SightMap scraper"
      to: "Google Sheet Availability tab"
      via: "push_availability function (clears then writes)"
      pattern: "push_availability"
---

<objective>
Run the validate-building pipeline for "Next" (SightMap platform, River North, Greystar) and report results.

Purpose: Verify the SightMap scraper works against a third building (after EMME and AMLI 900). SightMap discovery + API pattern is confirmed — this validates coverage across management companies (Greystar vs previous targets).
Output: Units for "Next" pushed to Google Sheet Availability tab; result reported to user whether scrape succeeded, returned 0 units, or errored.
</objective>

<execution_context>
@C:/Users/eimil/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/eimil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run validate-building for Next and report results</name>
  <files>moxie.db (updated in place by validate-building)</files>
  <action>
    Run the validate-building command for "Next" using the confirmed SightMap scraper path.

    Command:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && cd "/c/Users/eimil/projects/Roxie Projects/moxie-buildings" && uv run validate-building --building "Next"
    ```

    The command will:
    1. Look up "Next" in moxie.db by building name
    2. Detect platform as sightmap (or read from DB)
    3. Run SightMap scraper: fetch nextapts.com, find sightmap.com embed, parse __APP_CONFIG__, call public JSON API
    4. Normalize and save units to moxie.db
    5. Clear the Google Sheet Availability tab and push results

    If the command errors or returns 0 units, do NOT retry — capture the full output (stdout + stderr) and report it verbatim to the user. The goal is observability, not a successful scrape.

    Do NOT attempt to fix scraper errors inline — just run once and report.
  </action>
  <verify>
    Command exits (any exit code is acceptable). Capture full output including any errors.

    After running, check unit count:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && cd "/c/Users/eimil/projects/Roxie Projects/moxie-buildings" && uv run python -c "import sqlite3; conn = sqlite3.connect('moxie.db'); cur = conn.cursor(); cur.execute(\"SELECT COUNT(*) FROM units u JOIN buildings b ON u.building_id = b.id WHERE b.name = 'Next'\"); print('Units in DB:', cur.fetchone()[0])"
    ```
  </verify>
  <done>
    Command has run to completion. User receives:
    - Full CLI output (success message or error traceback)
    - Unit count found in moxie.db for "Next"
    - Confirmation that Google Sheet was updated (or reason it was not)
    - Clear pass/fail verdict on whether SightMap scraper works for this building
  </done>
</task>

</tasks>

<verification>
- validate-building ran (any outcome reported)
- Unit count in moxie.db for "Next" is known
- Google Sheet Availability tab reflects current state (even if 0 units)
</verification>

<success_criteria>
User knows exactly how many units were found for "Next" and whether the SightMap scraper works for a Greystar-managed building. If 0 units or error, the full output is shared so the cause can be diagnosed.
</success_criteria>

<output>
After completion, create `.planning/quick/3-validate-random-unvalidated-building-scr/3-SUMMARY.md` with:
- Units found for Next
- Whether scrape succeeded, returned 0, or errored
- Full CLI output (or key excerpt if very long)
- SightMap scraper verdict for this building
</output>
