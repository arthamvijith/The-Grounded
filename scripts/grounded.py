"""Repository-root launcher for the THE GROUNDED CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
