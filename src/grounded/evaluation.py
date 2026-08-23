"""Deterministic regression evaluation for the grounded public interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .audit import AuditLogger
from .calculation import CalculationResult, CalculationStatus, calculate_monthly_earnings_after_disregard
from .decision import DecisionStatus
from .public import GroundedPublicInterface, PublicGroundedResponse


@dataclass(frozen=True)
class EvaluationCase:
    """One question and the structured behavior expected from the system."""

    case_id: str
    question: str
    expected_status: DecisionStatus
    expected_answer_permitted: bool
    expected_next_action: str | None = None
    expected_source_amendments: tuple[str, ...] = ()
    expected_source_provisions: tuple[str, ...] = ()
    calculation_gross_monthly_earnings: str | None = None
    expected_calculation_status: CalculationStatus | None = None
    expected_countable_monthly_earnings: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """The observed result and deterministic comparison for one case."""

    case_id: str
    question: str
    expected_status: DecisionStatus
    actual_status: DecisionStatus
    expected_answer_permitted: bool
    answer_permitted: bool
    expected_next_action: str | None
    next_action: str | None
    passed: bool
    failures: tuple[str, ...]
    response: PublicGroundedResponse
    calculation: CalculationResult | None = None


@dataclass(frozen=True)
class EvaluationReport:
    """Ordered results for a complete evaluation run."""

    results: tuple[EvaluationResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


def default_evaluation_cases() -> tuple[EvaluationCase, ...]:
    """Return the stable expanded regression corpus."""

    return (
        EvaluationCase(
            case_id="supported-household-resource-limit",
            question="What is the household resource limit?",
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
        ),
        EvaluationCase(
            case_id="missing-earnings-determination-date",
            question="How much earnings can be disregarded?",
            expected_status=DecisionStatus.NEEDS_CLARIFICATION,
            expected_answer_permitted=False,
            expected_next_action="request_missing_facts",
        ),
        EvaluationCase(
            case_id="reporting-rule-conflict",
            question="How many days must I report a change occurring on 28 February 2026?",
            expected_status=DecisionStatus.CONFLICTING_AUTHORITY,
            expected_answer_permitted=False,
            expected_next_action="escalate_conflict",
        ),
        EvaluationCase(
            case_id="broken-student-cross-reference",
            question="How is a full-time student treated in the needs calculation for a determination on 1 March 2026?",
            expected_status=DecisionStatus.BROKEN_CROSS_REFERENCE,
            expected_answer_permitted=False,
            expected_next_action="explain_broken_cross_reference",
        ),
        EvaluationCase(
            case_id="unsupported-unicorn-rule",
            question="What is a unicorn rule?",
            expected_status=DecisionStatus.INSUFFICIENT_EVIDENCE,
            expected_answer_permitted=False,
            expected_next_action="explain_insufficient_evidence",
        ),
        EvaluationCase(
            case_id="amended-earnings-disregard",
            question="What is the $175 earnings disregard for a determination on 1 April 2026?",
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
            expected_source_amendments=("2026-01 §1.1",),
        ),
        EvaluationCase(
            case_id="paraphrased-household-resources",
            question="How much money can a household have in resources?",
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
        ),
        EvaluationCase(
            case_id="historical-original-earnings-disregard",
            question="What is the earnings disregard for a determination on 1 February 2026?",
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
            expected_source_provisions=("\u00a76.4.1",),
        ),
        EvaluationCase(
            case_id="multi-clause-resource-and-earnings",
            question=(
                "What is the household resource limit and what earnings disregard applies "
                "for a determination on 1 April 2026?"
            ),
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
        ),
        EvaluationCase(
            case_id="calculated-amended-earnings",
            question="What is the $175 earnings disregard for a determination on 1 April 2026?",
            expected_status=DecisionStatus.ANSWERABLE,
            expected_answer_permitted=True,
            expected_next_action="answer",
            expected_source_amendments=("2026-01 \u00a71.1",),
            calculation_gross_monthly_earnings="500",
            expected_calculation_status=CalculationStatus.CALCULATED,
            expected_countable_monthly_earnings="325",
        ),
    )


class GroundedEvaluator:
    """Run deterministic cases through the existing public interface.

    If an :class:`AuditLogger` is supplied, each execution is also appended to
    its JSONL log. The logger remains optional and does not affect comparison.
    """

    def __init__(
        self,
        interface: GroundedPublicInterface | None = None,
        audit_logger: AuditLogger | None = None,
    ):
        self.interface = interface or GroundedPublicInterface()
        self.audit_logger = audit_logger

    def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        if self.audit_logger is None:
            response = self.interface.answer_question(case.question)
        else:
            response = self.audit_logger.record_question(case.question).response

        calculation = None
        if case.calculation_gross_monthly_earnings is not None or case.expected_calculation_status is not None:
            calculation = calculate_monthly_earnings_after_disregard(
                self.interface.pipeline.run(case.question),
                case.calculation_gross_monthly_earnings,
            )

        failures: list[str] = []
        if response.status is not case.expected_status:
            failures.append(
                f"status expected {case.expected_status.value}, got {response.status.value}"
            )
        if response.answer_permitted != case.expected_answer_permitted:
            failures.append(
                "answer_permitted expected "
                f"{case.expected_answer_permitted}, got {response.answer_permitted}"
            )
        if case.expected_next_action is not None and response.next_action != case.expected_next_action:
            failures.append(
                f"next_action expected {case.expected_next_action}, got {response.next_action}"
            )
        missing_amendments = tuple(
            amendment
            for amendment in case.expected_source_amendments
            if amendment not in response.source_amendments
        )
        if missing_amendments:
            failures.append(f"missing source amendments: {missing_amendments}")
        missing_provisions = tuple(
            provision
            for provision in case.expected_source_provisions
            if provision not in response.source_provisions
        )
        if missing_provisions:
            failures.append(f"missing source provisions: {missing_provisions}")

        if case.expected_calculation_status is not None:
            actual_status = None if calculation is None else calculation.status
            if actual_status is not case.expected_calculation_status:
                actual = None if actual_status is None else actual_status.value
                failures.append(
                    "calculation status expected "
                    f"{case.expected_calculation_status.value}, got {actual}"
                )
        if case.expected_countable_monthly_earnings is not None:
            actual_countable = (
                None
                if calculation is None or calculation.calculation is None
                else str(calculation.calculation.countable_monthly_earnings)
            )
            if actual_countable != case.expected_countable_monthly_earnings:
                failures.append(
                    "countable monthly earnings expected "
                    f"{case.expected_countable_monthly_earnings}, got {actual_countable}"
                )
        if case.expected_calculation_status is not None:
            actual_amendment = (
                None
                if calculation is None or calculation.calculation is None
                else calculation.calculation.provenance.amendment_id
            )
            if case.expected_source_amendments and actual_amendment != "2026-01":
                failures.append(f"calculation amendment expected 2026-01, got {actual_amendment}")

        # This is intentionally an explicit invariant: a non-answerable
        # decision must never be reported as permitted by evaluation.
        if response.status is not DecisionStatus.ANSWERABLE and response.answer_permitted:
            failures.append("non-answerable status incorrectly permits an answer")

        return EvaluationResult(
            case_id=case.case_id,
            question=case.question,
            expected_status=case.expected_status,
            actual_status=response.status,
            expected_answer_permitted=case.expected_answer_permitted,
            answer_permitted=response.answer_permitted,
            expected_next_action=case.expected_next_action,
            next_action=response.next_action,
            passed=not failures,
            failures=tuple(failures),
            response=response,
            calculation=calculation,
        )

    def run(self, cases: Iterable[EvaluationCase] | None = None) -> EvaluationReport:
        selected = default_evaluation_cases() if cases is None else tuple(cases)
        return EvaluationReport(tuple(self.evaluate_case(case) for case in selected))


def run_evaluation(
    cases: Iterable[EvaluationCase] | None = None,
    interface: GroundedPublicInterface | None = None,
    audit_logger: AuditLogger | None = None,
) -> EvaluationReport:
    """Convenience function for running the default or supplied cases."""

    return GroundedEvaluator(interface, audit_logger).run(cases)
