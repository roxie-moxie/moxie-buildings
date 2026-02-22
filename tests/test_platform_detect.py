"""
Tests for detect_platform() — URL pattern matching for scraper platform classification.

Covers: all 8 known platform domains, subdomains, unknown URLs (None), and empty string.
"""
import pytest
from moxie.scrapers.platform_detect import detect_platform


@pytest.mark.parametrize("url,expected", [
    # rentcafe — subdomain pattern
    ("https://thebuilding.rentcafe.com/apartments", "rentcafe"),
    ("https://foo.rentcafe.com/", "rentcafe"),
    # ppm — apex domain and subdomain
    ("https://ppmapartments.com/availability/", "ppm"),
    ("https://building.ppmapartments.com/", "ppm"),
    # funnel — nestiolistings.com subdomain
    ("https://someplace.nestiolistings.com/listings", "funnel"),
    # funnel — funnelleasing.com subdomain
    ("https://foo.funnelleasing.com/bar", "funnel"),
    # realpage — realpage.com subdomain
    ("https://myplace.realpage.com/", "realpage"),
    # realpage — G5 marketing subdomain
    ("https://widget.g5searchmarketing.com/unit-listing", "realpage"),
    # bozzuto — community subdomain
    ("https://community.bozzuto.com/apartments/", "bozzuto"),
    # groupfox — subdomain
    ("https://axis.groupfox.com/floorplans", "groupfox"),
    # appfolio — subdomain
    ("https://river-north.appfolio.com/listings", "appfolio"),
    # unknown custom site — no pattern match
    ("https://www.customapartments.com", None),
    # unknown — entrata-based site (not a known platform pattern)
    ("https://entrata-based-site.com/units", None),
    # empty string — returns None
    ("", None),
])
def test_detect_platform(url, expected):
    assert detect_platform(url) == expected


def test_detect_platform_none_like_empty():
    """Empty string is treated as a None-equivalent — no platform detected."""
    assert detect_platform("") is None


def test_detect_platform_path_does_not_match_hostname():
    """Platform pattern in path but not hostname should not match."""
    result = detect_platform("https://www.example.com/rentcafe/path")
    assert result is None


def test_detect_platform_case_insensitive():
    """URL matching is case-insensitive."""
    assert detect_platform("https://THEBUILDING.RENTCAFE.COM/apartments") == "rentcafe"


def test_detect_platform_returns_string_not_none_for_known():
    """Returns a non-None string for all known platforms."""
    known_cases = [
        ("https://thebuilding.rentcafe.com/", "rentcafe"),
        ("https://ppmapartments.com/", "ppm"),
        ("https://foo.nestiolistings.com/", "funnel"),
        ("https://foo.funnelleasing.com/", "funnel"),
        ("https://foo.realpage.com/", "realpage"),
        ("https://foo.g5searchmarketing.com/", "realpage"),
        ("https://foo.bozzuto.com/", "bozzuto"),
        ("https://foo.groupfox.com/", "groupfox"),
        ("https://foo.appfolio.com/", "appfolio"),
    ]
    for url, expected_platform in known_cases:
        result = detect_platform(url)
        assert result == expected_platform, f"Expected {expected_platform!r} for {url!r}, got {result!r}"


def test_known_platforms_contains_sightmap():
    """sightmap must be in KNOWN_PLATFORMS (58 buildings classified as sightmap)."""
    from moxie.scrapers.platform_detect import KNOWN_PLATFORMS
    assert "sightmap" in KNOWN_PLATFORMS
