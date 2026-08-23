"""Demonstrate Step 15 build, load, runtime equivalence, and integrity checks."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.amendments import parse_amendment, validate_amendment_targets
from grounded.build import build_artifacts
from grounded.ingest import parse_policy_manual
from grounded.pipeline import GroundedPipeline


def main() -> None:
    artifact_root = ROOT / "build" / "artifacts"
    bundle = build_artifacts(ROOT, artifact_root)
    loaded = GroundedPipeline(artifact_root=artifact_root)
    current = GroundedPipeline()
    question = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    current_result = current.run(question)
    loaded_result = loaded.run(question)
    equivalent = (
        current_result.decision.status == loaded_result.decision.status
        and current_result.answer.answer_permitted == loaded_result.answer.answer_permitted
        and current_result.answer.source_provisions == loaded_result.answer.source_provisions
        and current_result.answer.source_amendments == loaded_result.answer.source_amendments
        and tuple(section.content for section in current_result.answer.sections)
        == tuple(section.content for section in loaded_result.answer.sections)
    )

    provisions = parse_policy_manual(ROOT / "source/original/policy-manual.md")
    amendments = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
    invalid = replace(amendments[0], old_text="text not present in target provision")
    try:
        validate_amendment_targets([invalid, *amendments[1:]], provisions)
    except ValueError as error:
        mismatch = f"rejected: {error}"
    else:
        mismatch = "ERROR: mismatch was accepted"

    print(f"artifact_root: {artifact_root}")
    print(f"built provisions: {len(bundle.provisions)}")
    print(f"built amendments: {len(bundle.amendments)}")
    print(f"built index records: {len(bundle.search_index)}")
    print(f"query: {question}")
    print(f"current status: {current_result.decision.status.value}")
    print(f"loaded status: {loaded_result.decision.status.value}")
    print(f"runtime equivalent: {equivalent}")
    print(f"old_text mismatch: {mismatch}")


if __name__ == "__main__":
    main()
