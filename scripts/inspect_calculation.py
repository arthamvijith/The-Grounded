"""Inspect the small Step 20 policy-backed calculation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.calculation import calculate_monthly_earnings_after_disregard
from grounded.pipeline import GroundedPipeline


def main() -> None:
    pipeline = GroundedPipeline()
    amended = pipeline.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    result = calculate_monthly_earnings_after_disregard(amended, "500")
    print("amended calculation:", result)

    original = pipeline.run("What is the earnings disregard for a determination on 1 February 2026?")
    print("original calculation:", calculate_monthly_earnings_after_disregard(original, "500"))

    missing = calculate_monthly_earnings_after_disregard(amended, None)
    print("missing input:", missing)

    unsupported = pipeline.run("What is the household resource limit?")
    print("unsupported calculation:", calculate_monthly_earnings_after_disregard(unsupported, "500"))


if __name__ == "__main__":
    main()
