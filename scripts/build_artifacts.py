"""Build reproducible offline THE GROUNDED artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.build import build_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic THE GROUNDED source/index artifacts.")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "artifacts")
    args = parser.parse_args()
    bundle = build_artifacts(args.source_root, args.output)
    print(f"artifact_root: {args.output}")
    print(f"provisions: {len(bundle.provisions)}")
    print(f"amendments: {len(bundle.amendments)}")
    print(f"index_records: {len(bundle.search_index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
