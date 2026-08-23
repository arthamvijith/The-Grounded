import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.calculation import CalculationStatus, calculate_monthly_earnings_after_disregard
from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline


PIPELINE = GroundedPipeline()


def test_valid_amended_earnings_calculation():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    calculated = calculate_monthly_earnings_after_disregard(result, "500")
    assert calculated.status is CalculationStatus.CALCULATED
    assert calculated.calculation.countable_monthly_earnings == Decimal("325")


def test_calculation_uses_resolved_amendment_and_preserves_provenance():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    calculated = calculate_monthly_earnings_after_disregard(result, 500)
    provenance = calculated.calculation.provenance
    assert provenance.provision_id == "§6.4.1"
    assert provenance.version == "amendment"
    assert provenance.amendment_id == "2026-01"
    assert provenance.amendment_paragraph == "1.1"
    assert provenance.source_document.endswith("Amendment No. 2026-01.md")


def test_original_earnings_disregard_is_used_before_amendment():
    result = PIPELINE.run("What is the earnings disregard for a determination on 1 February 2026?")
    calculated = calculate_monthly_earnings_after_disregard(result, 500)
    assert calculated.status is CalculationStatus.CALCULATED
    assert calculated.calculation.disregard == Decimal("120")
    assert calculated.calculation.countable_monthly_earnings == Decimal("380")
    assert calculated.calculation.provenance.amendment_id is None


def test_missing_gross_earnings_fails_safely():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    calculated = calculate_monthly_earnings_after_disregard(result, None)
    assert calculated.status is CalculationStatus.NEEDS_CLARIFICATION
    assert calculated.missing_inputs == ("gross_monthly_earnings",)
    assert calculated.calculation is None


def test_invalid_gross_earnings_fails_safely():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    calculated = calculate_monthly_earnings_after_disregard(result, -1)
    assert calculated.status is CalculationStatus.NEEDS_CLARIFICATION
    assert calculated.calculation is None


def test_unsupported_calculation_is_not_invented():
    result = PIPELINE.run("What is the household resource limit?")
    calculated = calculate_monthly_earnings_after_disregard(result, 500)
    assert calculated.status is CalculationStatus.INSUFFICIENT_EVIDENCE
    assert calculated.calculation is None


def test_missing_determination_date_is_blocked_by_existing_gate():
    result = PIPELINE.run("How much earnings can be disregarded?")
    calculated = calculate_monthly_earnings_after_disregard(result, 500)
    assert result.decision.status is DecisionStatus.NEEDS_CLARIFICATION
    assert calculated.status is CalculationStatus.BLOCKED
    assert calculated.policy_status is DecisionStatus.NEEDS_CLARIFICATION


def test_period_with_multiple_disregard_versions_is_not_collapsed():
    result = PIPELINE.run(
        "What $175 earnings disregard applies for a period from 28 February 2026 to 2 March 2026 "
        "for a determination on 2 March 2026?"
    )
    calculated = calculate_monthly_earnings_after_disregard(result, 500)
    assert calculated.status is CalculationStatus.UNSUPPORTED
    assert calculated.calculation is None


def test_zero_and_low_earnings_are_not_made_negative():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert calculate_monthly_earnings_after_disregard(result, 0).calculation.countable_monthly_earnings == Decimal("0")
    assert calculate_monthly_earnings_after_disregard(result, 100).calculation.countable_monthly_earnings == Decimal("0")
