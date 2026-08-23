"""Deterministic, source-excerpt grounded answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .decision import DecisionResult, DecisionStatus
from .evidence import EvidenceAssessment, EvidenceItem, EvidenceVersion
from .models import AmendmentRecord, ProvisionRecord
from .question import QuestionSpec
from .temporal import ApplicabilityDecision, Version
from .retrieval import tokenize


@dataclass(frozen=True)
class Citation:
    """Source identity for one grounded answer section."""

    provision_id: str
    amendment_id: str | None
    amendment_paragraph: str | None
    source_document: str


EvidenceReference = Citation


@dataclass(frozen=True)
class AnswerSection:
    """One exact source excerpt, optionally scoped to a sub-question/period."""

    section_id: str
    content: str
    citations: tuple[Citation, ...]
    sub_question_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    version: str | None = None


@dataclass(frozen=True)
class AnswerResult:
    """Structured answer or non-answer; no conversational refusal prose."""

    status: DecisionStatus
    answer_permitted: bool
    sections: tuple[AnswerSection, ...]
    citations: tuple[Citation, ...]
    source_provisions: tuple[str, ...]
    source_amendments: tuple[str, ...]
    warnings: tuple[str, ...]
    refusal_reason: str | None
    missing_facts: tuple[str, ...] = ()
    conflicts: tuple[object, ...] = ()
    gaps: tuple[object, ...] = ()
    next_action: str | None = None


class GroundedAnswerGenerator:
    """Generate only exact source excerpts after the Step 8 gate passes."""

    def __init__(self, provisions: Iterable[ProvisionRecord] = (), amendments: Iterable[AmendmentRecord] = ()):
        self._provisions = {record.provision_no: record for record in provisions}
        self._amendments = {
            (record.amendment_id, record.amendment_paragraph): record
            for record in amendments
        }

    def generate(
        self,
        question: QuestionSpec,
        decision: DecisionResult,
        evidence: EvidenceAssessment,
        temporal_decisions: Iterable[ApplicabilityDecision] = (),
    ) -> AnswerResult:
        """Return source excerpts only when the decision gate permits an answer."""

        decisions = {item.provision_no: item for item in temporal_decisions}
        citations = self._citations(evidence.items)
        source_provisions = tuple(dict.fromkeys(citation.provision_id for citation in citations))
        source_amendments = tuple(
            dict.fromkeys(
                f"{citation.amendment_id} §{citation.amendment_paragraph}"
                for citation in citations
                if citation.amendment_id is not None
            )
        )

        if decision.status is not DecisionStatus.ANSWERABLE or not decision.answer_permitted:
            return self._non_answer(decision, citations, source_provisions, source_amendments)

        items = tuple(item for item in evidence.items if item.applicable and item.relevance_score > 0)
        sections = self._sections(question, items, decisions)
        if not sections:
            return AnswerResult(
                status=decision.status,
                answer_permitted=False,
                sections=(),
                citations=citations,
                source_provisions=source_provisions,
                source_amendments=source_amendments,
                warnings=("NO_APPLICABLE_SOURCE_EXCERPT",),
                refusal_reason="NO_APPLICABLE_SOURCE_EXCERPT",
                missing_facts=decision.missing_facts,
                conflicts=decision.conflicts,
                gaps=decision.gaps,
                next_action="explain_insufficient_evidence",
            )

        section_citations = tuple(
            citation
            for section in sections
            for citation in section.citations
        )
        answer_citations = tuple(dict.fromkeys(section_citations))
        answer_provisions = tuple(dict.fromkeys(citation.provision_id for citation in answer_citations))
        answer_amendments = tuple(
            dict.fromkeys(
                f"{citation.amendment_id} §{citation.amendment_paragraph}"
                for citation in answer_citations
                if citation.amendment_id is not None
            )
        )
        return AnswerResult(
            status=decision.status,
            answer_permitted=True,
            sections=sections,
            citations=answer_citations,
            source_provisions=answer_provisions,
            source_amendments=answer_amendments,
            warnings=(),
            refusal_reason=None,
            next_action="answer",
        )

    def _sections(
        self,
        question: QuestionSpec,
        items: tuple[EvidenceItem, ...],
        decisions: dict[str, ApplicabilityDecision],
    ) -> tuple[AnswerSection, ...]:
        if not items:
            return ()
        if len(question.sub_questions) <= 1:
            return tuple(
                section
                for index, item in enumerate(items, start=1)
                for section in self._item_sections(item, index, None, decisions)
            )

        sections: list[AnswerSection] = []
        for sub_index, sub_question in enumerate(question.sub_questions, start=1):
            terms = set(tokenize(sub_question.text))
            selected = tuple(
                item for item in items
                if terms.intersection(item.matched_terms)
            )
            if not selected:
                return ()
            for item in selected:
                sections.extend(self._item_sections(item, len(sections) + 1, sub_index, decisions))
        return tuple(sections)

    def _item_sections(
        self,
        item: EvidenceItem,
        index: int,
        sub_question_id: int | None,
        decisions: dict[str, ApplicabilityDecision],
    ) -> tuple[AnswerSection, ...]:
        text = self._source_text(item)
        if text is None:
            return ()
        citation = self._citation(item)
        decision = decisions.get(item.provision_id)
        periods = ()
        if decision is not None:
            periods = tuple(
                period for period in decision.periods
                if period.version.value == item.version.value
            )
        if not periods:
            periods = (None,)
        sections: list[AnswerSection] = []
        for period_index, period in enumerate(periods, start=1):
            suffix = f".{period_index}" if len(periods) > 1 else ""
            sections.append(AnswerSection(
                section_id=f"section-{index}{suffix}",
                content=text,
                citations=(citation,),
                sub_question_id=sub_question_id,
                period_start=period.start if period else None,
                period_end=period.end if period else None,
                version=item.version.value,
            ))
        return tuple(sections)

    def _source_text(self, item: EvidenceItem) -> str | None:
        if item.version is EvidenceVersion.ORIGINAL:
            record = self._provisions.get(item.provision_id)
            return record.original_text if record is not None else None
        amendment = self._amendments.get((item.amendment_id, item.amendment_paragraph))
        return amendment.new_text if amendment is not None else None

    @staticmethod
    def _citation(item: EvidenceItem) -> Citation:
        return Citation(
            provision_id=item.provision_id,
            amendment_id=item.amendment_id,
            amendment_paragraph=item.amendment_paragraph,
            source_document=item.source_document,
        )

    @staticmethod
    def _citations(items: Iterable[EvidenceItem]) -> tuple[Citation, ...]:
        return tuple(dict.fromkeys(GroundedAnswerGenerator._citation(item) for item in items))

    @staticmethod
    def _non_answer(
        decision: DecisionResult,
        citations: tuple[Citation, ...],
        source_provisions: tuple[str, ...],
        source_amendments: tuple[str, ...],
    ) -> AnswerResult:
        return AnswerResult(
            status=decision.status,
            answer_permitted=False,
            sections=(),
            citations=citations,
            source_provisions=source_provisions,
            source_amendments=source_amendments,
            warnings=(decision.status.value,),
            refusal_reason=decision.status.value,
            missing_facts=decision.missing_facts,
            conflicts=decision.conflicts,
            gaps=decision.gaps,
            next_action=decision.next_action,
        )


def generate_answer(
    question: QuestionSpec,
    decision: DecisionResult,
    evidence: EvidenceAssessment,
    temporal_decisions: Iterable[ApplicabilityDecision] = (),
    provisions: Iterable[ProvisionRecord] = (),
    amendments: Iterable[AmendmentRecord] = (),
) -> AnswerResult:
    """Convenience wrapper for :class:`GroundedAnswerGenerator`."""

    return GroundedAnswerGenerator(provisions, amendments).generate(
        question, decision, evidence, temporal_decisions
    )
