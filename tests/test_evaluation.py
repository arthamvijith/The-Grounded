import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.decision import DecisionStatus
from grounded.calculation import CalculationStatus
from grounded.evaluation import (
    EvaluationCase,
    GroundedEvaluator,
    default_evaluation_cases,
)
from grounded.public import GroundedPublicInterface


EVALUATOR = GroundedEvaluator(GroundedPublicInterface())


def test_default_regression_cases_are_present_and_pass():
    report = EVALUATOR.run()
    assert report.total == 10
    assert report.all_passed
    assert report.failed == 0


def test_expected_cases_cover_positive_and_negative_statuses():
    statuses = {case.expected_status for case in default_evaluation_cases()}
    assert DecisionStatus.ANSWERABLE in statuses
    assert DecisionStatus.NEEDS_CLARIFICATION in statuses
    assert DecisionStatus.CONFLICTING_AUTHORITY in statuses
    assert DecisionStatus.BROKEN_CROSS_REFERENCE in statuses
    assert DecisionStatus.INSUFFICIENT_EVIDENCE in statuses


def test_amended_case_checks_provenance():
    result = EVALUATOR.evaluate_case(
        next(case for case in default_evaluation_cases() if case.case_id == "amended-earnings-disregard")
    )
    assert result.passed
    assert "2026-01 §1.1" in result.response.source_amendments


def test_non_answerable_permission_is_a_regression_failure():
    case = EvaluationCase(
        case_id="deliberate-permission-regression",
        question="What is a unicorn rule?",
        expected_status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        expected_answer_permitted=True,
    )
    result = EVALUATOR.evaluate_case(case)
    assert not result.passed
    assert any("answer_permitted expected True" in failure for failure in result.failures)


def test_wrong_status_and_next_action_are_reported():
    case = EvaluationCase(
        case_id="deliberate-status-regression",
        question="How much earnings can be disregarded?",
        expected_status=DecisionStatus.ANSWERABLE,
        expected_answer_permitted=False,
        expected_next_action="answer",
    )
    result = EVALUATOR.evaluate_case(case)
    assert not result.passed
    assert any("status expected ANSWERABLE" in failure for failure in result.failures)
    assert any("next_action expected answer" in failure for failure in result.failures)


def test_evaluation_order_and_results_are_deterministic():
    first = EVALUATOR.run()
    second = EVALUATOR.run()
    assert first == second
    assert [result.case_id for result in first.results] == [
        "supported-household-resource-limit",
        "missing-earnings-determination-date",
        "reporting-rule-conflict",
        "broken-student-cross-reference",
        "unsupported-unicorn-rule",
        "amended-earnings-disregard",
        "paraphrased-household-resources",
        "historical-original-earnings-disregard",
        "multi-clause-resource-and-earnings",
        "calculated-amended-earnings",
    ]


def test_expanded_cases_check_original_and_multi_clause_coverage():
    report = EVALUATOR.run()
    historical = next(item for item in report.results if item.case_id == "historical-original-earnings-disregard")
    multi_clause = next(item for item in report.results if item.case_id == "multi-clause-resource-and-earnings")
    assert historical.passed
    assert historical.answer_permitted
    assert historical.response.source_amendments == ()
    assert multi_clause.passed
    assert len(multi_clause.response.sections) > 1


def test_expanded_calculation_case_checks_structured_result_and_provenance():
    result = next(item for item in EVALUATOR.run().results if item.case_id == "calculated-amended-earnings")
    assert result.passed
    assert result.calculation is not None
    assert result.calculation.status is CalculationStatus.CALCULATED
    assert result.calculation.calculation.countable_monthly_earnings == 325
    assert result.calculation.calculation.provenance.amendment_id == "2026-01"
    assert result.calculation.calculation.provenance.amendment_paragraph == "1.1"
