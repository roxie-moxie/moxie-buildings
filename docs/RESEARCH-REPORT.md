# Moxie Buildings Scraper — Research Report

**Date:** 2026-02-16  
**Goal:** Extract unit-level apartment availability data (unit #, rent, availability date, sqft) from ~400 Chicago apartment building websites. 55%+ use the RentCafe/Yardi platform.

---

## 1. RentCafe/Yardi API Patterns

### Known API Endpoints

RentCafe (owned by Yardi Systems) exposes several undocumented/semi-documented API endpoints that return structured data. These are the primary patterns discovered through reverse-engineering:

#### a) `rentcafeapi.com` Endpoints

The main API base appears to be `https://api.rentcafe.com/rentcafeapi.aspx` (or variations). Key parameters:

```
POST https://api.rentcafe.com/rentcafeapi.aspx
Content-Type: application/x-www-form-urlencoded

requestType=apartmentavailability
&apiToken=<token>
&propertyId=<id>
```

**Request Types observed:**
- `apartmentavailability` — Returns available units with rent, sqft, availability date, unit number, floor plan name
- `floorplan` — Returns floor plan details (name, beds, baths, sqft range, rent range)
- `property` — Returns property metadata (address, phone, amenities)
- `apartmentmatch` — Used by "apartment matcher" widget

**Key parameters:**
- `propertyId` — Numeric property ID (visible in page source or URL)
- `apiToken` — Often embedded in the page's JavaScript or widget embed code. Some properties use a public/shared token.
- `companyCode` — Alternative to propertyId for company-wide queries

#### b) `securecafe.com` / Direct Property Sites

Many buildings have their own branded RentCafe site (e.g., `mybuildingname.securecafe.com` or a custom domain). These use:

```
GET https://<property>.securecafe.com/onlineleasing/<property>/floorplans.aspx
GET https://<property>.securecafe.com/onlineleasing/<property>/guestlogin.aspx
```

The `floorplans.aspx` page renders HTML but the underlying data is fetched via AJAX calls to endpoints like:
```
POST /onlineleasing/<property>/LeadManagement/GetFloorPlansAndUnits
```

This returns JSON with unit-level data when called with the right headers.

#### c) Widget/Syndication API

RentCafe's embeddable widgets call:
```
https://api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability&propertyId=<id>&apiToken=<token>
```

The response is JSON containing an array of available units:
```json
[
  {
    "PropertyId": "p12345",
    "FloorplanName": "Studio A",
    "FloorplanId": "fp001",
    "ApartmentName": "Unit 1204",
    "Beds": "0",
    "Baths": "1",
    "SQFT": "450",
    "MinimumRent": "1650.00",
    "MaximumRent": "1650.00",
    "AvailableDate": "03/15/2026",
    "UnitImageURLs": [...],
    "FloorplanImageURL": "...",
    "AvailabilityURL": "...",
    "Amenities": "..."
  }
]
```

### How to Get Property IDs and API Tokens

- **Property ID**: Found in page source HTML, usually in a JavaScript variable like `propertyId`, in meta tags, or in the URL structure
- **API Token**: Embedded in widget JavaScript, often in a `<script>` tag or AJAX configuration. Some buildings share a common token per management company
- **Discovery approach**: Load a RentCafe property page, inspect the Network tab for XHR calls to `rentcafeapi.com` — the propertyId and token are in the request

### Assessment

**This is the #1 approach for 55%+ of your buildings.** If a building uses RentCafe, you can likely hit `api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability` with the correct propertyId and apiToken to get clean JSON. No HTML parsing needed.

**Challenges:**
- Need to discover propertyId + apiToken for each of ~220 RentCafe buildings (one-time manual or semi-automated task)
- RentCafe has Cloudflare protection on main site (rentcafe.com returns 403 to scrapers), but the API endpoint (`api.rentcafe.com`) may be less protected since widgets need to call it from browsers
- API tokens could rotate, though they appear relatively stable
- Rate limiting is unknown but likely lenient for moderate request volumes

**Sources:**
- [PeterYuan1986/Rentcafe-web-scraper](https://github.com/PeterYuan1986/Rentcafe-web-scraper) — Python scraper for RentCafe
- [tarekrahman3/rentcafe.com-scraper-python](https://github.com/tarekrahman3/rentcafe.com-scraper-python) — Another Python scraper
- Network traffic analysis of RentCafe widget embed codes

---

## 2. RentCafe Widget Data Source

### How the Widget Works

RentCafe provides embeddable "Apartment Availability" widgets that property managers place on their websites. These widgets are loaded via JavaScript and make client-side API calls to populate themselves.

#### Widget Embed Pattern

Typical embed code:
```html
<script src="https://www.rentcafe.com/widgetHandler/WidgetLoader.ashx?id=<widgetId>&type=apartmentavailability"></script>
```

Or newer pattern:
```html
<div id="rentcafe-widget" data-property-id="12345" data-token="abc123"></div>
<script src="https://cdn.rentcafe.com/widget/v2/availability.js"></script>
```

#### Data Fetching

The widget JavaScript makes AJAX calls to:
```
https://api.rentcafe.com/rentcafeapi.aspx
```

With parameters:
- `requestType=apartmentavailability`
- `propertyId=<from embed config>`
- `apiToken=<from embed config>`

The response is the same JSON structure described in Section 1.

### Practical Implication

**You don't need to scrape the widget** — you can call the same API endpoint directly. The widget is just a JavaScript frontend that consumes the API. Once you have the propertyId and apiToken (extractable from the widget embed code on any property's website), you can call the API yourself.

### Discovery Strategy

1. For each building URL, fetch the HTML
2. Look for patterns: `propertyId`, `apiToken`, `rentcafe`, `rentcafeapi`, `widgetHandler`
3. Extract the IDs from JavaScript/HTML
4. Call `api.rentcafe.com/rentcafeapi.aspx` directly

This could be semi-automated: scrape each building's homepage once to extract RentCafe credentials, then use the API going forward.

---

## 3. Universal/LLM-Based Scraping

For the ~45% of buildings NOT on RentCafe, we need a more general approach. LLM-based scraping is the most promising "universal" solution.

### Tools Evaluated

#### a) Firecrawl (`/extract` endpoint)

- **How it works:** Send URL(s) + a prompt/schema describing what you want. Firecrawl crawls the page, extracts markdown, and sends it to an LLM to extract structured data.
- **Schema support:** Define a JSON schema for output (unit number, rent, sqft, availability date)
- **Pricing:** Credit-based (each credit = 15 tokens). For a single page extraction, roughly $0.01-0.05 per page depending on page size.
- **Reliability:** Good for well-structured pages. May struggle with heavily JavaScript-rendered pages unless using their browser rendering mode.
- **Batch capability:** Supports wildcards (`example.com/*`) for multi-page extraction
- **New "Agent" mode:** Their `/agent` endpoint can autonomously navigate and find data without specifying exact URLs
- **Source:** [docs.firecrawl.dev/features/extract](https://docs.firecrawl.dev/features/extract)

#### b) ScrapeGraphAI

- **How it works:** Open-source Python library that uses LLMs + graph logic to create scraping pipelines. "Just say which information you want to extract."
- **Key class:** `SmartScraperGraph` — give it a URL and a prompt, it returns structured data
- **LLM support:** Works with OpenAI, Anthropic, local models (Ollama), etc.
- **Pricing:** Only LLM API costs (no additional fees for OSS version). Roughly $0.01-0.03 per page with GPT-4o-mini or Claude Haiku.
- **Hosted version:** Also available at scrapegraphai.com as a paid API
- **Source:** [github.com/ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) — 20k+ stars

#### c) Crawl4AI

- **How it works:** Open-source (#1 trending on GitHub), LLM-friendly web crawler. Generates clean markdown from web pages, supports CSS/XPath extraction AND LLM-based extraction.
- **Key features:** Browser automation (Playwright), stealth mode, session management, adaptive crawling
- **LLM extraction:** Can pass crawled content to any LLM for structured extraction
- **Pricing:** Free (open source). Only LLM API costs.
- **Best for:** Getting clean HTML/markdown that you then process yourself
- **Source:** [docs.crawl4ai.com](https://docs.crawl4ai.com)

#### d) Browser-Use

- **How it works:** AI agent that controls a real browser. Can navigate, click, scroll, and extract data.
- **Use case:** Sites with complex JavaScript interactions, login walls, infinite scroll
- **Pricing:** LLM API costs (higher due to multi-step reasoning)
- **Overkill for:** Static availability pages

### Cost Analysis for LLM Extraction (400 buildings, daily)

| Approach | Cost/page | Daily cost (400 pages) | Monthly cost |
|----------|-----------|----------------------|--------------|
| Claude Haiku + Crawl4AI | ~$0.01 | ~$4 | ~$120 |
| GPT-4o-mini + ScrapeGraphAI | ~$0.02 | ~$8 | ~$240 |
| Firecrawl Extract | ~$0.03-0.05 | ~$12-20 | ~$360-600 |
| Claude Sonnet + manual | ~$0.05 | ~$20 | ~$600 |

### Assessment

LLM-based scraping is viable as a **fallback** for non-RentCafe sites. It's not ideal as the primary approach because:
- Cost adds up at scale (vs. free API calls for RentCafe)
- Reliability is ~90-95% per page (occasional extraction errors)
- Speed is slower (2-5 seconds per page vs. <1 second for API calls)

**Best strategy:** Use Crawl4AI to fetch clean HTML, then pass to Claude Haiku with a structured extraction prompt. This gives you the most control and lowest cost.

---

## 4. Chicago-Specific Rental Data Sources

### Investigated Sources

#### a) Chicago MLSNI / MRED (MLS)

The Midwest Real Estate Data LLC (MRED) operates the MLS for Chicago. However:
- MLS primarily covers for-sale properties
- Rental listings on MLS are sparse and mainly for smaller landlords
- Requires broker access (not publicly available)

#### b) Chicago Housing Authority (CHA)

- Maintains waitlists and affordable housing data
- Not relevant for market-rate apartment availability

#### c) CoStar / Apartments.com

- CoStar (owner of Apartments.com) has the most comprehensive national database
- **Apartments.com does have significant Chicago inventory** — but their data is behind their platform
- No public API. Scraping is against TOS and they actively block it
- An Apartments.com Chrome extension scraper exists: [njraladdin/chrome-extension-appartments-com-scraper](https://github.com/njraladdin/chrome-extension-appartments-com-scraper) — extracts unit #, price, sqft, availability date. But it's manual/semi-manual.

#### d) Domu (domu.com)

- Chicago-specific apartment listing site
- Has some inventory but not comprehensive for larger buildings
- Could be scraped as supplementary source

#### e) Chicago Cityscape

- Focuses on development/zoning data, not unit-level availability

#### f) HotPads / Zillow

- Zillow Group properties. Partial Chicago coverage.
- Zillow has a research API but not unit-level real-time availability

### Assessment

**No silver bullet exists for Chicago-specific data.** The data lives primarily in:
1. Individual building websites (RentCafe et al.) — which is why we're building the scraper
2. Aggregators like Apartments.com and Zillow — which don't provide API access
3. ILS feeds (see Section 5) — which are B2B and not publicly accessible

The building-by-building scraping approach is fundamentally the right one.

---

## 5. ILS (Internet Listing Service) Feeds

### What Are ILS Feeds?

Property management companies push unit availability data to listing sites (Apartments.com, Zillow, etc.) using standardized feeds. The dominant standard is **MITS (Multifamily Information and Transactions Standard)**, maintained by the National Multifamily Housing Council (NMHC) and National Apartment Association (NAA).

### MITS Format

MITS is an XML schema that includes:
- Property information (name, address, amenities)
- Floor plans (name, beds, baths, sqft)
- Individual units (unit number, rent, availability date, sqft, floor)
- Photos, virtual tours, etc.

Example MITS XML structure:
```xml
<PhysicalProperty>
  <Property>
    <PropertyID>
      <Identification IDType="ApartmentID" IDValue="12345"/>
    </PropertyID>
    <Floorplan>
      <Name>Studio A</Name>
      <Room RoomType="Bedroom" Count="0"/>
      <SquareFeet Min="450" Max="450"/>
      <MarketRent Min="1650" Max="1800"/>
      <Unit>
        <Identification IDType="UnitID" IDValue="1204"/>
        <UnitRent>1650</UnitRent>
        <UnitAvailabilityDate>2026-03-15</UnitAvailabilityDate>
        <SquareFootage>450</SquareFootage>
      </Unit>
    </Floorplan>
  </Property>
</PhysicalProperty>
```

### Accessibility

**ILS feeds are NOT publicly accessible.** They are:
- B2B feeds sent from PMS (Yardi, Entrata, RealPage, AppFolio) → ILS (Apartments.com, Zillow, etc.)
- Transmitted via SFTP, API, or direct integration
- Protected by commercial agreements
- Not exposed via public URLs

**However**, there are angles:
- Yardi's RentCafe *is* effectively an ILS endpoint — the `rentcafeapi.aspx` API returns the same data that would be in a MITS feed
- Some smaller PMSes expose feeds at predictable URLs (rare)
- If you could partner with or license data from an ILS aggregator, you'd get everything in one feed

### Assessment

**Not a viable direct approach** unless you can establish business relationships with ILS providers or property management companies. The RentCafe API approach (Section 1) effectively gives you the same data for RentCafe properties.

---

## 6. Existing Open Source Apartment Scrapers

### RentCafe-Specific

| Project | Approach | Notes |
|---------|----------|-------|
| [PeterYuan1986/Rentcafe-web-scraper](https://github.com/PeterYuan1986/Rentcafe-web-scraper) | Python, likely Selenium/BS4 | Scrapes rentcafe.com listings |
| [tarekrahman3/rentcafe.com-scraper-python](https://github.com/tarekrahman3/rentcafe.com-scraper-python) | Python | RentCafe.com scraper |
| [hassanlabs/average-rent-scraper](https://github.com/hassanlabs/average-rent-scraper) | Python, Selenium + BS4 | Calculates avg rent/sqft from RentCafe |

### General Apartment Scrapers

| Project | Approach | Notes |
|---------|----------|-------|
| [njraladdin/chrome-extension-appartments-com-scraper](https://github.com/njraladdin/chrome-extension-appartments-com-scraper) | Chrome Extension, JS | Extracts unit #, price, sqft, availability from Apartments.com. **Most relevant to our use case.** |
| [knakamura13/apartment-availability-scraper](https://github.com/knakamura13/apartment-availability-scraper) | Python | Generic apartment availability monitoring |
| [michaeltoth/VenueApartmentScraper](https://github.com/michaeltoth/VenueApartmentScraper) | Python | Scrapes specific complexes, emails on new listings |
| [prajyotgupta/apartment_scraper](https://github.com/prajyotgupta/apartment_scraper) | Python | Monitors availability for specific unit types every 30 min |

### Common Approaches Used

1. **Selenium + BeautifulSoup** — Most common. Use Selenium to render JavaScript, then BS4 to parse HTML. Works but slow and brittle.
2. **Requests + BS4** — For server-rendered pages. Faster but can't handle JS-heavy sites.
3. **Chrome Extensions** — Run in the browser context, bypass many anti-bot measures. Not scalable for automated pipelines.
4. **Direct API calls** — The Apartments.com scraper hints at finding underlying API endpoints rather than parsing HTML.

### Key Takeaway

None of the existing open source scrapers operate at the scale we need (400 buildings). They're all one-off scripts for 1-5 specific properties. **We need to build our own system**, but we can learn from their approaches.

---

## 7. Recommendations — Ranked by Feasibility

### 🥇 Tier 1: RentCafe API Direct Calls (RECOMMENDED PRIMARY)

**Covers: ~55% of buildings (220+)**

- Call `api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability` with propertyId + apiToken
- Returns clean JSON with exactly the fields we need
- **One-time setup:** Build a discovery script that visits each RentCafe building's website, extracts propertyId and apiToken from page source
- **Ongoing:** Simple HTTP GET requests, easily parallelized, minimal infrastructure
- **Risk:** API token changes, rate limiting, Cloudflare blocking
- **Effort:** Medium (discovery phase), then Low (ongoing)
- **Cost:** Essentially free (just HTTP requests)

### 🥈 Tier 2: Crawl4AI + Claude Haiku Extraction (RECOMMENDED FALLBACK)

**Covers: ~45% of buildings (non-RentCafe) + any RentCafe failures**

- Use Crawl4AI (open source) to fetch and render each building's availability page
- Pass the clean markdown/HTML to Claude Haiku with a structured extraction prompt
- Define a consistent output schema: `{unit, rent, sqft, available_date, beds, baths}`
- **Effort:** Medium (prompt engineering, testing across diverse sites)
- **Cost:** ~$4/day for 180 buildings = ~$120/month
- **Reliability:** ~90-95% per extraction (need monitoring + manual review)

### 🥉 Tier 3: Platform-Specific Scrapers for Major Non-RentCafe Platforms

**Covers: Buildings on Entrata, AppFolio, RealPage**

- Identify which other platforms are common among the remaining ~180 buildings
- Build targeted scrapers for each platform (similar to the RentCafe API approach — find their API patterns)
- Entrata has its own API endpoints; AppFolio and RealPage may as well
- **Effort:** High (reverse-engineering each platform)
- **Cost:** Free (API calls)

### 🏅 Tier 4: Firecrawl or ScrapeGraphAI (ALTERNATIVE TO TIER 2)

- Managed services that handle rendering + extraction
- Higher cost but lower development effort
- Good option if Crawl4AI + custom extraction proves unreliable
- **Cost:** ~$360-600/month

### ❌ Not Recommended

- **ILS Feeds** — Not publicly accessible, requires business relationships
- **Chicago-specific aggregators** — None have comprehensive data
- **Browser-Use / Full agent** — Overkill and expensive for availability pages
- **Apartments.com scraping** — Against TOS, actively blocked, and we want direct building data anyway

---

## 8. Suggested Architecture

```
┌──────────────────────────────────────────────────┐
│              Building Registry (400 buildings)    │
│  building_name | url | platform | property_id     │
│  platform: rentcafe | entrata | appfolio | other  │
└──────────────┬───────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
┌────────────┐    ┌──────────────┐
│ RentCafe   │    │ LLM Scraper  │
│ API Client │    │ (Crawl4AI +  │
│            │    │  Claude)     │
│ Direct JSON│    │              │
│ ~220 bldgs │    │ ~180 bldgs   │
└─────┬──────┘    └──────┬───────┘
      │                  │
      └────────┬─────────┘
               │
               ▼
    ┌──────────────────┐
    │  Unified Output  │
    │  unit, rent,     │
    │  sqft, avail,    │
    │  building_id     │
    └──────────────────┘
```

## 9. Next Steps

1. **Validate RentCafe API** — Pick 5 known RentCafe buildings, manually extract propertyId + apiToken, test the `apartmentavailability` API call
2. **Build property ID discovery** — Script to visit each building URL, detect if it's RentCafe, extract credentials
3. **Prototype LLM extraction** — Set up Crawl4AI, test Claude Haiku extraction on 10 diverse non-RentCafe buildings
4. **Classify the 400 buildings** — Determine which platform each uses (RentCafe, Entrata, custom, etc.)
5. **Build the pipeline** — RentCafe API client + LLM fallback + unified data model
