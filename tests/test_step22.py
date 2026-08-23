import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.calculation import CalculationStatus
from grounded.cli import main
from grounded.decision import DecisionStatus
from grounded.public import GroundedPublicInterface


def test_public_success_exposes_grounded_sections_and_citations():
    response = GroundedPublicInterface().answer_question("What is the household resource limit?")
    assert response.status is DecisionStatus.ANSWERABLE
    assert response.answer_permitted
    assert response.sections
    assert all(section.content for section in response.sections)
    assert response.citations
    assert response.source_provisions


def test_public_amended_answer_preserves_provenance():
    response = GroundedPublicInterface().answer_question(
        "What is the $175 earnings disregard for a determination on 1 April 2026?"
    )
    assert response.answer_permitted
    assert any("2026-01" in amendment and "1.1" in amendment for amendment in response.source_amendments)
    assert any(citation.amendment_id == "2026-01" and citation.amendment_paragraph == "1.1" for citation in response.citations)


def test_public_blocking_response_preserves_conflict_metadata():
    response = GroundedPublicInterface().answer_question(
        "How many days must I report a change occurring on 28 February 2026?"
    )
    assert response.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert not response.answer_permitted
    assert response.sections == ()
    assert response.conflicts
    assert response.next_action == "escalate_conflict"


def test_public_insufficient_evidence_is_structured_non_answer():
    response = GroundedPublicInterface().answer_question("What is a unicorn rule?")
    assert response.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert not response.answer_permitted
    assert response.sections == ()
    assert response.refusal_reason
    assert response.next_action == "explain_insufficient_evidence"


def test_public_calculation_presentation_preserves_policy_provenance():
    response = GroundedPublicInterface().answer_question(
        "What is the $175 earnings disregard for a determination on 1 April 2026?",
        gross_monthly_earnings="500",
    )
    assert response.calculation is not None
    assert response.calculation.status is CalculationStatus.CALCULATED
    assert response.calculation.calculation.countable_monthly_earnings == Decimal("325")
    assert response.calculation.calculation.provenance.amendment_id == "2026-01"
    assert response.calculation.calculation.provenance.amendment_paragraph == "1.1"


def test_cli_human_output_distinguishes_answer_and_blocking_reason(capsys):
    assert main(["ask", "What is the household resource limit?"]) == 0
    answered = capsys.readouterr().out
    assert "STATUS: ANSWERABLE" in answered
    assert "ANSWER:" in answered
    assert "SOURCE:" in answered
    assert "Citation(" not in answered

    assert main(["ask", "What is a unicorn rule?"]) == 5
    blocked = capsys.readouterr().out
    assert "STATUS: INSUFFICIENT_EVIDENCE" in blocked
    assert "RESULT:" in blocked
    assert "REASON:" in blocked
    assert "NEXT ACTION:" in blocked
    assert "Citation(" not in blocked


def test_cli_json_with_calculation_is_deterministic(capsys):
    args = [
        "ask",
        "What is the $175 earnings disregard for a determination on 1 April 2026?",
        "--gross-monthly-earnings",
        "500",
        "--json",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["calculation"]["status"] == "CALCULATED"
    assert payload["calculation"]["calculation"]["countable_monthly_earnings"] == "325"
