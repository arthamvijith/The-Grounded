"""Inspect Step 18 validation decisions for representative executions."""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import replace

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.answer import Citation
from grounded.pipeline import GroundedPipeline
from grounded.validation import ValidationStatus, validate_answer


def main() -> None:
    pipeline = GroundedPipeline()
    original = pipeline.run("What is the household resource limit?")
    amended = pipeline.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    print(f"valid original: {original.validation.status.value} reasons={original.validation.reasons}")
    print(f"valid amended: {amended.validation.status.value} reasons={amended.validation.reasons}")

    section = amended.answer.sections[0]
    citation = section.citations[0]
    tampered_citation = replace(citation, amendment_paragraph="9.9")
    tampered_section = replace(section, citations=(tampered_citation,))
    tampered_answer = replace(amended.answer, sections=(tampered_section,), citations=(tampered_citation,))
    result = validate_answer(
        tampered_answer, amended.decision, amended.evidence_assessment,
        amended.temporal_decisions, amended.resolved_provisions,
    )
    print(f"tampered citation: {result.status.value} reasons={result.reasons}")

    altered = replace(original.answer.sections[0], content="altered source excerpt")
    altered_answer = replace(original.answer, sections=(altered,))
    result = validate_answer(
        altered_answer, original.decision, original.evidence_assessment,
        original.temporal_decisions, original.resolved_provisions,
    )
    print(f"altered excerpt: {result.status.value} reasons={result.reasons}")

    conflict = pipeline.run("How many days must I report a change occurring on 28 February 2026?")
    print(f"existing conflict: {conflict.answer.status.value} permitted={conflict.answer.answer_permitted} sections={len(conflict.answer.sections)}")


if __name__ == "__main__":
    main()
