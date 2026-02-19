"""
Platform detection -- URL pattern matching to classify buildings by scraper platform.

detect_platform(url) returns a platform string or None.
None means the building should be assigned platform='llm' (catch-all).

Platform strings:
  rentcafe  -- RentCafe/Yardi (rentcafe.com)
  ppm       -- PPM Apartments (ppmapartments.com)
  funnel    -- Funnel/Nestio (nestiolistings.com, funnelleasing.com)
  realpage  -- RealPage/G5 (realpage.com, g5searchmarketing.com)
  bozzuto   -- Bozzuto (bozzuto.com)
  groupfox  -- Groupfox (groupfox.com)
  appfolio  -- AppFolio (appfolio.com)
  llm       -- everything else (assigned by caller when detect_platform returns None)
"""
from urllib.parse import urlparse

# Ordered list: first match wins. More specific patterns before less specific.
PLATFORM_PATTERNS: list[tuple[str, str]] = [
    ("rentcafe", "rentcafe.com"),
    ("ppm", "ppmapartments.com"),
    ("funnel", "nestiolistings.com"),
    ("funnel", "funnelleasing.com"),
    ("realpage", "realpage.com"),
    ("realpage", "g5searchmarketing.com"),
    ("bozzuto", "bozzuto.com"),
    ("groupfox", "groupfox.com"),
    ("appfolio", "appfolio.com"),
]

KNOWN_PLATFORMS: frozenset[str] = frozenset({
    "rentcafe", "ppm", "funnel", "realpage", "bozzuto", "groupfox", "appfolio", "llm"
})


def detect_platform(url: str) -> str | None:
    """
    Return the platform string for a given building URL, or None if unrecognized.

    None should be treated as 'llm' by the caller (sheets_sync or manual assignment).
    Only runs URL pattern matching -- no HTTP requests.

    Args:
        url: Full URL string (e.g. "https://somebuilding.rentcafe.com/...")

    Returns:
        Platform string (e.g. "rentcafe") or None if no pattern matched.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.lower())
        hostname = parsed.netloc or parsed.path
    except Exception:
        return None
    for platform, pattern in PLATFORM_PATTERNS:
        if pattern in hostname:
            return platform
    return None
