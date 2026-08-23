"""Small deterministic calculations backed by resolved policy evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TYPE_CHECKING

from .decision import DecisionStatus
from .resolved import ResolvedProvision

if TYPE_CHECKING:
    from .pipeline import PipelineResult


class CalculationStatus(str, Enum):
    CALCULATED = "CALCULATED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CalculationProvenance:
    source_document: str
    provision_id: str
    version: str
    amendment_id: str | None
    amendment_paragraph: str | None
    period_start: object | None
    period_end: object | None


@dataclass(frozen=True)
class EarningsCalculation:
    gross_monthly_earnings: Decimal
    disregard: Decimal
    countable_monthly_earnings: Decimal
    provenance: CalculationProvenance


@dataclass(frozen=True)
class CalculationResult:
    status: CalculationStatus
    calculation: EarningsCalculation | None
    reason: str
    missing_inputs: tuple[str, ...] = ()
    policy_status: DecisionStatus | None = None


_DISREGARD_RE = re.compile(r"\$(\d[\d,]*(?:\.\d+)?)\s+per\s+month", re.IGNORECASE)
_SUPPORTED_PROVISION = "§6.4.1"


def calculate_monthly_earnings_after_disregard(
    pipeline_result: PipelineResult,
    gross_monthly_earnings: Decimal | int | str | None,
) -> CalculationResult:
    """Calculate countable monthly employment earnings from §6.4.1(a).

    This function accepts only a completed pipeline result. It uses an
    applicable ``ResolvedProvision`` and never selects an amendment itself.
    The calculation is ``gross - min(gross, disregard)`` because the source
    rule says the first stated monthly amount is disregarded.
    """

    if pipeline_result.decision.status is not DecisionStatus.ANSWERABLE or not pipeline_result.decision.answer_permitted:
        return CalculationResult(
            status=CalculationStatus.BLOCKED,
            calculation=None,
            reason="The existing decision gate did not permit a policy answer.",
            policy_status=pipeline_result.decision.status,
        )
    if pipeline_result.validation is None or not pipeline_result.validation.valid:
        return CalculationResult(
            status=CalculationStatus.BLOCKED,
            calculation=None,
            reason="The generated grounded result did not pass output validation.",
            policy_status=pipeline_result.decision.status,
        )

    if gross_monthly_earnings is None:
        return CalculationResult(
            status=CalculationStatus.NEEDS_CLARIFICATION,
            calculation=None,
            reason="Gross monthly employment earnings are required.",
            missing_inputs=("gross_monthly_earnings",),
            policy_status=pipeline_result.decision.status,
        )

    try:
        gross = Decimal(str(gross_monthly_earnings))
    except (InvalidOperation, ValueError):
        return CalculationResult(
            status=CalculationStatus.NEEDS_CLARIFICATION,
            calculation=None,
            reason="Gross monthly employment earnings must be a numeric amount.",
            missing_inputs=("gross_monthly_earnings",),
            policy_status=pipeline_result.decision.status,
        )
    if not gross.is_finite() or gross < 0:
        return CalculationResult(
            status=CalculationStatus.NEEDS_CLARIFICATION,
            calculation=None,
            reason="Gross monthly employment earnings must be a finite non-negative amount.",
            missing_inputs=("gross_monthly_earnings",),
            policy_status=pipeline_result.decision.status,
        )

    authoritative = {
        item.provision_id
        for item in pipeline_result.evidence_assessment.items
        if item.provision_id == _SUPPORTED_PROVISION and item.applicable and item.relevance_score > 0
    }
    applicable = tuple(
        provision for provision in pipeline_result.resolved_provisions
        if provision.applicable and provision.provision_id == _SUPPORTED_PROVISION
    )
    if not authoritative or not applicable:
        return CalculationResult(
            status=CalculationStatus.INSUFFICIENT_EVIDENCE,
            calculation=None,
            reason="Applicable authoritative evidence for the §6.4.1(a) earnings disregard is not available.",
            policy_status=pipeline_result.decision.status,
        )
    if len(applicable) != 1:
        return CalculationResult(
            status=CalculationStatus.UNSUPPORTED,
            calculation=None,
            reason="This small calculation does not calculate a period containing multiple disregard versions.",
            policy_status=pipeline_result.decision.status,
        )

    provision = applicable[0]
    match = _DISREGARD_RE.search(provision.text)
    if match is None:
        return CalculationResult(
            status=CalculationStatus.INSUFFICIENT_EVIDENCE,
            calculation=None,
            reason="The applicable resolved provision does not state a supported monthly earnings disregard.",
            policy_status=pipeline_result.decision.status,
        )
    disregard = Decimal(match.group(1).replace(",", ""))
    countable = gross - min(gross, disregard)
    provenance = CalculationProvenance(
        source_document=provision.source_document,
        provision_id=provision.provision_id,
        version=provision.version.value,
        amendment_id=provision.amendment_id,
        amendment_paragraph=provision.amendment_paragraph,
        period_start=provision.period_start,
        period_end=provision.period_end,
    )
    return CalculationResult(
        status=CalculationStatus.CALCULATED,
        calculation=EarningsCalculation(gross, disregard, countable, provenance),
        reason="Calculated from the applicable resolved §6.4.1(a) employment-earnings disregard.",
        policy_status=pipeline_result.decision.status,
    )
