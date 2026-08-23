"""Inspect complete deterministic pipeline results."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.pipeline import GroundedPipeline


PIPELINE = GroundedPipeline()
QUESTIONS = (
    ("supported", "What is the household resource limit?"),
    ("missing date", "How much earnings can be disregarded?"),
    ("reporting conflict", "How many days must I report a change occurring on 28 February 2026?"),
    ("broken cross-reference", "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?"),
    ("unsupported", "What is a unicorn rule?"),
    ("amended provision", "What is the $175 earnings disregard for a determination on 1 April 2026?"),
)


for label, question in QUESTIONS:
    result = PIPELINE.run(question)
    print(f"\n=== {label} ===")
    print(f"question: {result.question}")
    print(f"question_intents: {result.question_spec.intents}")
    print(f"retrieval_count: {len(result.retrieval_results)}")
    print(f"temporal_count: {len(result.temporal_decisions)}")
    print(f"evidence_status: {result.evidence_assessment.status.value}")
    print(f"decision_status: {result.decision.status.value}")
    print(f"answer_status: {result.answer.status.value}")
    print(f"answer_permitted: {result.answer.answer_permitted}")
    print(f"sections: {result.answer.sections}")
    print(f"citations: {result.answer.citations}")
    print(f"source_provisions: {result.answer.source_provisions}")
    print(f"source_amendments: {result.answer.source_amendments}")
    print(f"missing_facts: {result.answer.missing_facts}")
    print(f"conflicts: {result.answer.conflicts}")
    print(f"gaps: {result.answer.gaps}")
    print(f"refusal_reason: {result.answer.refusal_reason}")
    print(f"next_action: {result.answer.next_action}")
