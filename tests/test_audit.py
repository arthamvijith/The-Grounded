import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.audit import AuditLogger
from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline


PIPELINE = GroundedPipeline()
ROOT = Path(__file__).parents[1]


def execute(question):
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        logger = AuditLogger(Path(directory) / "audit.jsonl", PIPELINE)
        execution = logger.record_question(question)
        stored = logger.read_records()
        assert len(stored) == 1
        return execution, stored[0]


def test_answerable_execution_is_audited():
    execution, stored = execute("What is the household resource limit?")
    assert execution.response.status is DecisionStatus.ANSWERABLE
    assert stored["status"] == "ANSWERABLE"
    assert stored["answer_permitted"] is True
    assert stored["question"] == "What is the household resource limit?"
    assert stored["citations"]
    assert stored["decision_result"]["status"] == "ANSWERABLE"


def test_missing_fact_execution_is_audited():
    execution, stored = execute("How much earnings can be disregarded?")
    assert execution.response.status is DecisionStatus.NEEDS_CLARIFICATION
    assert stored["missing_facts"] == ["determination_date"]
    assert stored["answer_permitted"] is False
    assert stored["next_action"] == "request_missing_facts"


def test_conflict_execution_preserves_conflict():
    execution, stored = execute("How many days must I report a change occurring on 28 February 2026?")
    assert execution.response.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert stored["answer_permitted"] is False
    assert stored["conflicts"]
    values = stored["conflicts"][0]["claims_or_values"]
    assert values == ["§4.3.2: 10 calendar days", "§9.1.4: 30 calendar days"]


def test_broken_reference_execution_is_audited():
    execution, stored = execute("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?")
    assert execution.response.status is DecisionStatus.BROKEN_CROSS_REFERENCE
    assert stored["answer_permitted"] is False
    assert stored["decision_result"]["status"] == "BROKEN_CROSS_REFERENCE"


def test_insufficient_evidence_execution_is_audited():
    execution, stored = execute("What is a unicorn rule?")
    assert execution.response.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert stored["answer_permitted"] is False
    assert stored["gaps"] == []


def test_amended_execution_preserves_provenance_and_temporal_data():
    execution, stored = execute("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert execution.response.status is DecisionStatus.ANSWERABLE
    assert "2026-01 §1.1" in stored["source_amendments"]
    assert any(item["amendment_id"] == "2026-01" for item in stored["citations"])
    assert stored["temporal_decisions"]
    assert stored["evidence_assessment"]["status"] == "SUPPORTED"


def test_jsonl_is_append_only_and_deterministic():
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "nested" / "audit.jsonl"
        logger = AuditLogger(path, PIPELINE)
        first = logger.record_question("What is a unicorn rule?")
        second = logger.record_question("What is a unicorn rule?")
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["execution_id"] == first.record.execution_id
        assert json.loads(lines[1])["execution_id"] == second.record.execution_id
        assert first.record.execution_id == second.record.execution_id
