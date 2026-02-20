---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [moxie.db, src/moxie/scrapers/tier2/appfolio.py, src/moxie/scrapers/tier2/realpage.py, src/moxie/scrapers/tier2/bozzuto.py]
autonomous: true
requirements: [SCRAPER-REMAINING-PLATFORMS]

must_haves:
  truths:
    - "At least 5 needs_classification buildings are investigated and either reclassified to a working platform or documented as requiring a new approach"
    - "At least one building from each broken platform (AppFolio, RealPage, Bozzuto) is tested and the failure mode is diagnosed"
    - "At least one Entrata and one MRI building is tested via LLM fallback"
    - "Findings are documented with clear patterns: which management companies map to which actual data sources"
  artifacts:
    - path: "moxie.db"
      provides: "Reclassified buildings and any newly scraped units"
      contains: "Updated platform values for investigated buildings"
    - path: ".planning/quick/4-validate-next-building-groups-needs-clas/4-SUMMARY.md"
      provides: "Documented findings, patterns, and next steps"
      contains: "Platform investigation results table"
  key_links:
    - from: "needs_classification investigation"
      to: "SightMap/SecureCafe reclassification"
      via: "Checking building websites for sightmap.com/embed or securecafe.com links"
      pattern: "sightmap.com/embed|securecafe.com"
    - from: "broken scraper diagnosis"
      to: "scraper fix or platform reclassification"
      via: "Running validate-building, inspecting HTML, checking for alternative data sources"
      pattern: "validate-building --building"
---

<objective>
Investigate remaining unscraped building groups to discover patterns and expand coverage beyond 75%.

Purpose: 101 buildings remain without working scrapers (needs_classification: 61, appfolio: 18, realpage: 5, bozzuto: 2, entrata: 9, mri: 5, funnel: 2). Previous sessions discovered that many buildings classified under one platform actually serve data via SightMap embeds or SecureCafe portals. This task systematically probes samples from each group to find the fastest path to coverage.

Output: Investigation report with building-by-building results, platform reclassifications applied to moxie.db, and a prioritized strategy for the remaining 101 buildings.
</objective>

<execution_context>
@C:/Users/eimil/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/eimil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/3-validate-random-unvalidated-building-scr/3-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Investigate needs_classification buildings — strategic sample of 8-10</name>
  <files>moxie.db</files>
  <action>
    Pick 8-10 buildings from needs_classification, prioritizing diversity of management companies and URL patterns. Use this specific sample to cover the widest variety:

    **Priority picks (known mgmt companies with multiple buildings — patterns transfer):**
    1. "1325 N Wells" (Greystar — high chance of SightMap embed)
    2. "The Bachelor" (FLATS — livethe*.com pattern, likely SightMap like The Ardus)
    3. "1471 N Milwaukee" (Reside — 3 Reside buildings in needs_classification)
    4. "3141 N Sheffield" (BJB — 3 BJB buildings, property management portfolio site)
    5. "500 Lake Shore Drive" (Related — 2 Related buildings, relatedrentals.com domain)
    6. "Renew Waterside" (Trinity — 3 Trinity buildings)
    7. "Alta" (Morguard — also has Entrata buildings, might reveal connection)
    8. "Left Bank" (Hines — unique mgmt company)

    **For each building, follow this investigation protocol:**

    Step 1: Run validate-building to see what happens with current platform:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "BUILDING_NAME"
    ```
    Since platform is `needs_classification`, this will fail or fall through. Note the error.

    Step 2: Check for SightMap embed (the most common hidden pattern):
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx
    url = 'BUILDING_URL'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    client = httpx.Client(timeout=30, headers=headers, follow_redirects=True)
    for page_url in [url, url.rstrip('/') + '/floorplans', url.rstrip('/') + '/floorplans/']:
        try:
            resp = client.get(page_url)
            if 'sightmap.com/embed' in resp.text:
                import re
                matches = re.findall(r'sightmap\.com/embed/([a-z0-9]+)', resp.text)
                print(f'SIGHTMAP FOUND at {page_url}: embed IDs = {matches}')
        except Exception as e:
            print(f'Error fetching {page_url}: {e}')
    client.close()
    "
    ```

    Step 3: Check for SecureCafe leasing portal link:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx
    url = 'BUILDING_URL'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    if 'securecafe.com' in resp.text:
        import re
        matches = re.findall(r'https?://[a-z0-9.-]*securecafe\.com/[^\s\"<>]+', resp.text)
        print(f'SECURECAFE FOUND: {matches[:3]}')
    elif 'rentcafe.com' in resp.text:
        import re
        matches = re.findall(r'https?://[a-z0-9.-]*rentcafe\.com/[^\s\"<>]+', resp.text)
        print(f'RENTCAFE FOUND: {matches[:3]}')
    else:
        print('No SecureCafe/RentCafe links found')
        # Check for other known patterns
        for pattern in ['entrata.com', 'appfolio.com', 'realpage.com', 'residentportal.com', 'funnelleasing.com', 'nestiolistings.com']:
            if pattern in resp.text:
                print(f'  Found pattern: {pattern}')
    "
    ```

    Step 4: If SightMap or SecureCafe found, reclassify the building in the DB:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && uv run python -c "
    from moxie.db.session import SessionLocal
    from moxie.db.models import Building
    db = SessionLocal()
    b = db.query(Building).filter(Building.name == 'BUILDING_NAME').first()
    b.platform = 'sightmap'  # or 'rentcafe'
    db.commit()
    print(f'Reclassified {b.name} to {b.platform}')
    db.close()
    "
    ```

    Step 5: Re-run validate-building after reclassification to confirm it works:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "BUILDING_NAME"
    ```

    Step 6: If neither SightMap nor SecureCafe found, try LLM fallback:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "BUILDING_NAME" --platform llm
    ```

    Record results in a structured table for each building: Name, Original Platform, Discovered Platform, Units Found, Verdict (pass/fail/reclassified/needs-manual).

    IMPORTANT: Do NOT spend more than 3-5 minutes per building. If investigation is inconclusive, mark as "needs deeper investigation" and move on. The goal is pattern discovery, not 100% resolution.

    After investigating the sample, check if any discovered patterns apply broadly:
    - If FLATS/Bachelor has SightMap, the remaining FLATS buildings likely do too
    - If BJB buildings are simple property pages, all 3 BJB buildings share the pattern
    - If Reside buildings use a specific portal, all 3 Reside buildings likely match
  </action>
  <verify>
    Count reclassified buildings:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && uv run python -c "
    from moxie.db.session import SessionLocal
    from moxie.db.models import Building
    db = SessionLocal()
    nc = db.query(Building).filter(Building.platform == 'needs_classification').count()
    print(f'Remaining needs_classification: {nc} (was 61)')
    db.close()
    "
    ```
    Count should be lower than 61 if any reclassifications were made.
  </verify>
  <done>
    8-10 needs_classification buildings investigated. For each: discovered platform identified (sightmap/securecafe/llm/unknown), reclassification applied if applicable, validate-building re-run result recorded. Management company patterns documented (e.g., "all Reside buildings use X", "BJB sites are static portfolio pages").
  </done>
</task>

<task type="auto">
  <name>Task 2: Diagnose broken platform scrapers — AppFolio, RealPage, Bozzuto (one building each)</name>
  <files>moxie.db, src/moxie/scrapers/tier2/appfolio.py, src/moxie/scrapers/tier2/realpage.py, src/moxie/scrapers/tier2/bozzuto.py</files>
  <action>
    Test one building from each broken platform. The goal is NOT to fix the scraper yet — it is to diagnose the actual HTML structure and determine whether the platform scraper approach is viable or if these buildings should be reclassified.

    **AppFolio — test "Astoria Tower" (has named mgmt company, most likely to have real listing page):**

    Step 1: Run the existing scraper to see the failure:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "Astoria Tower"
    ```

    Step 2: Fetch the page HTML and inspect its actual structure:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx
    url = 'https://astoriatowerchicago.com/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    print(f'Status: {resp.status_code}, Final URL: {resp.url}')
    print(f'Content length: {len(resp.text)}')
    # Check for known platform patterns
    for pattern in ['sightmap.com', 'securecafe.com', 'rentcafe.com', 'appfolio.com', 'entrata.com', 'realpage.com', 'funnelleasing.com']:
        if pattern in resp.text.lower():
            print(f'Found: {pattern}')
    # Show a snippet around 'available' or 'unit' or 'apartment'
    text = resp.text.lower()
    for keyword in ['available', 'unit', 'floorplan', 'apartment', 'listing']:
        idx = text.find(keyword)
        if idx > 0:
            print(f'Context around \"{keyword}\": ...{resp.text[max(0,idx-100):idx+200]}...')
            break
    "
    ```

    Step 3: Check if AppFolio buildings actually link to appfolio.com listing pages (the scraper expects this):
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && uv run python -c "
    import httpx, re
    url = 'https://astoriatowerchicago.com/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    # Look for appfolio iframe or link
    matches = re.findall(r'https?://[a-z0-9.-]*appfolio[a-z]*\.[a-z]+/[^\s\"<>]+', resp.text, re.I)
    if matches:
        print(f'AppFolio links found: {matches[:5]}')
    else:
        print('No AppFolio links in page HTML')
    # Also check /floorplans or /availability subpages
    for suffix in ['/floorplans', '/availability', '/apartments', '/listings']:
        try:
            resp2 = httpx.get(url.rstrip('/') + suffix, headers=headers, follow_redirects=True, timeout=15)
            if resp2.status_code == 200 and len(resp2.text) > 500:
                print(f'{suffix}: {resp2.status_code}, length={len(resp2.text)}')
                if 'appfolio' in resp2.text.lower():
                    print(f'  -> Contains appfolio reference!')
        except Exception:
            pass
    "
    ```

    **RealPage — test "Luxe on Chicago" (Greystar — high chance of SightMap embed):**

    Step 1: Check for SightMap embed first (all 5 RealPage buildings are Greystar):
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx, re
    url = 'https://www.luxeonchicago.com/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    client = httpx.Client(timeout=30, headers=headers, follow_redirects=True)
    for page_url in [url, url.rstrip('/') + '/floorplans', url.rstrip('/') + '/floorplans/']:
        try:
            resp = client.get(page_url)
            if 'sightmap.com/embed' in resp.text:
                matches = re.findall(r'sightmap\.com/embed/([a-z0-9]+)', resp.text)
                print(f'SIGHTMAP FOUND at {page_url}: embed IDs = {matches}')
            elif resp.status_code == 200:
                print(f'{page_url}: no sightmap (status {resp.status_code}, len={len(resp.text)})')
        except Exception as e:
            print(f'Error: {page_url}: {e}')
    client.close()
    "
    ```

    If SightMap found for Luxe on Chicago, check the other 4 RealPage buildings (Elevate, Sono East, Aston, Clybourn 1200) for the same pattern. If all have SightMap, reclassify all 5 to sightmap platform.

    Step 2: If no SightMap, run existing RealPage scraper and inspect failure:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "Luxe on Chicago"
    ```

    **Bozzuto — test "Atwater Apartments":**

    Step 1: Check for SightMap/SecureCafe patterns:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx, re
    url = 'https://www.liveatwaterchicago.com'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    client = httpx.Client(timeout=30, headers=headers, follow_redirects=True)
    for page_url in [url, url + '/floorplans', url + '/floorplans/', url + '/floor-plans', url + '/apartments']:
        try:
            resp = client.get(page_url)
            for pattern in ['sightmap.com/embed', 'securecafe.com', 'rentcafe.com', 'entrata.com', 'bozzuto.com/apartments']:
                if pattern in resp.text:
                    print(f'Found {pattern} at {page_url}')
                    if 'sightmap' in pattern:
                        ids = re.findall(r'sightmap\.com/embed/([a-z0-9]+)', resp.text)
                        print(f'  SightMap IDs: {ids}')
        except Exception as e:
            print(f'Error: {page_url}: {e}')
    client.close()
    "
    ```

    Step 2: Run existing Bozzuto scraper:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "Atwater Apartments"
    ```

    **For each platform, record:**
    - Does the building URL redirect somewhere?
    - What's the actual HTML structure?
    - Is there a SightMap embed or SecureCafe portal hiding?
    - Is the current scraper's CSS selector approach viable, or should these be reclassified?
    - If reclassification possible, apply it and re-run validate-building

    Do NOT attempt to rewrite the scraper files in this task. Only reclassify buildings in the DB if a working alternative platform (sightmap/rentcafe) is found. Scraper rewrites are a separate task.
  </action>
  <verify>
    For each of the 3 tested buildings, one of these outcomes is documented:
    - Reclassified to working platform (sightmap/rentcafe) and validate-building succeeds
    - Current scraper diagnosed with specific CSS selector issues (what the HTML actually looks like)
    - LLM fallback tested as alternative
    - Building identified as truly unscrapeable (no public availability data)

    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && uv run python -c "
    from moxie.db.session import SessionLocal
    from moxie.db.models import Building
    db = SessionLocal()
    for plat in ['appfolio', 'realpage', 'bozzuto']:
        count = db.query(Building).filter(Building.platform == plat).count()
        print(f'{plat}: {count} buildings')
    db.close()
    "
    ```
  </verify>
  <done>
    One building from each of AppFolio, RealPage, and Bozzuto has been tested. For each: the failure mode is identified (wrong selectors, needs JS rendering, has hidden SightMap/SecureCafe, or no public data). Any buildings with discovered SightMap/SecureCafe are reclassified and validated. A clear recommendation exists for each platform: "fix scraper selectors", "reclassify all to sightmap", "use LLM fallback", or "skip — no public data".
  </done>
</task>

<task type="auto">
  <name>Task 3: Test Entrata and MRI LLM fallback + compile investigation report</name>
  <files>moxie.db</files>
  <action>
    **Part A: Test Entrata LLM fallback (pick "Echelon at K Station" — Morguard mgmt):**

    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "Echelon at K Station"
    ```

    Since Entrata routes to LLM scraper, this tests whether the LLM fallback can extract unit data from an Entrata-powered site. Record:
    - Did it find any units?
    - Were the units plausible (real unit numbers, reasonable prices)?
    - How long did it take?
    - Any errors?

    If LLM fails, also check for SightMap/SecureCafe:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run python -c "
    import httpx, re
    url = 'https://www.echelonchicago.com/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    client = httpx.Client(timeout=30, headers=headers, follow_redirects=True)
    for page_url in [url, url + 'floorplans', url + 'floorplans/', url + 'floor-plans', url + 'apartments']:
        try:
            resp = client.get(page_url)
            if resp.status_code == 200:
                for pat in ['sightmap.com/embed', 'securecafe.com', 'rentcafe.com']:
                    if pat in resp.text:
                        print(f'Found {pat} at {page_url}')
                        if 'sightmap' in pat:
                            ids = re.findall(r'sightmap\.com/embed/([a-z0-9]+)', resp.text)
                            print(f'  IDs: {ids}')
        except Exception as e:
            print(f'{page_url}: {e}')
    client.close()
    "
    ```

    **Part B: Test MRI LLM fallback (pick "Arrive LEX"):**

    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && export PYTHONIOENCODING=utf-8 && uv run validate-building --building "Arrive LEX"
    ```

    Same evaluation criteria as Entrata. Also check for SightMap/SecureCafe alternatives.

    **Part C: Compile full investigation report**

    After all 3 tasks complete, compile a full results table summarizing ALL buildings investigated across Tasks 1-3:

    | Building | Original Platform | Discovered Source | Units | Action Taken | Transferable Pattern |
    |----------|-------------------|-------------------|-------|--------------|---------------------|
    | ... | ... | ... | ... | ... | ... |

    Then compute updated coverage:
    ```
    export PATH="/c/Users/eimil/.local/bin:$PATH" && uv run python -c "
    from moxie.db.session import SessionLocal
    from moxie.db.models import Building
    db = SessionLocal()
    working = ['rentcafe', 'ppm', 'sightmap', 'groupfox']
    working_count = sum(db.query(Building).filter(Building.platform == p).count() for p in working)
    total = db.query(Building).count()
    print(f'Working scraper coverage: {working_count}/{total} ({100*working_count//total}%)')
    print()
    for plat in ['rentcafe', 'sightmap', 'ppm', 'groupfox', 'needs_classification', 'appfolio', 'realpage', 'bozzuto', 'entrata', 'mri', 'funnel', 'llm']:
        c = db.query(Building).filter(Building.platform == plat).count()
        if c > 0:
            print(f'  {plat}: {c}')
    db.close()
    "
    ```

    Document key findings:
    1. Which management companies map to which actual data sources
    2. How many needs_classification buildings can be batch-reclassified based on discovered patterns
    3. Whether AppFolio/RealPage/Bozzuto scrapers should be fixed or abandoned in favor of reclassification
    4. Whether Entrata/MRI LLM fallback is viable or needs dedicated scrapers
    5. Updated coverage number and remaining gap
  </action>
  <verify>
    Both Entrata and MRI LLM fallback runs are documented with pass/fail + unit counts. Final coverage report generated with updated platform distribution.
  </verify>
  <done>
    Entrata and MRI LLM fallback tested on one building each. Full investigation report compiled covering 12-15 buildings across all remaining groups. Updated coverage percentage calculated. Clear next-step strategy documented: which buildings to batch-reclassify, which scrapers to fix, which to abandon.
  </done>
</task>

</tasks>

<verification>
- At least 12 buildings investigated across needs_classification, AppFolio, RealPage, Bozzuto, Entrata, MRI
- Any discovered SightMap/SecureCafe buildings reclassified in moxie.db
- Reclassified buildings validated with validate-building
- Management company patterns documented (which mgmt companies use which platforms)
- Updated coverage percentage calculated
- Actionable next-steps identified for remaining unscraped buildings
</verification>

<success_criteria>
Coverage percentage increases from 75% (306/407) due to needs_classification reclassifications. Each remaining platform group has a clear diagnosis: fix, reclassify, LLM fallback, or skip. Management company patterns are documented so remaining buildings in same groups can be batch-processed.
</success_criteria>

<output>
After completion, create `.planning/quick/4-validate-next-building-groups-needs-clas/4-SUMMARY.md` with:
- Building-by-building results table
- Platform reclassifications applied
- Management company pattern map
- Updated coverage number
- Prioritized next steps for remaining buildings
Also update `.planning/STATE.md` with new coverage numbers and findings.
</output>
