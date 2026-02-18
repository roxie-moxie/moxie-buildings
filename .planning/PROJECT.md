# Moxie Building Aggregator (MBA)

## What This Is

A proprietary web application that scrapes ~400 downtown Chicago rental building websites daily, aggregates per-unit listing data into a private database, and surfaces it as a searchable, filterable interface exclusively for Team Moxie real estate agents. The system automatically classifies scraping strategy per building based on platform type (API, known scraper, or LLM fallback), and syncs its building list from a live Google Sheets source of truth.

## Core Value

Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily — without visiting 400 individual building websites.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Data Collection**
- [ ] Sync building list from Google Sheets (source of truth: ~400 buildings with URL, neighborhood, management company)
- [ ] Scrape RentCafe/Yardi buildings via API (~220 buildings, 55%) — access method TBD, needs investigation
- [ ] Scrape Entrata buildings via API patterns (~30-40 buildings)
- [ ] Scrape PPM buildings via single centralized availability page (ppmapartments.com/availability, ~18 buildings)
- [ ] Scrape Funnel/Nestio buildings (~15-20 buildings, mostly FLATS brand)
- [ ] Scrape RealPage/G5 buildings (~10-15 buildings: AMLI, Magellan, Tandem)
- [ ] Scrape Bozzuto buildings (~13 buildings, custom platform)
- [ ] Scrape Groupfox buildings (~12 buildings, RentCafe variant via /floorplans pages)
- [ ] Scrape AppFolio buildings (~5-10 buildings)
- [ ] Scrape long-tail custom sites (WordPress, Squarespace, ~50-70 buildings) via LLM fallback (Crawl4AI + Claude Haiku)
- [ ] Run all scrapes on a daily schedule
- [ ] On scrape failure: retain last known data, flag building for admin review

**Data Model (per unit)**
- [ ] Store required fields: Unit #, Beds (Studio / Convertible / 1BR / 1BR+Den / 2BR / 3BR / 4BR+), Base monthly rent, Availability date
- [ ] Store default fields: Neighborhood, Building name, Building website URL, Date of last update
- [ ] Store optional fields when available: Floor plan, Baths, Square footage

**Agent Interface**
- [ ] Agents log in with credentials created by admin
- [ ] Agents can search and filter units by bed type, rent range, availability date, neighborhood
- [ ] Agents can export filtered results to share with clients (format TBD — likely PDF and/or spreadsheet)

**Admin Interface**
- [ ] Admin can create and manage agent accounts
- [ ] Admin can view scrape health dashboard (last run, success/failure per building, stale flags)
- [ ] Admin can manually trigger re-scrape for flagged buildings
- [ ] Admin can view and manage building list (synced from Google Sheets)

### Out of Scope

- Real-time / on-demand scraping — daily batch is sufficient
- Client-facing logins — agents use the tool themselves, then export to clients
- Mobile app — web-first
- Manual unit data entry — all data comes from scraping
- Buildings without a website URL — excluded from the spreadsheet and system

## Context

- **Platform research is complete.** Full categorization of all ~400 buildings by scraping platform exists in a separate document. Platform-specific scrapers can be built in parallel.
- **Google Sheets API is already set up.** The building list spreadsheet contains URL, neighborhood, and management company per building.
- **LLM scraping cost is known.** Crawl4AI + Claude Haiku for the long-tail custom sites is estimated at ~$120/month for daily scraping of ~50-70 buildings.
- **RentCafe/Yardi API access is unconfirmed.** The API exists and is the biggest data collection shortcut, but access credentials/method needs investigation before implementation.
- **PPM is a special case shortcut.** All ~18 PPM buildings are covered by a single availability page — one scraper covers all of them.

## Constraints

- **Access**: Proprietary system, login required — not publicly accessible
- **Operating cost**: LLM fallback scraping estimated ~$120/month; acceptable per user
- **Data freshness**: Daily refresh is the target cadence, not real-time
- **Building list**: Managed externally in Google Sheets — MBA must sync, not replace it
- **Yardi API**: Access method unconfirmed — investigation required before implementation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tiered scraping strategy (API → platform scraper → LLM fallback) | Maximizes reliability and minimizes cost — use structured APIs where available, fall back to LLM only for long-tail custom sites | — Pending |
| Google Sheets as ongoing building list source of truth | Team already maintains the sheet; syncing avoids duplicating data management work | — Pending |
| LLM fallback (Crawl4AI + Claude Haiku) for custom sites | Eliminates need to write bespoke scrapers for ~50-70 unique sites; ~$120/month cost is acceptable | — Pending |
| Daily scrape cadence | Rental availability changes daily; weekly is too stale, real-time is unnecessary overhead | — Pending |

---
*Last updated: 2026-02-17 after initialization*
