import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.audit import AuditRecord
from grounded.calculation import CalculationStatus
from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline
from grounded.public import GroundedPublicInterface


PIPELINE = GroundedPipeline()
INTERFACE = GroundedPublicInterface(PIPELINE)


def make_record(question, gross=None):
    result = PIPELINE.run(question)
    response = INTERFACE.answer_question(question, gross)
    return AuditRecord.from_execution(result, response)


def test_answerable_audit_contains_each_pipeline_stage():
    record = make_record("What is the household resource limit?")
    stored = record.to_dict()
    assert stored["question"] == "What is the household resource limit?"
    assert stored["retrieval_results"]
    assert stored["retrieval_results"][0]["relevance_score"] is not None
    assert "matched_signals" in stored["retrieval_results"][0]
    assert stored["temporal_decisions"]
    assert stored["evidence_assessment"]["status"] == "SUPPORTED"
    assert stored["decision_result"]["status"] == "ANSWERABLE"
    assert stored["resolved_provisions"]
    assert stored["answer_result"]["sections"]
    assert stored["validation_result"]["status"] == "VALID"


def test_amended_audit_preserves_provenance_across_outputs():
    record = make_record("What is the $175 earnings disregard for a determination on 1 April 2026?")
    stored = record.to_dict()
    assert "2026-01 §1.1" in stored["source_amendments"]
    assert any(item["amendment_id"] == "2026-01" for item in stored["citations"])
    assert any(
        item["amendment_id"] == "2026-01"
        for item in stored["resolved_provisions"]
    )


def test_blocked_audit_preserves_conflict_and_non_answer_state():
    record = make_record("How many days must I report a change occurring on 28 February 2026?")
    stored = record.to_dict()
    assert record.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert stored["answer_permitted"] is False
    assert stored["decision_result"]["status"] == "CONFLICTING_AUTHORITY"
    assert stored["answer_result"]["sections"] == []
    assert stored["conflicts"]


def test_calculation_audit_preserves_decimal_values_and_provenance():
    record = make_record(
        "What is the $175 earnings disregard for a determination on 1 April 2026?",
        "500",
    )
    stored = record.to_dict()
    assert stored["calculation"]["status"] == CalculationStatus.CALCULATED.value
    assert stored["calculation"]["calculation"]["countable_monthly_earnings"] == "325"
    assert stored["calculation"]["calculation"]["provenance"]["amendment_id"] == "2026-01"
    assert stored["calculation"]["calculation"]["provenance"]["amendment_paragraph"] == "1.1"


def test_audit_record_json_is_stable_and_valid():
    record = make_record("What is the $175 earnings disregard for a determination on 1 April 2026?", "500")
    first = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    second = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert first == second
    parsed = json.loads(first)
    assert parsed["execution_id"] == record.execution_id
    assert isinstance(parsed["calculation"]["calculation"]["gross_monthly_earnings"], str)

