"""Inspect local JSONL audit records for representative grounded questions."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.audit import AuditLogger
from grounded.pipeline import GroundedPipeline


QUESTIONS = (
    "What is the household resource limit?",
    "How much earnings can be disregarded?",
    "How many days must I report a change occurring on 28 February 2026?",
    "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?",
    "What is a unicorn rule?",
    "What is the $175 earnings disregard for a determination on 1 April 2026?",
)


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "grounded-audit.jsonl"
    logger = AuditLogger(path, GroundedPipeline())
    for question in QUESTIONS:
        gross = "500" if "175" in question else None
        execution = logger.record_question(question, gross)
        record = execution.record
        print(f"\nquestion: {record.question}")
        print(f"execution_id: {record.execution_id}")
        print(f"status: {record.status}")
        print(f"answer_permitted: {record.answer_permitted}")
        print(f"next_action: {record.next_action}")
        print(f"missing_facts: {record.missing_facts}")
        print(f"source_provisions: {record.source_provisions}")
        print(f"source_amendments: {record.source_amendments}")
        print(f"citation_count: {len(record.citations)}")
        print(f"retrieval_result_count: {len(record.retrieval_results)}")
        print(f"temporal_decision_count: {len(record.temporal_decisions)}")
        print(f"resolved_provision_count: {len(record.resolved_provisions)}")
        print(f"evidence_status: {record.evidence_assessment.status.value}")
        print(f"decision_status: {record.decision_result.status.value}")
        print(f"validation_status: {record.validation_result.status.value if record.validation_result else None}")
        print(f"calculation_status: {record.calculation.status.value if record.calculation else None}")
        if record.calculation and record.calculation.calculation:
            print(f"calculation_countable_monthly_earnings: {record.calculation.calculation.countable_monthly_earnings}")
        print(f"audit_lines: {len(logger.read_records())}")
