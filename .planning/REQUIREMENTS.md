# Requirements: Moxie Building Aggregator (MBA)

**Defined:** 2026-02-17
**Core Value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: System reads building list from Google Sheets and syncs records (building name, URL, neighborhood, management company) to the local database
- [ ] **INFRA-02**: All scrapes run automatically on a daily scheduled basis without manual intervention
- [ ] **INFRA-03**: On scrape failure, last known unit data is retained and the building is marked as stale

### Data Model

- [ ] **DATA-01**: Each unit record stores required fields: Unit #, Beds (Studio / Convertible / 1BR / 1BR+Den / 2BR / 3BR / 4BR+), Base monthly rent, Availability date, Neighborhood, Building name, Building website URL, Date of last scrape
- [ ] **DATA-02**: Unit records store optional fields when source provides them: Floor plan, Number of baths, Square footage
- [ ] **DATA-03**: Unit data from all platforms is normalized to the canonical format before storage (no platform-specific raw values in the database)

### Scraping — Tier 1 (REST APIs)

- [ ] **SCRAP-01**: Yardi/RentCafe buildings (~220 buildings, 55%) scraped via API — access method requires a spike investigation before implementation
- [ ] **SCRAP-02**: Entrata buildings (~30-40 buildings) scraped via Entrata's modernized API gateway (legacy gateway deprecated April 2025)
- [ ] **SCRAP-03**: PPM buildings (~18 buildings) scraped via the single centralized availability page at ppmapartments.com/availability — one scraper covers all PPM buildings

### Scraping — Tier 2 (Platform HTML)

- [ ] **SCRAP-04**: Funnel/Nestio buildings (~15-20 buildings) scraped via platform-specific HTML scraper
- [ ] **SCRAP-05**: RealPage/G5 buildings (~10-15 buildings) scraped via platform-specific HTML scraper
- [ ] **SCRAP-06**: Bozzuto buildings (~13 buildings) scraped via platform-specific HTML scraper
- [ ] **SCRAP-07**: Groupfox buildings (~12 buildings) scraped via /floorplans HTML pages
- [ ] **SCRAP-08**: AppFolio buildings (~5-10 buildings) scraped via platform-specific HTML scraper

### Scraping — Tier 3 (LLM Fallback)

- [ ] **SCRAP-09**: Long-tail custom sites (WordPress, Squarespace, ~50-70 buildings) scraped via Crawl4AI + Claude Haiku with HTML-to-markdown preprocessing to control token cost

### Agent Interface

- [ ] **AGENT-01**: Agent can log in with credentials created by an admin
- [ ] **AGENT-02**: Agent can filter units by bed type (multi-select: Studio, Convertible, 1BR, 1BR+Den, 2BR, 3BR, 4BR+)
- [ ] **AGENT-03**: Agent can filter units by rent range (min and/or max monthly rent)
- [ ] **AGENT-04**: Agent can filter units by availability date ("available on or before" a selected date)
- [ ] **AGENT-05**: Agent can filter units by neighborhood (multi-select from canonical list)
- [ ] **AGENT-06**: Agent can sort results by any column (rent, availability, building name, neighborhood)
- [ ] **AGENT-07**: Agent can see a data freshness indicator per building (timestamp of last successful scrape)

### Admin Interface

- [ ] **ADMIN-01**: Admin can create new agent accounts (name, email, password)
- [ ] **ADMIN-02**: Admin can disable or deactivate agent accounts
- [ ] **ADMIN-03**: Admin can view the full building list as synced from Google Sheets (name, URL, neighborhood, management company, scraper type)
- [ ] **ADMIN-04**: Admin can manually trigger a re-scrape for a specific building and see when it completes

## v2 Requirements

### Export

- **EXPORT-01**: Agent can export a filtered result set as a PDF to share with clients
- **EXPORT-02**: Agent can export a filtered result set as a CSV or Excel spreadsheet

### Scrape Monitoring

- **MON-01**: Admin can view per-building scrape history (run timestamps, success/fail, unit count delta)
- **MON-02**: Admin receives a notification when a building has been stale for more than N days

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time / on-demand scraping | Daily batch is sufficient; real-time adds significant infrastructure complexity |
| Client-facing login portal | Agents share results with clients via export; no client accounts needed |
| Mobile app | Web-first; mobile deferred indefinitely |
| Manual unit data entry | All unit data comes from scraping; manual entry creates data quality risk |
| Map / geographic view | Neighborhood multi-select handles geographic filtering without maps API cost |
| Saved searches (per user) | URL-serialized query params provide bookmark behavior without per-user state complexity |
| Buildings without a website URL | Not included in the Google Sheets source; no URL means no scraping |

## Traceability

*Populated during roadmap creation.*

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| DATA-01 | — | Pending |
| DATA-02 | — | Pending |
| DATA-03 | — | Pending |
| SCRAP-01 | — | Pending |
| SCRAP-02 | — | Pending |
| SCRAP-03 | — | Pending |
| SCRAP-04 | — | Pending |
| SCRAP-05 | — | Pending |
| SCRAP-06 | — | Pending |
| SCRAP-07 | — | Pending |
| SCRAP-08 | — | Pending |
| SCRAP-09 | — | Pending |
| AGENT-01 | — | Pending |
| AGENT-02 | — | Pending |
| AGENT-03 | — | Pending |
| AGENT-04 | — | Pending |
| AGENT-05 | — | Pending |
| AGENT-06 | — | Pending |
| AGENT-07 | — | Pending |
| ADMIN-01 | — | Pending |
| ADMIN-02 | — | Pending |
| ADMIN-03 | — | Pending |
| ADMIN-04 | — | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 0
- Unmapped: 26 ⚠️

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after initial definition*
