import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline


PIPELINE = GroundedPipeline()


def test_supported_question_is_answerable():
    result = PIPELINE.run("What is the household resource limit?")
    assert result.final_answer.status is DecisionStatus.ANSWERABLE
    assert result.final_answer.answer_permitted
    assert result.final_answer.sections


def test_missing_date_needs_clarification():
    result = PIPELINE.run("How much earnings can be disregarded?")
    assert result.final_answer.status is DecisionStatus.NEEDS_CLARIFICATION
    assert result.final_answer.missing_facts == ("determination_date",)
    assert result.final_answer.sections == ()


def test_reporting_conflict_is_preserved():
    result = PIPELINE.run("How many days must I report a change occurring on 28 February 2026?")
    assert result.final_answer.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert result.final_answer.answer_permitted is False
    assert result.final_answer.sections == ()
    assert result.final_answer.conflicts


def test_broken_cross_reference_is_preserved():
    result = PIPELINE.run("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?")
    assert result.final_answer.status is DecisionStatus.BROKEN_CROSS_REFERENCE
    assert result.final_answer.sections == ()


def test_unsupported_question_is_insufficient():
    result = PIPELINE.run("What is a unicorn rule?")
    assert result.final_answer.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert result.final_answer.answer_permitted is False
    assert result.final_answer.sections == ()


def test_amended_provision_preserves_provenance():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert result.final_answer.status is DecisionStatus.ANSWERABLE
    assert any(
        citation.amendment_id == "2026-01" and citation.amendment_paragraph == "1.1"
        for citation in result.final_answer.citations
    )


def test_all_intermediate_outputs_are_preserved():
    result = PIPELINE.run("What is the household resource limit?")
    assert result.question_spec.raw_question == "What is the household resource limit?"
    assert result.retrieval_results
    assert result.temporal_decisions
    assert result.evidence_assessment is not None
    assert result.decision.status is result.final_answer.status


def test_pipeline_is_deterministic():
    question = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    first = PIPELINE.run(question)
    second = PIPELINE.run(question)
    assert first == second
