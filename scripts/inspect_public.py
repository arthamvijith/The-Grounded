"""Inspect the Step 11 public grounded interface."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.public import GroundedPublicInterface


INTERFACE = GroundedPublicInterface()
QUESTIONS = (
    ("supported", "What is the household resource limit?"),
    ("missing fact", "How much earnings can be disregarded?"),
    ("conflict", "How many days must I report a change occurring on 28 February 2026?"),
    ("broken cross-reference", "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?"),
    ("insufficient evidence", "What is a unicorn rule?"),
    ("amended provision", "What is the $175 earnings disregard for a determination on 1 April 2026?"),
)


for label, question in QUESTIONS:
    response = INTERFACE.answer_question(question)
    print(f"\n=== {label} ===")
    print(f"question: {response.question}")
    print(f"status: {response.status.value}")
    print(f"answer_permitted: {response.answer_permitted}")
    print(f"sections: {response.sections}")
    print(f"citations: {response.citations}")
    print(f"source_provisions: {response.source_provisions}")
    print(f"source_amendments: {response.source_amendments}")
    print(f"missing_facts: {response.missing_facts}")
    print(f"conflicts: {response.conflicts}")
    print(f"gaps: {response.gaps}")
    print(f"refusal_reason: {response.refusal_reason}")
    print(f"next_action: {response.next_action}")
