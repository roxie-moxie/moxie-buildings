"""
LLM fallback scraper -- Tier 3 (Crawl4AI + Claude Haiku).

Covers:
- ~50-70 custom/long-tail sites with no recognized platform pattern
- All Entrata buildings (~30-40) -- routed here per CONTEXT.md decision
  (no Entrata API scraper; revisit as Phase 2.x if LLM struggles)

How it works:
1. Crawl4AI fetches and renders the building's URL (handles JS)
2. Crawl4AI converts HTML to markdown (5-10x token reduction vs raw HTML)
3. LLMExtractionStrategy sends markdown to Claude Haiku with a Pydantic schema
4. Claude Haiku returns a JSON list of UnitRecord objects
5. Scraper returns the list for normalize() / save_scrape_result()

Cost estimate (Claude Haiku 3, as of 2026-02-18):
- ~5,000-20,000 tokens per page -> ~$0.15-$0.30/day for 60 buildings
- ~$4.50-$9/month -- well under the $120/month target

Provider: "anthropic/claude-3-haiku-20240307" (via LiteLLM in Crawl4AI)
Requires: ANTHROPIC_API_KEY in environment

Platform: 'llm'
Coverage: ~80-110 buildings (custom sites + Entrata)
"""
import asyncio
import json
import os
from typing import Optional

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

from moxie.db.models import Building

# Claude Haiku model via LiteLLM provider string
_HAIKU_PROVIDER = "anthropic/claude-3-haiku-20240307"


# Structured extraction schema -- matches UnitInput fields in normalizer.py
class _UnitRecord(BaseModel):
    unit_number: str
    bed_type: str
    rent: str  # raw string; normalizer handles "$1,500/mo", "1500", etc.
    availability_date: str  # raw string; normalizer parses all formats
    floor_plan_name: Optional[str] = None
    baths: Optional[str] = None
    sqft: Optional[str] = None


_EXTRACTION_INSTRUCTION = (
    "Extract all apartment units currently available for rent from this page. "
    "For each available unit, extract: "
    "unit_number (the unit identifier, e.g. '101', 'A3', 'Studio-2'), "
    "bed_type (e.g. 'Studio', '1 Bedroom', '2BR', 'Convertible'), "
    "rent (monthly price as a string, e.g. '$1,800/mo', '2500'), "
    "availability_date (move-in date as a string, e.g. 'Available Now', 'March 1, 2026', '2026-04-01'), "
    "floor_plan_name (name of the floor plan if shown, otherwise null), "
    "baths (number of bathrooms as a string if shown, otherwise null), "
    "sqft (square footage as a string if shown, otherwise null). "
    "Only include units available for immediate rent (not waitlisted, leased, or 'coming soon'). "
    "Return an empty list if no available units are found."
)


async def _scrape_with_llm(url: str) -> list[dict]:
    """
    Use Crawl4AI LLMExtractionStrategy to extract unit data from a building URL.

    Returns list of raw dicts (matching _UnitRecord schema).
    Returns empty list on extraction failure or no units found.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or environment before running the LLM scraper."
        )

    strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider=_HAIKU_PROVIDER,
            api_token=api_key,
        ),
        schema=_UnitRecord.model_json_schema(),
        extraction_type="schema",
        instruction=_EXTRACTION_INSTRUCTION,
    )
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)

    raw_content = getattr(result, "extracted_content", None) or ""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        # Malformed output from LLM -- treat as empty (not a crash)
        return []

    if not isinstance(parsed, list):
        return []

    # Filter to dicts that have the minimum required fields
    units = []
    for item in parsed:
        if isinstance(item, dict) and item.get("unit_number") and item.get("bed_type") and item.get("rent"):
            units.append(item)

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability using LLM extraction (Crawl4AI + Claude Haiku).

    Works for any building URL -- custom sites, Entrata buildings, and any
    platform that cannot be classified into a specific scraper.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Returns empty list if LLM finds no available units.

    Raises EnvironmentError if ANTHROPIC_API_KEY is not set.
    """
    return asyncio.run(_scrape_with_llm(building.url))
