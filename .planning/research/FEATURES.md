# Feature Research

**Domain:** Internal rental property data aggregator / agent search tool
**Researched:** 2026-02-17
**Confidence:** MEDIUM — core search/filter and export patterns verified across multiple real estate platforms; admin/scrape-monitoring patterns verified from scraping-tool products; some UX specifics are training-data synthesis from evidence

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features agents will assume exist. Missing these = the tool feels broken or incomplete, and agents revert to visiting individual building sites.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Filter by bed type | Primary search dimension for any rental search; all consumer rental platforms (Apartments.com, StreetEasy) lead with bedrooms | LOW | Checkbox group: Studio / Convertible / 1BR / 1BR+Den / 2BR / 3BR / 4BR+ — multi-select, not single-choice |
| Filter by rent range | Price is renters' top consideration (Apartments.com data); agents always screen by budget first | LOW | Min/max inputs or dual-handle slider; show unit count updating in real time as filters change |
| Filter by availability date | Move-in date is hard constraint for clients; without it the tool forces manual date math | LOW | "Available on or before [date]" calendar picker; include "Available now" quick toggle |
| Filter by neighborhood | 400 buildings span multiple Chicago neighborhoods; spatial pre-filtering is mandatory before unit-level search | LOW | Multi-select from enum list (neighborhoods come from Google Sheets source of truth) |
| Tabular results view | Agents scan multiple attributes side-by-side; card views hide data that professionals need visible at once | LOW | Sortable columns: building, unit, beds, rent, available date, last updated |
| Column sort | Agents sort by rent to find cheapest units, or by date to see most recently updated first | LOW | Click-to-sort column headers; default sort by availability date ascending |
| Clear/reset all filters | Power users iterate rapidly across filter states; without reset they manually undo each filter | LOW | Single "Clear filters" button returns to unfiltered view |
| "Last updated" timestamp per building | Agents need to know if data is fresh before trusting it for client conversations | LOW | Show last-scraped date on every building row; visually flag if >48h stale (yellow/red badge) |
| Login / auth | System is private; unauthenticated access is not acceptable per project requirements | LOW | Username + password; no SSO complexity needed for v1; secure session management |
| Secure, private access | No public exposure; agents log in to access all features | LOW | All routes require authenticated session; no public listing pages |

### Differentiators (Competitive Advantage)

Features that make MBA meaningfully better than manually visiting 400 sites. These are why the tool is worth building.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Export filtered results to PDF | Agents share curated unit lists with clients as a professional deliverable; PDF is universal format clients can receive over email/text | MEDIUM | "Export PDF" button on filtered results; include: building name, unit #, beds, baths (if known), sq ft (if known), rent, available date, building URL; clean branded layout |
| Export filtered results to CSV/Excel | Agents who work in spreadsheets can manipulate data further; CSV allows import into CRM tools | LOW | CSV export of current filtered view; straightforward mapping of displayed columns to file |
| Data freshness badge per building | Distinguishes this tool from stale manual notes; builds agent trust in the data | LOW | Color-coded indicator: green (<24h), yellow (24-48h), red (>48h); visible in search results and building detail |
| "Available soon" filter | Clients often need units available within 30/60 days, not just today; proactive search is a workflow unlock | LOW | Availability date filter defaults to "within 60 days"; agents can expand or tighten window |
| Result count with active filters | Agents need to know if a filter combination is too narrow before wasting time scrolling | LOW | Live count: "Showing 47 units across 12 buildings" updates as filters change |
| Building detail page | Agents sometimes want all available units in one building, not just filtered results | MEDIUM | Per-building page: all current units, building website link, scrape status, last updated; accessed from results table |
| Admin scrape health dashboard | Admin can spot broken scrapers before agents notice stale data; proactive rather than reactive | MEDIUM | Per-building status: last run time, success/fail, unit count delta, stale flag; sortable by last-failed or stale age |
| Manual re-scrape trigger (admin) | When a scraper fails, admin can re-run it immediately rather than waiting for next daily batch | LOW | "Re-scrape" button per building in admin view; async execution with status feedback |
| Agent account management (admin) | Admin creates/deactivates agents without needing developer intervention | LOW | Create account (email + temp password), deactivate, reset password — basic CRUD |
| Building list sync from Google Sheets | Building list stays authoritative in the existing team workflow without double-entry | MEDIUM | Admin-triggered or automated daily sync; show last sync time; flag buildings in system not in sheet |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like good ideas but add complexity that outweighs their value for v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Map view of results | Agents think visually about Chicago geography | Requires a maps API (cost + integration), adds significant frontend complexity, and neighborhoods already serve as the geographic proxy filter | Multi-select neighborhood filter; include neighborhood prominently in result rows |
| Client-facing portal / shared links | "Could we send clients a link to see results?" | Complicates auth (public vs. private), adds a separate UX context, and clients should receive a finished deliverable not a live tool — scope creep | PDF export is the right sharing mechanism; agents control what clients see |
| Real-time / on-demand scraping | "Can we refresh a building right now when I need it?" | On-demand scraping during agent sessions creates unpredictable load, infrastructure cost, and user-facing wait time; daily batch covers all data freshness needs | Admin manual re-scrape for genuinely broken buildings; daily cadence is sufficient |
| Favorites / saved searches per agent | "Let me save this filter combination for recurring client" | Requires per-user state persistence, database schema additions, and UI for managing saves — adds significant scope with low immediate payoff | Agents bookmark the URL with filter query params (implement URL-serialized filters from the start) |
| Email/notification alerts for new units | "Notify me when a new unit matching criteria appears" | Requires background diff jobs, email service integration, and notification preferences UI; doubles scope of the data pipeline | Agents run a fresh search daily — daily cadence makes this redundant |
| Historical price / availability trends | "Has this building's rent been going up?" | Requires storing historical snapshots (not just current state), data model redesign, and charting UI — better served by a v2 analytics layer | Show "last updated" date; agents can observe changes informally over time |
| Floor plan images in results | "Show the floor plan image" | Scraping and storing images is bandwidth/storage intensive; not all buildings expose image URLs consistently; adds significant scrape complexity | Include floor plan name/code as text field (already optional in data model); link to building website for images |
| Mobile app | Agents may request a native app | Web app in a mobile browser is sufficient for occasional use; a native app doubles build/maintenance effort for a tool primarily used at desks | Responsive web design so mobile browser works; no native app |
| Natural language search | AI-powered "find me a 2BR under $3000 near the loop" | Impressive but adds LLM API call per search, latency, and prompt engineering work for marginal gain over well-designed filters | Excellent structured filters are the right solution; NLP is a v3 idea if filter UX proves insufficient |
| Bulk unit import / manual entry | "What if we want to add a building manually?" | Contradicts the scraping-as-source-of-truth architecture; creates data consistency problems and maintenance burden | All data comes from scraping; manual entries would never refresh automatically |

---

## Feature Dependencies

```
Auth / Login
    └──required by──> All agent features
    └──required by──> All admin features

Neighborhood filter
    └──requires──> Google Sheets sync (neighborhoods sourced from the sheet)

Filter system (bed, rent, date, neighborhood)
    └──required by──> PDF export (export current filtered view)
    └──required by──> CSV export (export current filtered view)
    └──required by──> Result count display

Google Sheets sync
    └──required by──> Building list in admin
    └──required by──> Neighborhood enum for filter

Scrape jobs (pipeline)
    └──required by──> Scrape health dashboard (admin)
    └──required by──> Data freshness badges (agent view)
    └──required by──> Manual re-scrape trigger (admin)

Building detail page
    └──enhances──> Filter results (drill down from table row)

URL-serialized filters
    └──enables──> Shareable/bookmarkable filter state (soft workaround for saved searches)
```

### Dependency Notes

- **Auth requires nothing** — build first, everything else gates on it
- **Filter system requires scrape data to exist** — data pipeline must land data before filter UI is meaningful
- **PDF/CSV export requires filter system** — export is always of the current filtered view, not a raw dump
- **Scrape health dashboard requires scrape job metadata** — the pipeline must emit run status, timestamps, and per-building counts for the dashboard to display
- **Neighborhood filter requires Google Sheets sync** — the neighborhood values come from the sheet; hard-coding them is an anti-pattern since the sheet is the source of truth
- **Data freshness badges depend on last-scraped timestamp stored per building** — the schema must store `last_scraped_at` from day one

---

## MVP Definition

### Launch With (v1)

Minimum viable product that makes the tool immediately useful and trustworthy for agents.

- [ ] Login / auth — required for any private access
- [ ] Filter panel: bed type (multi-select), rent range (min/max), availability date ("available on or before"), neighborhood (multi-select) — the core value of the tool
- [ ] Sortable results table — bed, rent, available date, building, last updated
- [ ] Data freshness badge — green/yellow/red per building based on last-scraped timestamp
- [ ] CSV export of filtered results — low effort, immediately useful for agents who work in spreadsheets
- [ ] PDF export of filtered results — professional client deliverable; the primary sharing format
- [ ] Admin: agent account management (create, deactivate, reset password)
- [ ] Admin: scrape health dashboard (per-building status, last run, success/fail, stale flag)
- [ ] Admin: manual re-scrape trigger per building
- [ ] Admin: building list view (synced from Google Sheets, shows last sync time)
- [ ] URL-serialized filter state — filters serialize to query params so agents can bookmark or copy URLs

### Add After Validation (v1.x)

Add once v1 is in agents' hands and feedback identifies real friction.

- [ ] Building detail page — useful if agents frequently want to see all units in a single building; validate demand first
- [ ] "Available within N days" quick-select toggle — simplifies the most common date filter pattern if agents request it
- [ ] Scrape health email alerts to admin — currently admin must visit dashboard; alerts reduce time-to-notice for failures
- [ ] Result count display ("47 units across 12 buildings") — low effort quality-of-life if not in v1

### Future Consideration (v2+)

Defer until product-market fit is established.

- [ ] Saved searches / per-agent filter presets — validate whether URL bookmarks are sufficient first
- [ ] Historical availability / rent trend data — requires schema redesign to store snapshots; meaningful after 3-6 months of data exists
- [ ] Floor plan image display — meaningful only after verifying that enough buildings expose structured image URLs
- [ ] Natural language search — validate that structured filters are inadequate first

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth / login | HIGH | LOW | P1 |
| Bed type filter | HIGH | LOW | P1 |
| Rent range filter | HIGH | LOW | P1 |
| Availability date filter | HIGH | LOW | P1 |
| Neighborhood filter | HIGH | LOW | P1 |
| Sortable results table | HIGH | LOW | P1 |
| Data freshness badge | HIGH | LOW | P1 |
| CSV export | HIGH | LOW | P1 |
| PDF export | HIGH | MEDIUM | P1 |
| Admin: agent account management | HIGH | LOW | P1 |
| Admin: scrape health dashboard | HIGH | MEDIUM | P1 |
| Admin: manual re-scrape trigger | MEDIUM | LOW | P1 |
| Admin: building list view | MEDIUM | LOW | P1 |
| URL-serialized filter state | MEDIUM | LOW | P1 |
| Result count display | MEDIUM | LOW | P2 |
| Building detail page | MEDIUM | MEDIUM | P2 |
| "Available soon" quick toggle | MEDIUM | LOW | P2 |
| Scrape health email alerts | MEDIUM | MEDIUM | P2 |
| Saved searches / bookmarks | LOW | HIGH | P3 |
| Historical trend data | LOW | HIGH | P3 |
| Floor plan images | LOW | HIGH | P3 |
| Natural language search | LOW | HIGH | P3 |
| Map view | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

This is an internal proprietary tool, not a consumer product. Relevant comparisons are to internal tools and MLS platforms used by agents, not to Zillow or Apartments.com.

| Feature | Zillow/Apartments.com (consumer) | MLS / BrightMLS (agent) | MBA (our approach) |
|---------|----------------------------------|-------------------------|-------------------|
| Bed/rent/date filters | Yes, consumer-oriented | Yes, professional-grade | Yes — match MLS-grade professionalism |
| Neighborhood filter | Location-centric (map-based) | MLS area codes | Enum from Google Sheets (simpler, fits our 400-building scope) |
| Export for clients | None (send link) | PDF "Client Short" and "Client Long" formats | PDF export of filtered results; CSV for spreadsheet-oriented agents |
| Data freshness visibility | None (scrapes are opaque) | MLS updated timestamp per listing | Explicit freshness badge per building; critical for trust given daily-batch model |
| Scrape/data health monitoring | Not visible to users | Not applicable (agent-submitted data) | Admin dashboard — this is a key internal operational need |
| Admin account management | Not applicable | Broker-level controls | Simple CRUD — create/deactivate agents |
| Coverage | National / market-driven | MLS members only | All 400 downtown Chicago buildings — more complete than any public source for this market |

---

## Sources

- [Apartments.com — search filter patterns and availability date filtering](https://renterhelp.apartments.com/article/752-how-can-i-maximize-the-search-on-apartments-com)
- [StreetEasy — how to use apartment search filters](https://streeteasy.com/blog/how-to-find-apartments-for-rent/)
- [Propertyshelf — PDF report types for agent/client sharing](https://propertyshelf.com/en/tools/mls-agent-tools/sharing-listings-via-pdf-reports)
- [ScrapeOps — scraper monitoring dashboard features](https://scrapeops.io/monitoring-scheduling/)
- [Eleken — filter UI design patterns for SaaS](https://www.eleken.co/blog-posts/filter-ux-and-ui-for-saas)
- [Insaim Design — filter UI best practices](https://www.insaim.design/blog/filter-ui-design-best-ux-practices-and-examples)
- [Palantir Foundry — data freshness widget pattern](https://www.palantir.com/docs/foundry/workshop/widgets-data-freshness)
- [Smashing Magazine — UX strategies for real-time dashboards (2025)](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/)
- [Tenscope — table UX best practices](https://www.tenscope.com/post/table-ux-best-practices)
- [DealCheck — export to CSV and Excel for property data](https://dealcheck.io/blog/export-property-data-csv-excel/)

---

*Feature research for: Internal rental property data aggregator (Moxie Building Aggregator)*
*Researched: 2026-02-17*
