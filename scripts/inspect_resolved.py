"""Inspect formal query-specific resolved provision projections."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.build import build_artifacts
from grounded.pipeline import GroundedPipeline


def show(label: str, result) -> None:
    print(f"\n=== {label} ===")
    print(f"question: {result.question}")
    print(f"status: {result.decision.status.value}")
    for item in result.resolved_provisions:
        print(
            f"- {item.provision_id} version={item.version.value} "
            f"applicable={item.applicable} temporal={item.temporal_status.value} "
            f"amendment={item.amendment_id}:{item.amendment_paragraph} "
            f"period={item.period_start}..{item.period_end}"
        )
        print(f"  source: {item.source_document}")
        print(f"  text: {item.text}")


def main() -> None:
    artifact_root = ROOT / "build" / "artifacts"
    build_artifacts(ROOT, artifact_root)
    pipeline = GroundedPipeline(artifact_root=artifact_root)
    show("original provision", pipeline.run("What is the household resource limit?"))
    show("amended provision", pipeline.run("What is the $175 earnings disregard for a determination on 1 April 2026?"))
    show("missing determination date", pipeline.run("How much earnings can be disregarded?"))
    show(
        "multiple periods",
        pipeline.run("What is the earnings disregard for a period from 28 February 2026 to 2 March 2026 for a determination on 2 March 2026?"),
    )


if __name__ == "__main__":
    main()
