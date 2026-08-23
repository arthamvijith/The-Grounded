"""Small public interface for the complete grounded pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .answer import AnswerSection, Citation
from .calculation import CalculationResult, calculate_monthly_earnings_after_disregard
from .decision import DecisionStatus

if TYPE_CHECKING:
    from .pipeline import GroundedPipeline


@dataclass(frozen=True)
class PublicGroundedResponse:
    """Safe structured response exposed to a caller of the project."""

    question: str
    status: DecisionStatus
    answer_permitted: bool
    sections: tuple[AnswerSection, ...]
    citations: tuple[Citation, ...]
    source_provisions: tuple[str, ...]
    source_amendments: tuple[str, ...]
    missing_facts: tuple[str, ...]
    conflicts: tuple[object, ...]
    gaps: tuple[object, ...]
    refusal_reason: str | None
    next_action: str | None
    warnings: tuple[str, ...] = ()
    calculation: CalculationResult | None = None


class GroundedPublicInterface:
    """Public entry point that delegates execution to :class:`GroundedPipeline`."""

    def __init__(self, pipeline: GroundedPipeline | None = None):
        if pipeline is None:
            from .pipeline import GroundedPipeline

            pipeline = GroundedPipeline()
        self.pipeline = pipeline

    def answer_question(
        self,
        question: str,
        gross_monthly_earnings: str | int | None = None,
    ) -> PublicGroundedResponse:
        """Run one question and expose only the structured grounded result."""

        result = self.pipeline.run(question)
        answer = result.final_answer
        calculation = (
            calculate_monthly_earnings_after_disregard(result, gross_monthly_earnings)
            if gross_monthly_earnings is not None
            else None
        )

        # Keep the Step 8 decision authoritative even if a future answer-layer
        # implementation accidentally returns an inconsistent object.
        if result.decision.status is not DecisionStatus.ANSWERABLE:
            answer = replace(
                answer,
                status=result.decision.status,
                answer_permitted=False,
                sections=(),
                refusal_reason=answer.refusal_reason or result.decision.status.value,
                missing_facts=result.decision.missing_facts,
                conflicts=result.decision.conflicts,
                gaps=result.decision.gaps,
                next_action=result.decision.next_action,
            )

        return PublicGroundedResponse(
            question=result.question,
            status=answer.status,
            answer_permitted=answer.answer_permitted,
            sections=answer.sections,
            citations=answer.citations,
            source_provisions=answer.source_provisions,
            source_amendments=answer.source_amendments,
            missing_facts=answer.missing_facts,
            conflicts=answer.conflicts,
            gaps=answer.gaps,
            refusal_reason=answer.refusal_reason,
            next_action=answer.next_action,
            warnings=answer.warnings,
            calculation=calculation,
        )


def answer_question(
    question: str,
    pipeline: GroundedPipeline | None = None,
    gross_monthly_earnings: str | int | None = None,
) -> PublicGroundedResponse:
    """Convenience function for callers that do not need a persistent interface."""

    return GroundedPublicInterface(pipeline).answer_question(question, gross_monthly_earnings)
