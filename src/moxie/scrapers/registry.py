"""
Centralized scraper registry.

Single source of truth for the PLATFORM_SCRAPERS mapping.
All modules that need to dispatch to a scraper by platform key should import from here.
"""

# Maps platform string -> Python module path for importlib.import_module()
PLATFORM_SCRAPERS: dict[str, str] = {
    "rentcafe": "moxie.scrapers.tier2.securecafe",
    "ppm":      "moxie.scrapers.tier1.ppm",
    "funnel":   "moxie.scrapers.tier2.funnel",
    "appfolio": "moxie.scrapers.tier2.appfolio",
    "bozzuto":  "moxie.scrapers.tier2.bozzuto",
    "realpage": "moxie.scrapers.tier2.realpage",
    "groupfox": "moxie.scrapers.tier2.groupfox",
    "sightmap": "moxie.scrapers.tier2.sightmap",
    # Entrata, MRI: no dedicated scraper yet — use LLM as fallback
    "entrata":  "moxie.scrapers.tier3.llm",
    "mri":      "moxie.scrapers.tier3.llm",
    "llm":      "moxie.scrapers.tier3.llm",
}

# Platforms that have no working scraper and should be excluded from batch runs
SKIP_PLATFORMS: set[str] = {"dead", "needs_classification"}
