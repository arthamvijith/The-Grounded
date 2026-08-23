"""Deterministic answerability gate for structured policy evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from .evidence import EvidenceAssessment, EvidenceStatus
from .question import QuestionSpec
from .retrieval import RetrievalResult, tokenize
from .temporal import ApplicabilityDecision, ApplicabilityStatus


class DecisionStatus(str, Enum):
    """Machine-readable result of the answerability gate."""

    ANSWERABLE = "ANSWERABLE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_AUTHORITY = "CONFLICTING_AUTHORITY"
    BROKEN_CROSS_REFERENCE = "BROKEN_CROSS_REFERENCE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class DecisionResult:
    """Structured gate output; it deliberately contains no answer prose."""

    status: DecisionStatus
    answer_permitted: bool
    reasons: tuple[str, ...]
    missing_facts: tuple[str, ...]
    conflicts: tuple[object, ...]
    gaps: tuple[object, ...]
    relevant_provisions: tuple[str, ...]
    applicable_amendments: tuple[str, ...]
    evidence_status: EvidenceStatus
    next_action: str
    unanswered_sub_questions: tuple[str, ...] = ()


_OUT_OF_SCOPE_PATTERNS = (
    r"\b(weather|recipe|football|sports|stock market|municipal licensing)\b",
    r"\b(quantum spacecraft|tax return|immigration advice|programming help)\b",
)


class DecisionGate:
    """Apply only gate rules to outputs already produced by earlier layers."""

    def evaluate(
        self,
        question: QuestionSpec,
        evidence: EvidenceAssessment,
        temporal_decisions: Iterable[ApplicabilityDecision] = (),
        retrieval_results: Iterable[RetrievalResult] = (),
    ) -> DecisionResult:
        decisions = tuple(temporal_decisions)
        relevant = tuple(dict.fromkeys(item.provision_id for item in evidence.items))
        amendments = tuple(
            dict.fromkeys(
                f"{record.amendment_id} §{record.amendment_paragraph}"
                for decision in decisions
                for record in decision.applicable_amendments
            )
        )
        missing = self._missing_facts(question, evidence, decisions)
        reasons: list[str] = []

        # The explicit scope check is intentionally narrow. An unknown or
        # poorly retrieved policy question is not automatically out of scope.
        if self._is_explicitly_out_of_scope(question.raw_question):
            reasons.append("The question explicitly concerns a subject outside the supplied policy corpus.")
            return self._result(
                DecisionStatus.OUT_OF_SCOPE, reasons, missing, evidence,
                relevant, amendments, "explain_out_of_scope",
            )

        if missing or self._has_unresolved_date_ambiguity(question, decisions):
            if missing:
                reasons.append("Required facts or dates are missing or unresolved: " + ", ".join(missing) + ".")
            else:
                reasons.append("A supplied date has an unresolved policy role.")
            return self._result(
                DecisionStatus.NEEDS_CLARIFICATION, reasons, missing, evidence,
                relevant, amendments, "request_missing_facts",
            )

        if evidence.cross_reference_issues or evidence.status is EvidenceStatus.BROKEN_CROSS_REFERENCE:
            reasons.append("A material cross-reference issue prevents a safe policy conclusion.")
            return self._result(
                DecisionStatus.BROKEN_CROSS_REFERENCE, reasons, missing, evidence,
                relevant, amendments, "explain_broken_cross_reference",
            )

        if evidence.conflicts or evidence.status is EvidenceStatus.CONFLICTING:
            reasons.append("The evidence layer reports unresolved conflicting authority.")
            return self._result(
                DecisionStatus.CONFLICTING_AUTHORITY, reasons, missing, evidence,
                relevant, amendments, "escalate_conflict",
            )

        unanswered = self._unanswered_sub_questions(question, evidence)
        if evidence.status is not EvidenceStatus.SUPPORTED or unanswered:
            if unanswered:
                reasons.append("Not every sub-question has directly applicable authoritative evidence.")
            else:
                reasons.append(evidence.reason)
            return self._result(
                DecisionStatus.INSUFFICIENT_EVIDENCE, reasons, missing, evidence,
                relevant, amendments, "explain_insufficient_evidence", unanswered,
            )

        # A supported assessment must still contain applicable, relevant
        # evidence. A retrieval score by itself can never pass this gate.
        authoritative = tuple(item for item in evidence.items if item.applicable and item.relevance_score > 0)
        if not authoritative:
            reasons.append("Retrieval results do not by themselves establish authoritative policy evidence.")
            return self._result(
                DecisionStatus.INSUFFICIENT_EVIDENCE, reasons, missing, evidence,
                relevant, amendments, "explain_insufficient_evidence",
            )

        reasons.append("Required facts, temporal applicability, and authoritative evidence passed the decision gate.")
        return self._result(
            DecisionStatus.ANSWERABLE, reasons, missing, evidence,
            relevant, amendments, "answer",
        )

    @staticmethod
    def _missing_facts(
        question: QuestionSpec,
        evidence: EvidenceAssessment,
        decisions: tuple[ApplicabilityDecision, ...],
    ) -> tuple[str, ...]:
        values = list(question.missing_required_facts)
        for decision in decisions:
            if decision.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION:
                values.extend(decision.missing_dates)
        for gap in evidence.gaps:
            values.extend(gap.missing_dates)
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _has_unresolved_date_ambiguity(
        question: QuestionSpec,
        decisions: tuple[ApplicabilityDecision, ...],
    ) -> bool:
        if any("role" in flag.lower() or "ambiguous" in flag.lower() for flag in question.ambiguity_flags):
            return True
        return any(decision.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION for decision in decisions)

    @staticmethod
    def _is_explicitly_out_of_scope(text: str) -> bool:
        lower = text.lower()
        return any(re.search(pattern, lower) for pattern in _OUT_OF_SCOPE_PATTERNS)

    @staticmethod
    def _unanswered_sub_questions(question: QuestionSpec, evidence: EvidenceAssessment) -> tuple[str, ...]:
        if len(question.sub_questions) <= 1:
            return ()
        evidence_terms = {
            term
            for item in evidence.items
            if item.applicable and item.relevance_score > 0
            for term in item.matched_terms
        }
        unanswered: list[str] = []
        for sub_question in question.sub_questions:
            terms = set(tokenize(sub_question.text))
            if terms and not terms.intersection(evidence_terms):
                unanswered.append(sub_question.text)
        return tuple(unanswered)

    @staticmethod
    def _result(
        status: DecisionStatus,
        reasons: list[str],
        missing: tuple[str, ...],
        evidence: EvidenceAssessment,
        relevant: tuple[str, ...],
        amendments: tuple[str, ...],
        next_action: str,
        unanswered: tuple[str, ...] = (),
    ) -> DecisionResult:
        conflicts = tuple(
            replace(conflict, claims_or_values=tuple(dict.fromkeys(conflict.claims_or_values)))
            for conflict in evidence.conflicts
        )
        return DecisionResult(
            status=status,
            answer_permitted=status is DecisionStatus.ANSWERABLE,
            reasons=tuple(dict.fromkeys(reasons)),
            missing_facts=missing,
            conflicts=conflicts,
            gaps=evidence.gaps,
            relevant_provisions=relevant,
            applicable_amendments=amendments,
            evidence_status=evidence.status,
            next_action=next_action,
            unanswered_sub_questions=unanswered,
        )


def decide(
    question: QuestionSpec,
    evidence: EvidenceAssessment,
    temporal_decisions: Iterable[ApplicabilityDecision] = (),
    retrieval_results: Iterable[RetrievalResult] = (),
) -> DecisionResult:
    """Convenience wrapper around :class:`DecisionGate`."""

    return DecisionGate().evaluate(question, evidence, temporal_decisions, retrieval_results)
