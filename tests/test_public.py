import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline
from grounded.public import GroundedPublicInterface, PublicGroundedResponse, answer_question


INTERFACE = GroundedPublicInterface(GroundedPipeline())


def test_supported_question_returns_public_answer():
    response = INTERFACE.answer_question("What is the household resource limit?")
    assert isinstance(response, PublicGroundedResponse)
    assert response.status is DecisionStatus.ANSWERABLE
    assert response.answer_permitted is True
    assert response.sections
    assert response.citations


def test_missing_fact_is_exposed_without_answer():
    response = INTERFACE.answer_question("How much earnings can be disregarded?")
    assert response.status is DecisionStatus.NEEDS_CLARIFICATION
    assert response.answer_permitted is False
    assert response.sections == ()
    assert response.missing_facts == ("determination_date",)
    assert response.next_action == "request_missing_facts"


def test_conflict_is_exposed_without_answer():
    response = answer_question("How many days must I report a change occurring on 28 February 2026?", INTERFACE.pipeline)
    assert response.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert response.answer_permitted is False
    assert response.sections == ()
    assert response.conflicts
    assert response.next_action == "escalate_conflict"


def test_broken_cross_reference_is_exposed_without_answer():
    response = INTERFACE.answer_question("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?")
    assert response.status is DecisionStatus.BROKEN_CROSS_REFERENCE
    assert response.answer_permitted is False
    assert response.sections == ()
    assert response.next_action == "explain_broken_cross_reference"


def test_insufficient_evidence_is_exposed_without_answer():
    response = INTERFACE.answer_question("What is a unicorn rule?")
    assert response.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert response.answer_permitted is False
    assert response.sections == ()
    assert response.next_action == "explain_insufficient_evidence"


def test_amended_provenance_is_exposed():
    response = INTERFACE.answer_question("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert response.status is DecisionStatus.ANSWERABLE
    assert response.answer_permitted is True
    assert any(
        citation.amendment_id == "2026-01" and citation.amendment_paragraph == "1.1"
        for citation in response.citations
    )
    assert "2026-01 §1.1" in response.source_amendments


def test_public_interface_is_deterministic():
    question = "What is the household resource limit?"
    assert INTERFACE.answer_question(question) == INTERFACE.answer_question(question)
