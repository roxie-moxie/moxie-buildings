# Platform Categorization Report

**Date:** 2026-02-16  
**Total Buildings in Sheet:** 544  
**Buildings with URLs:** ~410  
**Management Companies Identified:** 63+  

---

## Executive Summary

The ~544 Chicago apartment buildings break down into **6 major rental platforms** plus several minor/custom ones. **RentCafe/Yardi dominates** with an estimated 55-60% of all buildings, making it the clear priority for scraper development.

---

## Platform → Building Count Estimates

| Platform | Est. Buildings | % of Total | Scraper Status |
|----------|---------------|------------|----------------|
| **RentCafe/Yardi** | ~280-310 | ~55% | 🔧 Needs scraper |
| **Entrata** | ~30-40 | ~7% | 🔧 Needs scraper |
| **Groupfox** | ~12 | ~2% | ✅ Built |
| **PPM Custom** | ~18 | ~3% | ✅ Built |
| **Bozzuto Custom** | ~13 | ~2% | 🔧 Needs scraper |
| **Funnel/Nestio** | ~15-20 | ~3% | 🔧 Needs scraper |
| **AppFolio** | ~5-10 | ~1% | 🔧 Needs scraper |
| **RealPage/G5** | ~10-15 | ~2% | 🔧 Needs scraper |
| **WordPress/Custom** | ~40-60 | ~10% | ⚠️ Manual/varied |
| **Squarespace** | ~8-10 | ~2% | ⚠️ Manual/varied |
| **No URL / Inquiry Only** | ~134 | ~25% | ❌ No website |

---

## Management Company → Platform Mapping

### RentCafe/Yardi (Largest Platform ~280-310 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **Reside** | 38 | ✅ Confirmed | RentCafe widget + Yardi v2 scripts |
| **Greystar** | 24 | ✅ Confirmed | WordPress frontend + RentCafe/SecureCafe leasing |
| **Willow Bridge** | 23 | ✅ Confirmed | RentCafe (previously confirmed) |
| **Horizon** | 16 | ✅ Confirmed | Groupfox/RentCafe mix |
| **Waterton** | 7 | ✅ Confirmed | "Powered by RentCafe (© 2026 Yardi)" in footer |
| **Village Green** | 4 | ✅ Confirmed | RentCafe + Yardi + SecureCafe |
| **Habitat** | 4 | ✅ Confirmed | RentCafe (previously confirmed) |
| **Related** | 3 | ✅ Confirmed | RentCafe + Yardi + SecureCafe + Knock |
| **Calibrate** | 2 | ✅ Confirmed | RentCafe + Yardi + SecureCafe |
| **B&A Associates** | 2 | ✅ Confirmed | RentCafe + Yardi + SecureCafe |
| **Pinnacle** | 1 | ✅ Confirmed | RentCafe/Yardi |
| **Lakeside** | 1 | ✅ Confirmed | RentCafe + Yardi + SecureCafe |
| **LG Management** | 1 | ✅ Confirmed | SecureCafe + WordPress |
| **Birkshire** | 1 | ✅ Confirmed | SecureCafe |
| **Marquette** | 5 | ✅ Confirmed | RentCafe via CNAME (rentcafecn.com) |
| ~60-70% of blank-mgmt with URLs | ~60-70 | 🔶 Estimated | Many CF-blocked sites resolve to rentcafecn.com |

### Entrata (~30-40 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **Morguard** | 4 | ✅ Confirmed | Entrata scripts on echelonchicago.com |
| **Akara** | 1 | ✅ Confirmed | Entrata on chateauwells.com |
| **Crescent Heights** | 1 | ✅ Confirmed | RealPage/Entrata detected |
| Some blank-mgmt buildings | ~10-15 | 🔶 Estimated | e.g. thantower.com, thelydian.com |

### Groupfox (~12 buildings) ✅ SCRAPER BUILT

| Management Company | Buildings | Confidence |
|-------------------|-----------|------------|
| **Groupfox** | 9 | ✅ Confirmed |
| **GroupFox** | 1 | ✅ Confirmed |
| **Group Fox** | 1 | ✅ Confirmed |
| Some Horizon buildings | ~1-3 | ✅ Confirmed |

### PPM Custom (~18 buildings) ✅ SCRAPER BUILT

| Management Company | Buildings | Confidence |
|-------------------|-----------|------------|
| **PPM** | 18 | ✅ Confirmed |

### Bozzuto Custom (~13 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **Bozzuto** | 13 | ✅ Confirmed | Custom platform at bozzuto.com, schedule.tours integration |

### Funnel Leasing + Nestio (~15-20 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **FLATS** | 13 | ✅ Confirmed | Funnel Leasing + Nestio contact widget |
| **LMC** | 1 | ✅ Confirmed | Funnel Leasing |
| Some Greystar | varies | 🔶 Possible | Funnel detected alongside RentCafe |

### AppFolio (~5-10 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **3L Living** | 1 | ✅ Confirmed | AppFolio scripts |
| **Astoria Tower** | 1 | ✅ Confirmed | AppFolio scripts |
| **Cross Street** | 1 | ✅ Confirmed | AppFolio scripts |
| Some blank-mgmt | ~3-5 | 🔶 Estimated | e.g. livemadisonthroop.com |

### RealPage / G5 (~10-15 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **AMLI** | 5 | ✅ Confirmed | RealPage detected |
| **Magellan** | 7 | ✅ Confirmed | G5/RealPage marketing platform |
| **Styl Residential** | 1 | ✅ Confirmed | RealPage + Knock |
| **Tandem** | 4 | ✅ Confirmed | RealPage detected |

### Jonah Digital / Custom (~6-10 buildings)

| Management Company | Buildings | Confidence | Notes |
|-------------------|-----------|------------|-------|
| **Golub** | 6 | ✅ Confirmed | Jonah Digital (jonahdigital.com) custom sites |
| **Cagan** / **Cagan Mgmt** | 3 | ✅ Confirmed | Jonah Digital custom sites |

### WordPress / Custom Sites (~40-60 buildings)

| Management Company | Buildings | Platform Variant | Notes |
|-------------------|-----------|-----------------|-------|
| **Draper & Kramer** | 7 | WordPress | Custom WP theme |
| **Wirtz** | 7 | WordPress | Custom WP theme |
| **Onni** | 6 | WordPress | Custom WP theme |
| **Lincoln** | 5 | WordPress | Custom WP theme |
| **Luxury Living** | 5 | WordPress | Custom WP theme |
| **Trinity** | 4 | WordPress | Custom WP theme |
| **John Buck** | 3 | WordPress | Custom WP theme |
| **Windsor** | 3 | WordPress | Custom WP theme |
| **Arrive** | 2 | WordPress | Custom WP theme |
| **Hines** | 2 | WordPress | Custom WP theme |
| **DMG** | 2 | WordPress | Custom WP theme |
| **Brookfield** | 1 | WordPress | Custom WP theme |
| **Entrada** | 1 | WordPress | Custom WP theme |

### Squarespace (~8-10 buildings)

| Management Company | Buildings | Notes |
|-------------------|-----------|-------|
| **RMK** / **RMK Managment** | 7 | Squarespace sites |
| **33 Management** | 2 | Squarespace |
| **33 Realty** | 1 | Likely Squarespace |

### Other / Unidentified

| Management Company | Buildings | Notes |
|-------------------|-----------|-------|
| **Peak Properties** | 13 | Cloudflare-blocked, custom site |
| **BJB** | 3 | Custom PHP site |
| **Holsten** | 1 | Custom site |
| **Quarterra** | 1 | CraftCMS custom |
| **JL Woode** | 1 | CF-blocked, unknown |
| **Red Tail** | 1 | CF-blocked, unknown |
| **Wood** | 1 | CF-blocked, unknown |
| **Himes McCaffery** | 1 | CF-blocked, unknown |
| **Eposition Residential** | 1 | Unknown |

### No URL Available (~134 buildings)

238 buildings have blank management companies, and 134 of those also have no website URL. These require manual research.

---

## Recommended Scraper Priority Order

### Priority 1: RentCafe/Yardi (~280-310 buildings, ~55%)
**Impact:** Covers the majority of buildings including Reside (38), Greystar (24), Willow Bridge (23), Horizon (16), Waterton (7), and many blank-management buildings.
- API endpoint: `https://{property}.rentcafe.com/` or SecureCafe
- Key patterns: `.aspx` pages, `securecafe.com` leasing, Yardi v2 widgets
- Many behind Cloudflare — may need browser-based scraping or API approach
- **Note:** RentCafe sites share a common API structure making one scraper cover all

### Priority 2: Entrata (~30-40 buildings, ~7%)
**Impact:** Morguard (4), Akara (1), some blank-management buildings
- API endpoint: `https://{property}.entrata.com/`
- Standardized API available

### Priority 3: Bozzuto Custom (~13 buildings, ~2%)
**Impact:** All 13 Bozzuto-managed buildings
- Custom platform at bozzuto.com with schedule.tours integration
- Would need bozzuto-specific scraper

### Priority 4: RealPage/G5 (~15 buildings, ~3%)
**Impact:** AMLI (5), Magellan (7), Tandem (4)
- G5 marketing platform + RealPage leasing backend

### Priority 5: Funnel/Nestio (~15 buildings, ~3%)
**Impact:** FLATS (13), LMC (1)
- Funnel Leasing API + Nestio contact widgets
- May overlap with RentCafe (some use both)

### Priority 6: AppFolio (~5-10 buildings, ~1%)
**Impact:** Smaller companies (3L Living, Astoria Tower, Cross Street)
- AppFolio has a standard widget/API pattern

### Already Built ✅
- **Groupfox** (~12 buildings): Scraper complete
- **PPM** (~18 buildings): Scraper complete

### Low Priority / Manual
- **WordPress/Custom** (~50 buildings): Each site is different, no common API
- **Squarespace** (~10 buildings): No standard rental API
- **Jonah Digital** (~9 buildings): Custom sites, no common structure

---

## Key Findings

1. **RentCafe/Yardi is the clear winner** — building a robust RentCafe scraper would cover 55%+ of all buildings in one shot.

2. **Cloudflare protection is widespread** — most RentCafe and Entrata sites are behind Cloudflare. The scraper will need to either:
   - Use browser automation (Playwright/Puppeteer)
   - Find direct API endpoints that bypass CF
   - Use the RentCafe API directly (most reliable)

3. **CNAME detection works** for identifying RentCafe sites without loading the page: domains pointing to `*.rentcafecn.com` are RentCafe.

4. **With just 3 scrapers (RentCafe + Entrata + existing Groupfox/PPM)**, we'd cover ~340-370 buildings (~70% of the total with URLs).

5. **134 buildings have no URL** and 238 have no management company — these need manual research/categorization.

---

## Detection Methodology

- **curl + grep**: Checked HTML source for platform-specific strings
- **DNS CNAME**: Identified `*.rentcafecn.com` as RentCafe indicator
- **HTTP headers**: Used `wp-json` header to identify WordPress sites
- **Browser automation**: Used Playwright to bypass Cloudflare and evaluate JavaScript
- **Platform indicators checked**: rentcafe, yardi, entrata, realpage, appfolio, groupfox, bozzuto, nestio, funnel, knock, g5search, squarespace, wordpress, wix, securecafe
