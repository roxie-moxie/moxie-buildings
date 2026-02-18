# Moxie Buildings — Project Specification

## Overview

Build a system that scrapes unit-level apartment availability from ~400 Chicago rental building websites daily, stores the data, and serves it through a webapp where real estate agents can filter, sort, and generate client-ready availability lists.

This replaces a painful manual process: agents currently visit individual building websites one at a time to pull pricing for clients. This takes 1-2 hours daily and is the team's biggest time sink.

---

## The Business

- **Moxie** is a luxury real estate team in Downtown Chicago (brokerage: Compass)
- ~7 agents, led by Caira, focused on rentals + sales
- ~44 active rental clients at any time, ~14 active sales clients
- Agents need to send clients current availability for specific neighborhoods/building types daily
- The **Moxie Buildings Spreadsheet** tracks ~400+ managed rental buildings with metadata (name, address, neighborhood, management company, URL, etc.)

---

## What We're Building

### Component 1: The Scraper Pipeline

A daily automated pipeline that:

1. Reads the building registry (list of buildings + their URLs + platform type)
2. For each building, fetches current unit-level availability
3. Normalizes the data into a standard schema
4. Stores it (database or structured files)
5. Logs successes, failures, and quality metrics

### Component 2: The Webapp

A web application where agents can:

1. Filter buildings by neighborhood, size category, price range, availability date
2. Sort results by any column
3. Select specific buildings/units
4. Export a client-ready formatted list (copy-paste or PDF)

---

## Data Model

### Building Registry

Each building has:

| Field | Description | Example |
|-------|-------------|---------|
| building_id | Internal ID | BLD-0031 |
| name | Building name | Axis Apartments |
| address | Street address | 1130 S Michigan Ave |
| neighborhood | Chicago neighborhood | South Loop |
| management_company | Property manager | Waterton |
| url | Building website | https://axisapts.com |
| platform | Detected rental platform | rentcafe |
| rentcafe_property_id | RentCafe API property ID (if applicable) | p12345 |
| rentcafe_api_token | RentCafe API token (if applicable) | abc123 |
| scraper_quality | Quality label | ✅ Validated |

### Unit Availability (scraped daily)

Each available unit:

| Field | Description | Example |
|-------|-------------|---------|
| building_id | FK to building | BLD-0031 |
| unit_number | Unit identifier | 1204 |
| size_category | Standardized type | Studio |
| sqft | Square footage | 450 |
| rent | Monthly rent ($) | 1650 |
| available_date | When available | 3/15 or "Now" |
| floor_plan | Floor plan name (if given) | Studio A |
| scraped_at | Timestamp of scrape | 2026-02-17T08:00:00Z |

### Standardized Size Categories

- Studio
- Convertible
- One Bed
- One Bed + Den
- Two Bed
- Three Bed
- Four Bed+

---

## Scraping Strategy (Tiered)

Research identified that buildings fall into distinct platform categories. The scraping strategy is tiered by platform:

### Tier 1: RentCafe/Yardi Direct API (~280-310 buildings, ~55%)

**This is the #1 priority and biggest win.**

RentCafe exposes an undocumented but well-understood API:

```
GET/POST https://api.rentcafe.com/rentcafeapi.aspx
  ?requestType=apartmentavailability
  &propertyId=<id>
  &apiToken=<token>
```

Returns clean JSON:
```json
[
  {
    "FloorplanName": "Studio A",
    "ApartmentName": "Unit 1204",
    "Beds": "0",
    "Baths": "1",
    "SQFT": "450",
    "MinimumRent": "1650.00",
    "MaximumRent": "1650.00",
    "AvailableDate": "03/15/2026"
  }
]
```

**Discovery process:** For each RentCafe building, visit the website once, extract `propertyId` and `apiToken` from the page source/JavaScript. These are embedded in widget code or AJAX configurations. Store them in the building registry. Then daily scraping is just simple HTTP calls — no HTML parsing needed.

**Key management companies on RentCafe:** Reside (38), Greystar (24), Willow Bridge (23), Horizon (16), Waterton (7), Village Green (4), Habitat (4), Related (3), Marquette (5), and many more.

### Tier 2: LLM-Based Extraction (~80-100 buildings, fallback)

For non-RentCafe buildings without a known API pattern, use:

1. A headless browser or crawler to fetch the building's availability page
2. Extract clean text/markdown from the page
3. Pass to a cheap LLM (Claude Haiku or GPT-4o-mini) with a structured extraction prompt
4. Parse the LLM output into the standard unit schema

Estimated cost: ~$0.01-0.02 per page → ~$120/month for 180 buildings daily.

### Tier 3: Platform-Specific Scrapers

Some platforms have enough buildings to justify dedicated scrapers:

| Platform | Buildings | Status |
|----------|-----------|--------|
| Entrata | ~30-40 | Needs scraper (has own API patterns) |
| Groupfox | ~12 | ✅ POC built |
| PPM | ~18 | ✅ POC built (single centralized page) |
| Bozzuto | ~13 | Needs scraper |
| RealPage/G5 | ~10-15 | Needs scraper |
| Funnel/Nestio | ~15-20 | Needs scraper |
| AppFolio | ~5-10 | Needs scraper |

### Dead Ends (~134 buildings)

- ~134 buildings have no website URL at all
- Some buildings show "Call for details" / "Inquire" with no pricing online
- These are excluded from automated scraping; marked in the registry

---

## Business Rules

These were established during POC validation:

1. **"Call for pricing" = skip** — unit is not actually available, don't include
2. **Date format:** MM/DD or MM/DD/YYYY. "Now" stays as "Now". Convert "Mar. 07" → "3/7"
3. **Size category mapping:** Map floor plan names to standardized categories (Studio, One Bed, etc.)
4. **Scraper quality labels per building:**
   - ✅ Validated — scraped and human-verified
   - 🔍 Needs Validation — scraped, awaiting review
   - ⏳ Fully leased / no availability — untested
   - ❌ No data / Call for details — can't scrape
5. **Concessions/specials:** Extract if available, but not critical for MVP

---

## Google Sheets Integration

The existing Moxie workflow lives in Google Sheets. The system needs to read from and write to Sheets:

- **Read:** Building registry (names, URLs, metadata) from the Moxie Buildings Spreadsheet
- **Write:** Scraped availability data back to a sheet (or database that syncs to sheets)

**Existing service account:** `roxie-sheets@moxie-roxie.iam.gserviceaccount.com`
- Credentials file exists (JSON key)
- Alex shares copies of sheets with the service account
- Libraries: `googleapis` (Node.js) tested and working

**Current test sheet:** Moxie Buildings 2.0 beta (`1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI`)

---

## Architecture Recommendations

### Suggested Pipeline Flow

```
┌────────────────────────────────────────────────────┐
│           Building Registry (400+ buildings)        │
│  name | url | platform | property_id | api_token    │
└──────────────────┬─────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
┌─────────────┐     ┌───────────────────┐
│ RentCafe    │     │ LLM / Platform    │
│ API Client  │     │ Scrapers          │
│             │     │                   │
│ Direct JSON │     │ Crawl → Extract   │
│ ~280 bldgs  │     │ ~120 bldgs        │
└──────┬──────┘     └────────┬──────────┘
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
       ┌──────────────────┐
       │  Normalized Data  │
       │  Store (DB/files) │
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │     Webapp        │
       │  Filter / Sort    │
       │  Export lists     │
       └──────────────────┘
```

### Key Technical Decisions (Open — For You to Decide)

1. **Language/runtime** — Node.js, Python, or other. Research and POCs were in Node.js but no commitment.
2. **Database** — SQLite (simple, file-based), PostgreSQL (more robust), or even just JSON files for MVP
3. **Webapp framework** — Next.js, SvelteKit, plain HTML, etc.
4. **Hosting** — Where the scraper runs daily and where the webapp is served
5. **Headless browser** — Playwright vs Puppeteer for sites that need JS rendering

---

## Development Phases

### Phase 1: RentCafe API Foundation
- Build the RentCafe API client
- Create a discovery script to extract propertyId + apiToken from RentCafe building websites
- Run discovery across all ~280 known RentCafe buildings
- Store credentials in the building registry
- Test daily scraping for the RentCafe buildings
- **Success metric:** Clean availability data for 200+ buildings via API

### Phase 2: Expand Platform Coverage
- Build LLM extraction fallback for non-RentCafe buildings
- Build platform-specific scrapers where justified (Entrata, Bozzuto, etc.)
- Classify remaining unidentified buildings
- **Success metric:** Coverage for 350+ buildings

### Phase 3: Webapp
- Build the filtering/sorting interface
- Client-ready export (formatted list, PDF, etc.)
- Connect to the scraped data store
- **Success metric:** Agents can generate a client availability list in <2 minutes

### Phase 4: Automation & Monitoring
- Daily cron job for scraping
- Alerting on failures (buildings that stop returning data)
- Historical tracking (price trends, availability patterns)
- VPN/proxy rotation for bot detection avoidance

---

## Reference Data

The `docs/` folder contains detailed research and validation notes:

- **RESEARCH-REPORT.md** — Deep dive on RentCafe API patterns, LLM scraping tools, Chicago-specific data sources, ILS feeds, open source scrapers, and cost analysis
- **PLATFORM-REPORT.md** — Complete categorization of all ~544 buildings by platform, management company → platform mapping, and scraper priority order
- **SCRAPER-NOTES.md** — POC validation notes, platform quirks, business rules, bug list, and architecture notes from building-by-building testing

---

## Credentials & Access

- **GitHub:** `roxie-moxie` — repo owner
- **Google Sheets API:** Service account `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` (credentials JSON needed locally)
- **Google Sheet ID (test):** `1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI`
