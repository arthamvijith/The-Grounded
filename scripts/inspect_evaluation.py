"""Print the deterministic Step 13 regression summary."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.evaluation import run_evaluation


def main() -> None:
    report = run_evaluation()
    print(f"total cases: {report.total}")
    print(f"passed: {report.passed}")
    print(f"failed: {report.failed}")
    for result in report.results:
        state = "PASS" if result.passed else "FAIL"
        print(
            f"{state} {result.case_id}: "
            f"expected={result.expected_status.value}, "
            f"actual={result.actual_status.value}, "
            f"answer_permitted={result.answer_permitted}, "
            f"next_action={result.next_action}"
        )
        for failure in result.failures:
            print(f"  failure: {failure}")


if __name__ == "__main__":
    main()
