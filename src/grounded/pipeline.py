"""Deterministic orchestration of the grounded policy pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Iterable

from .amendments import parse_amendment
from .answer import AnswerResult, GroundedAnswerGenerator
from .decision import DecisionGate, DecisionResult
from .evidence import EvidenceAnalyzer, EvidenceAssessment, EvidenceStatus
from .ingest import parse_policy_manual
from .models import AmendmentRecord, ProvisionRecord
from .question import QuestionSpec, analyze_question
from .retrieval import LexicalRetriever, RetrievalResult
from .temporal import ApplicabilityDecision, ApplicabilityStatus, TemporalApplicabilityResolver


@dataclass(frozen=True)
class PipelineResult:
    """All structured outputs produced for one pipeline invocation."""

    question: str
    question_spec: QuestionSpec
    retrieval_results: tuple[RetrievalResult, ...]
    temporal_decisions: tuple[ApplicabilityDecision, ...]
    evidence_assessment: EvidenceAssessment
    decision: DecisionResult
    answer: AnswerResult

    @property
    def final_answer(self) -> AnswerResult:
        """Alias emphasizing that the answer layer is the final stage."""

        return self.answer


class GroundedPipeline:
    """Connect Steps 7–9 while delegating policy logic to those components."""

    def __init__(
        self,
        provisions: Iterable[ProvisionRecord] | None = None,
        amendments: Iterable[AmendmentRecord] | None = None,
        top_k: int = 20,
        source_root: str | Path | None = None,
    ):
        if provisions is None or amendments is None:
            root = Path(source_root) if source_root is not None else Path(__file__).parents[2]
            if provisions is None:
                provisions = parse_policy_manual(root / "source/original/policy-manual.md")
            if amendments is None:
                amendments = parse_amendment(root / "source/amendment/Amendment No. 2026-01.md")
        self.provisions = tuple(provisions)
        self.amendments = tuple(amendments)
        self.top_k = top_k
        self.retriever = LexicalRetriever(list(self.provisions), list(self.amendments))
        self.temporal_resolver = TemporalApplicabilityResolver(list(self.amendments))
        self.evidence_analyzer = EvidenceAnalyzer(list(self.provisions), list(self.amendments))
        self.decision_gate = DecisionGate()
        self.answer_generator = GroundedAnswerGenerator(self.provisions, self.amendments)

    def run(self, question: str) -> PipelineResult:
        """Run the existing components in their prescribed order."""

        question_spec = analyze_question(question)
        retrieval_query = self._retrieval_query(question_spec)
        retrieval_results = tuple(self.retriever.retrieve(retrieval_query, top_k=self.top_k))
        temporal_decisions = self._resolve_retrieved_provisions(question_spec, retrieval_results)
        evidence = self.evidence_analyzer.assess(question, list(retrieval_results), temporal_decisions)

        # The evidence layer identifies which retrieved records are
        # authoritative. Do not let unrelated contextual candidates with an
        # unresolved date create a gate failure for the actual claim.
        gate_provision_ids = {
            item.provision_id for item in evidence.items if item.applicable
        }
        gate_temporal_decisions = tuple(
            decision for decision in temporal_decisions
            if decision.provision_no in gate_provision_ids
        )
        gate_evidence = replace(
            evidence,
            gaps=tuple(
                gap for gap in evidence.gaps
                if not gap.provision_ids or set(gap.provision_ids) & gate_provision_ids
            ),
        )
        gate_question = self._gate_question(question_spec, evidence, gate_temporal_decisions)
        decision = self.decision_gate.evaluate(
            gate_question,
            gate_evidence,
            gate_temporal_decisions,
            retrieval_results,
        )
        answer = self.answer_generator.generate(
            gate_question,
            decision,
            evidence,
            temporal_decisions,
        )
        return PipelineResult(
            question=question,
            question_spec=question_spec,
            retrieval_results=retrieval_results,
            temporal_decisions=temporal_decisions,
            evidence_assessment=evidence,
            decision=decision,
            answer=answer,
        )

    def _resolve_retrieved_provisions(
        self,
        question: QuestionSpec,
        results: tuple[RetrievalResult, ...],
    ) -> tuple[ApplicabilityDecision, ...]:
        original_by_id = {record.provision_no: record for record in self.provisions}
        decisions: list[ApplicabilityDecision] = []
        seen: set[str] = set()
        for result in results:
            record = result.record
            provision_no = record.provision_no if isinstance(record, ProvisionRecord) else record.target_provision
            if provision_no in seen:
                continue
            seen.add(provision_no)
            decisions.append(
                self.temporal_resolver.resolve(
                    original_by_id.get(provision_no),
                    question.to_date_facts(),
                    provision_no=provision_no,
                )
            )
        return tuple(decisions)

    @staticmethod
    def _retrieval_query(question: QuestionSpec) -> str:
        """Keep date facts for temporal resolution, not lexical noise."""

        query = question.raw_question
        for fact in question.facts_present:
            if fact.kind == "date":
                query = query.replace(fact.raw_text, " ")
        query = re.sub(r"\bfor\s+(?:a\s+)?determination\s+on\b", " ", query, flags=re.IGNORECASE)
        query = re.sub(r"\b(?:determination|decision)\s+on\b", " ", query, flags=re.IGNORECASE)
        query = re.sub(r"\bperiod\s+(?:spanning|from)\b", " period ", query, flags=re.IGNORECASE)
        return query

    @staticmethod
    def _gate_question(
        question: QuestionSpec,
        evidence: EvidenceAssessment,
        temporal_decisions: tuple[ApplicabilityDecision, ...],
    ) -> QuestionSpec:
        """Reconcile only stale generic date requirements with resolved evidence.

        Question analysis currently assigns a determination date to every
        eligibility intent. When evidence is already SUPPORTED and no
        authoritative temporal decision is unresolved, that generic slot is
        not needed for the unaffected provision. This adapter does not infer
        a date or alter the original QuestionSpec stored in PipelineResult.
        """

        unresolved = any(
            decision.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION
            for decision in temporal_decisions
        )
        if evidence.status is not EvidenceStatus.SUPPORTED or unresolved:
            return question
        if not question.missing_required_facts:
            return question
        return replace(
            question,
            missing_required_facts=(),
            ambiguity_flags=tuple(
                flag for flag in question.ambiguity_flags
                if not flag.startswith("Required fact(s) not supplied:")
            ),
            clarification_may_be_required=any(
                not flag.startswith("Required fact(s) not supplied:")
                for flag in question.ambiguity_flags
            ),
        )


def run_pipeline(
    question: str,
    provisions: Iterable[ProvisionRecord] | None = None,
    amendments: Iterable[AmendmentRecord] | None = None,
    top_k: int = 200,
    source_root: str | Path | None = None,
) -> PipelineResult:
    """Convenience wrapper for :class:`GroundedPipeline`."""

    return GroundedPipeline(provisions, amendments, top_k, source_root).run(question)
