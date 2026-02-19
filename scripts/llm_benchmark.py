#!/usr/bin/env python
"""
LLM scraper benchmark — runs the Tier 3 LLM scraper against N real buildings
with platform='llm' and measures per-site token cost.

Usage:
    uv run python scripts/llm_benchmark.py [--count N]

Requires:
    - ANTHROPIC_API_KEY in .env
    - Populated moxie.db with buildings synced from Google Sheets
    - crawl4ai-setup to have been run (Playwright browsers installed)
"""
import argparse
import sys
import os
import time
from pathlib import Path

# Ensure src/ is on the path when run via uv run python
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from moxie.db.session import SessionLocal
from moxie.db.models import Building

# Haiku 3 pricing (USD per million tokens)
HAIKU_INPUT_COST_PER_MTOK = 0.25
HAIKU_OUTPUT_COST_PER_MTOK = 1.25


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD."""
    return (
        (input_tokens / 1_000_000) * HAIKU_INPUT_COST_PER_MTOK
        + (output_tokens / 1_000_000) * HAIKU_OUTPUT_COST_PER_MTOK
    )


def run_benchmark(count: int = 5) -> None:
    db = SessionLocal()
    try:
        buildings = (
            db.query(Building)
            .filter(Building.platform == "llm", Building.url.isnot(None))
            .limit(count)
            .all()
        )
    finally:
        db.close()

    if not buildings:
        print("No buildings with platform='llm' found in DB. Run sheets-sync first.")
        sys.exit(1)

    print(f"Running LLM benchmark against {len(buildings)} buildings...")
    print("-" * 80)

    results = []
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for i, building in enumerate(buildings, 1):
        print(f"[{i}/{len(buildings)}] {building.name} — {building.url}")
        start = time.time()

        # Import here to avoid loading crawl4ai before env is set
        from moxie.scrapers.tier3 import llm as llm_scraper
        try:
            units = llm_scraper.scrape(building)
            elapsed = time.time() - start

            # Token estimation: Crawl4AI may expose usage in future versions.
            # For now, estimate from output JSON length.
            # A more accurate approach is to instrument _scrape_with_llm to
            # return token counts from the Anthropic API response headers.
            output_json_chars = len(str(units))
            estimated_output_tokens = max(output_json_chars // 4, 10)
            # Input tokens: assume 10,000 avg (markdown from apartment page)
            estimated_input_tokens = 10_000

            cost = estimate_cost(estimated_input_tokens, estimated_output_tokens)
            total_input += estimated_input_tokens
            total_output += estimated_output_tokens
            total_cost += cost

            result = {
                "building": building.name,
                "url": building.url,
                "units_found": len(units),
                "elapsed_s": round(elapsed, 1),
                "est_input_tokens": estimated_input_tokens,
                "est_output_tokens": estimated_output_tokens,
                "est_cost_usd": round(cost, 4),
                "error": None,
            }
            print(f"  -> {len(units)} units found in {elapsed:.1f}s | est. ${cost:.4f}")
        except Exception as e:
            elapsed = time.time() - start
            result = {
                "building": building.name,
                "url": building.url,
                "units_found": 0,
                "elapsed_s": round(elapsed, 1),
                "est_input_tokens": 0,
                "est_output_tokens": 0,
                "est_cost_usd": 0.0,
                "error": str(e),
            }
            print(f"  -> ERROR in {elapsed:.1f}s: {e}")
        results.append(result)
        print()

    # Summary
    print("=" * 80)
    print(f"BENCHMARK SUMMARY ({len(results)} sites)")
    print(f"Total estimated cost: ${total_cost:.4f}")
    print(f"Average per site: ${total_cost / len(results):.4f}")
    buildings_per_day = 110  # estimated platform='llm' building count
    monthly_cost = (total_cost / len(results)) * buildings_per_day * 30
    print(f"Monthly projection ({buildings_per_day} buildings/day × 30 days): ${monthly_cost:.2f}")
    print(f"Target: <$120/month (within 20% = $96-$144)")
    print(f"Status: {'PASS' if monthly_cost <= 144 else 'EXCEEDS TARGET'}")
    print()

    # Save results
    output_path = Path(".planning/phases/02-scrapers/02-LLM-BENCHMARK.md")
    _write_benchmark_report(output_path, results, total_cost, monthly_cost, count)
    print(f"Results written to {output_path}")


def _write_benchmark_report(path, results, total_cost, monthly_cost, count):
    lines = [
        "# LLM Scraper Benchmark Results",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        f"**Model:** claude-3-haiku-20240307",
        f"**Sites tested:** {count}",
        f"**Pricing:** $0.25/MTok input, $1.25/MTok output",
        "",
        "## Per-Site Results",
        "",
        "| Building | Units | Elapsed | Est. Input Tokens | Est. Output Tokens | Est. Cost |",
        "|----------|-------|---------|-------------------|--------------------|-----------|",
    ]
    for r in results:
        error_note = f" *(ERROR: {r['error'][:40]})*" if r["error"] else ""
        lines.append(
            f"| {r['building'][:40]} | {r['units_found']} | {r['elapsed_s']}s "
            f"| {r['est_input_tokens']:,} | {r['est_output_tokens']:,} "
            f"| ${r['est_cost_usd']:.4f}{error_note} |"
        )
    lines += [
        "",
        "## Cost Projection",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total cost ({count} sites) | ${total_cost:.4f} |",
        f"| Average per site | ${total_cost / count:.4f} |",
        f"| Est. daily (110 buildings) | ${(total_cost / count) * 110:.2f} |",
        f"| **Monthly projection** | **${monthly_cost:.2f}** |",
        f"| Target (<$120/month) | {'PASS' if monthly_cost <= 120 else 'EXCEEDS - review model or approach'} |",
        f"| Within 20% band ($96-$144) | {'PASS' if monthly_cost <= 144 else 'EXCEEDS BAND'} |",
        "",
        "## Notes",
        "",
        "- Token counts are estimated from output JSON length (~4 chars/token) and assumed 10K input tokens/page.",
        "- For precise token counts, instrument `_scrape_with_llm()` to capture Anthropic API usage headers.",
        "- If cost exceeds target, consider: Claude Batch API (50% discount), fewer sites per day, or caching.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM scraper benchmark")
    parser.add_argument("--count", type=int, default=5, help="Number of sites to test (default: 5)")
    args = parser.parse_args()
    run_benchmark(args.count)
