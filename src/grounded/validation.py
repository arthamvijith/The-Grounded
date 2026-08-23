"""Deterministic validation of grounded answer results.

The current answer contract is an exact source-excerpt contract.  This module
checks that contract after answer generation; it does not resolve policy dates
or decide whether evidence is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from .answer import AnswerResult, AnswerSection, Citation
from .decision import DecisionResult, DecisionStatus
from .evidence import EvidenceAssessment, EvidenceItem, EvidenceVersion
from .resolved import ResolvedProvision
from .temporal import ApplicabilityDecision, ApplicabilityStatus


class ValidationStatus(str, Enum):
    """Whether the generated structured result passed its active contract."""

    VALID = "VALID"
    REJECTED = "REJECTED"


class ValidationMode(str, Enum):
    """Validation contract used for the generated answer."""

    EXACT_SOURCE_EXCERPT = "EXACT_SOURCE_EXCERPT"


@dataclass(frozen=True)
class ValidationResult:
    """Structured validation outcome; it contains no replacement answer."""

    status: ValidationStatus
    valid: bool
    answer_permitted: bool
    mode: ValidationMode
    reasons: tuple[str, ...]


class GroundedAnswerValidator:
    """Validate answers against evidence and already-resolved provisions."""

    def validate(
        self,
        answer: AnswerResult,
        decision: DecisionResult,
        evidence: EvidenceAssessment,
        temporal_decisions: Iterable[ApplicabilityDecision],
        resolved_provisions: Iterable[ResolvedProvision],
    ) -> ValidationResult:
        reasons: list[str] = []
        temporal = {item.provision_no: item for item in temporal_decisions}
        resolved = tuple(resolved_provisions)
        authoritative = self._authoritative_items(evidence.items)

        if answer.status is not decision.status:
            reasons.append("ANSWER_STATUS_DOES_NOT_MATCH_DECISION")
        if decision.status is not DecisionStatus.ANSWERABLE or not decision.answer_permitted:
            if answer.sections:
                reasons.append("NON_ANSWERABLE_RESULT_HAS_SUBSTANTIVE_SECTIONS")
            if answer.answer_permitted:
                reasons.append("NON_ANSWERABLE_RESULT_PERMITS_ANSWER")
        else:
            if not answer.answer_permitted:
                reasons.append("ANSWERABLE_DECISION_DOES_NOT_PERMIT_ANSWER")
            if not answer.sections:
                reasons.append("ANSWERABLE_RESULT_HAS_NO_SUBSTANTIVE_SECTIONS")
            for section in answer.sections:
                self._validate_section(section, authoritative, temporal, resolved, reasons)
            for citation in answer.citations:
                if not self._citation_matches_authority(citation, authoritative):
                    reasons.append("CITATION_NOT_AUTHORITATIVE")
            section_citations = {
                citation
                for section in answer.sections
                for citation in section.citations
            }
            if not section_citations.issubset(set(answer.citations)):
                reasons.append("SECTION_CITATION_NOT_IN_RESULT_CITATIONS")

        valid = not reasons
        return ValidationResult(
            status=ValidationStatus.VALID if valid else ValidationStatus.REJECTED,
            valid=valid,
            answer_permitted=answer.answer_permitted if valid else False,
            mode=ValidationMode.EXACT_SOURCE_EXCERPT,
            reasons=tuple(dict.fromkeys(reasons)),
        )

    @staticmethod
    def _authoritative_items(items: Iterable[EvidenceItem]) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in items if item.applicable and item.relevance_score > 0)

    def _validate_section(
        self,
        section: AnswerSection,
        authoritative: tuple[EvidenceItem, ...],
        temporal: dict[str, ApplicabilityDecision],
        resolved: tuple[ResolvedProvision, ...],
        reasons: list[str],
    ) -> None:
        if not section.citations:
            reasons.append("SECTION_MISSING_CITATION")
            return
        for citation in section.citations:
            if not self._citation_matches_authority(citation, authoritative):
                reasons.append("CITATION_NOT_AUTHORITATIVE")
                continue
            item = self._matching_item(citation, authoritative)
            if item is None:
                continue
            candidates = tuple(
                item for item in resolved
                if item.applicable
                and item.provision_id == citation.provision_id
                and item.source_document == citation.source_document
                and self._version_matches(item, citation)
            )
            if not candidates:
                reasons.append("CITATION_HAS_NO_APPLICABLE_RESOLVED_PROVISION")
                continue
            if not self._temporal_matches(candidates, temporal.get(citation.provision_id)):
                reasons.append("CITATION_TEMPORAL_RESULT_MISMATCH")
            if not any(candidate.text == section.content for candidate in candidates):
                reasons.append("ANSWER_TEXT_DOES_NOT_MATCH_SOURCE_EVIDENCE")
            if section.period_start is not None or section.period_end is not None:
                if not any(
                    candidate.period_start == section.period_start
                    and candidate.period_end == section.period_end
                    for candidate in candidates
                ):
                    reasons.append("ANSWER_PERIOD_DOES_NOT_MATCH_RESOLVED_PERIOD")
            elif any(candidate.temporal_status is ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS for candidate in candidates):
                reasons.append("MULTI_PERIOD_SECTION_MISSING_PERIOD")

    @staticmethod
    def _matching_item(citation: Citation, items: tuple[EvidenceItem, ...]) -> EvidenceItem | None:
        for item in items:
            if (
                item.provision_id == citation.provision_id
                and item.amendment_id == citation.amendment_id
                and item.amendment_paragraph == citation.amendment_paragraph
                and item.source_document == citation.source_document
            ):
                return item
        return None

    @classmethod
    def _citation_matches_authority(cls, citation: Citation, items: tuple[EvidenceItem, ...]) -> bool:
        return cls._matching_item(citation, items) is not None

    @staticmethod
    def _version_matches(provision: ResolvedProvision, citation: Citation) -> bool:
        if provision.provenance.source_document != citation.source_document:
            return False
        if provision.provenance.provision_id != citation.provision_id:
            return False
        if citation.amendment_id is None:
            return provision.version.value == EvidenceVersion.ORIGINAL.value and provision.amendment_paragraph is None
        return (
            provision.version.value == EvidenceVersion.AMENDMENT.value
            and provision.amendment_id == citation.amendment_id
            and provision.amendment_paragraph == citation.amendment_paragraph
        )

    @staticmethod
    def _temporal_matches(
        provisions: tuple[ResolvedProvision, ...],
        decision: ApplicabilityDecision | None,
    ) -> bool:
        if decision is None:
            return False
        return all(provision.temporal_status is decision.status for provision in provisions)


def validate_answer(
    answer: AnswerResult,
    decision: DecisionResult,
    evidence: EvidenceAssessment,
    temporal_decisions: Iterable[ApplicabilityDecision],
    resolved_provisions: Iterable[ResolvedProvision],
) -> ValidationResult:
    """Validate one generated answer using only earlier-layer outputs."""

    return GroundedAnswerValidator().validate(
        answer, decision, evidence, temporal_decisions, resolved_provisions
    )


def fail_closed_answer(
    answer: AnswerResult,
    decision: DecisionResult,
    validation: ValidationResult,
) -> AnswerResult:
    """Return a non-substantive result when validation rejects an answer.

    Existing non-answer statuses are preserved.  An answerable result that
    fails its output contract is downgraded to the existing
    ``INSUFFICIENT_EVIDENCE`` safety status; no policy conclusion is added.
    """

    if validation.valid:
        return answer
    status = decision.status if decision.status is not DecisionStatus.ANSWERABLE else DecisionStatus.INSUFFICIENT_EVIDENCE
    next_action = decision.next_action if status is not DecisionStatus.INSUFFICIENT_EVIDENCE else "explain_insufficient_evidence"
    return replace(
        answer,
        status=status,
        answer_permitted=False,
        sections=(),
        warnings=tuple(dict.fromkeys((*answer.warnings, "VALIDATION_REJECTED"))),
        refusal_reason="VALIDATION_REJECTED",
        missing_facts=decision.missing_facts,
        conflicts=decision.conflicts,
        gaps=decision.gaps,
        next_action=next_action,
    )
