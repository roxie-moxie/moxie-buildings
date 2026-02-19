"""
Tests for the Tier 3 LLM fallback scraper (moxie.scrapers.tier3.llm).

Strategy:
- For scrape() tests that check EnvironmentError: let it run directly (no network needed)
- For scrape() tests that check result passthrough: monkeypatch _scrape_with_llm
- For _scrape_with_llm tests (JSON parsing, filtering): monkeypatch AsyncWebCrawler
  context manager so Playwright is never invoked

No real network calls, no real API calls, no Playwright browser needed.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import moxie.scrapers.tier3.llm as llm_module
from moxie.scrapers.tier3.llm import scrape, _scrape_with_llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_building(url="https://example.com/apartments"):
    """Return a minimal Building-like object (duck-typed) for tests."""
    class FakeBuilding:
        id = 1
        name = "Test Building"

    b = FakeBuilding()
    b.url = url
    return b


def _make_unit(unit_number="101", bed_type="1 Bedroom", rent="$1,500/mo",
               availability_date="Available Now", **kwargs):
    """Return a valid unit dict matching _UnitRecord schema."""
    unit = {
        "unit_number": unit_number,
        "bed_type": bed_type,
        "rent": rent,
        "availability_date": availability_date,
    }
    unit.update(kwargs)
    return unit


def _make_fake_crawler_ctx(extracted_content):
    """
    Return a mock async context manager that simulates AsyncWebCrawler.
    The crawler's arun() returns a FakeResult with the given extracted_content.
    Does NOT launch Playwright.

    FakeResult.links is set to {} so the two-pass _find_availability_link
    finds no internal links and falls back to the original URL, allowing
    Pass 2 (LLM extraction) to proceed with extracted_content.
    """
    class FakeResult:
        pass

    result = FakeResult()
    result.extracted_content = extracted_content
    result.links = {}   # Pass 1: no internal links → fall back to original URL
    result.html = ""    # Pass 1 also checks .html in some paths

    mock_crawler = MagicMock()
    mock_crawler.arun = AsyncMock(return_value=result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.return_value = mock_crawler
    return mock_ctx


# ---------------------------------------------------------------------------
# Test: EnvironmentError when ANTHROPIC_API_KEY is missing
# ---------------------------------------------------------------------------

def test_scrape_raises_environment_error_if_no_api_key(monkeypatch):
    """scrape() must raise EnvironmentError when ANTHROPIC_API_KEY is absent."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    building = _make_building()
    with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
        scrape(building)


# ---------------------------------------------------------------------------
# Helper: patch _scrape_with_llm at the module level for scrape() passthrough tests
# ---------------------------------------------------------------------------

def _patch_async_scrape(monkeypatch, return_value):
    """Replace _scrape_with_llm with a coroutine that returns return_value."""
    async def fake_scrape_with_llm(url):
        return return_value

    monkeypatch.setattr(llm_module, "_scrape_with_llm", fake_scrape_with_llm)


# ---------------------------------------------------------------------------
# Test: scrape() passthrough tests (patching _scrape_with_llm)
# ---------------------------------------------------------------------------

def test_scrape_returns_empty_on_malformed_json(monkeypatch):
    """scrape() returns [] when _scrape_with_llm returns [] (malformed JSON path)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _patch_async_scrape(monkeypatch, [])
    result = scrape(_make_building())
    assert result == []


def test_scrape_returns_empty_on_null_content(monkeypatch):
    """scrape() returns [] when _scrape_with_llm returns [] (null content path)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _patch_async_scrape(monkeypatch, [])
    result = scrape(_make_building())
    assert result == []


def test_scrape_returns_empty_on_non_list_json(monkeypatch):
    """scrape() returns [] when _scrape_with_llm returns [] (non-list JSON path)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _patch_async_scrape(monkeypatch, [])
    result = scrape(_make_building())
    assert result == []


def test_scrape_returns_all_valid_records(monkeypatch):
    """scrape() returns all valid records when _scrape_with_llm returns them."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    unit1 = _make_unit(unit_number="101", bed_type="Studio", rent="$1,200/mo",
                       availability_date="Available Now")
    unit2 = _make_unit(unit_number="202", bed_type="1 Bedroom", rent="$1,800/mo",
                       availability_date="March 1, 2026",
                       floor_plan_name="Lakeview A", baths="1", sqft="750")
    _patch_async_scrape(monkeypatch, [unit1, unit2])
    result = scrape(_make_building())
    assert len(result) == 2
    assert result[0]["unit_number"] == "101"
    assert result[1]["unit_number"] == "202"
    assert result[1]["floor_plan_name"] == "Lakeview A"


# ---------------------------------------------------------------------------
# Tests for _scrape_with_llm internal JSON parsing and filtering logic
# (AsyncWebCrawler is mocked -- no Playwright launched)
# ---------------------------------------------------------------------------

def test_scrape_with_llm_returns_empty_on_malformed_json(monkeypatch):
    """_scrape_with_llm returns [] when extracted_content is invalid JSON."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_ctx = _make_fake_crawler_ctx("not valid json{{")
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert result == []


def test_scrape_with_llm_returns_empty_on_null_content(monkeypatch):
    """_scrape_with_llm returns [] when extracted_content is None."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_ctx = _make_fake_crawler_ctx(None)
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert result == []


def test_scrape_with_llm_returns_empty_on_dict_json(monkeypatch):
    """_scrape_with_llm returns [] when extracted_content is a JSON object (not list)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_ctx = _make_fake_crawler_ctx(json.dumps({"key": "value"}))
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert result == []


def test_scrape_filters_incomplete_records(monkeypatch):
    """Records missing required fields (unit_number, bed_type, rent) are excluded."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    units = [
        _make_unit(unit_number="101", bed_type="Studio", rent="$1,200/mo"),
        _make_unit(unit_number="202", bed_type="1 Bedroom", rent="$1,800/mo"),
        {"unit_number": "303", "bed_type": "2BR"},  # no rent -> filtered
    ]
    mock_ctx = _make_fake_crawler_ctx(json.dumps(units))
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert len(result) == 2
    assert all("rent" in r for r in result)


def test_unit_number_field_required(monkeypatch):
    """Records without unit_number are filtered out."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    units = [
        {"bed_type": "1 Bedroom", "rent": "$1,500/mo", "availability_date": "Now"},  # no unit_number
        _make_unit(unit_number="101", bed_type="Studio", rent="$1,200/mo"),
    ]
    mock_ctx = _make_fake_crawler_ctx(json.dumps(units))
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert len(result) == 1
    assert result[0]["unit_number"] == "101"


def test_bed_type_field_required(monkeypatch):
    """Records without bed_type are filtered out."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    units = [
        {"unit_number": "101", "rent": "$1,500/mo", "availability_date": "Now"},  # no bed_type
        _make_unit(unit_number="202", bed_type="2BR", rent="$2,000/mo"),
    ]
    mock_ctx = _make_fake_crawler_ctx(json.dumps(units))
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert len(result) == 1
    assert result[0]["unit_number"] == "202"


def test_scrape_with_llm_filters_and_returns_valid_records(monkeypatch):
    """_scrape_with_llm filters records and returns only those with all required fields."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    units = [
        {"unit_number": "101", "bed_type": "Studio", "rent": "$1,200/mo",
         "availability_date": "Available Now"},
        {"unit_number": "202", "bed_type": "1 Bedroom", "rent": "$1,800/mo",
         "availability_date": "March 1, 2026"},
        {"bed_type": "2BR", "rent": "$2,000/mo"},  # missing unit_number -> filtered
    ]
    mock_ctx = _make_fake_crawler_ctx(json.dumps(units))
    with patch("moxie.scrapers.tier3.llm.AsyncWebCrawler", mock_ctx):
        result = asyncio.run(_scrape_with_llm("https://example.com"))
    assert len(result) == 2
    assert result[0]["unit_number"] == "101"
    assert result[1]["unit_number"] == "202"
