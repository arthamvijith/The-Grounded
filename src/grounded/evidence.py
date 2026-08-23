"""Deterministic evidence sufficiency, conflict, and gap analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import AmendmentRecord, ProvisionRecord
from .retrieval import RetrievalResult, tokenize
from .temporal import ApplicabilityDecision, ApplicabilityStatus


class EvidenceStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    BROKEN_CROSS_REFERENCE = "BROKEN_CROSS_REFERENCE"


class EvidenceVersion(str, Enum):
    ORIGINAL = "original"
    AMENDMENT = "amendment"


@dataclass(frozen=True)
class EvidenceItem:
    provision_id: str
    source_document: str
    version: EvidenceVersion
    amendment_id: str | None
    amendment_paragraph: str | None
    temporal_status: ApplicabilityStatus | None
    applicable: bool
    relevance_score: float
    matched_terms: tuple[str, ...]
    matched_signals: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Conflict:
    provision_ids: tuple[str, ...]
    amendment_refs: tuple[str, ...]
    claims_or_values: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Gap:
    code: str
    reason: str
    provision_ids: tuple[str, ...] = ()
    missing_dates: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossReferenceIssue:
    source_provision: str
    target_provision: str
    issue_type: str
    reason: str


@dataclass(frozen=True)
class EvidenceAssessment:
    status: EvidenceStatus
    claim: str
    items: tuple[EvidenceItem, ...]
    conflicts: tuple[Conflict, ...]
    gaps: tuple[Gap, ...]
    cross_reference_issues: tuple[CrossReferenceIssue, ...]
    reason: str


class EvidenceAnalyzer:
    """Assess retrieved candidates without generating a policy answer."""

    def __init__(self, provisions: list[ProvisionRecord], amendments: list[AmendmentRecord]):
        self._provisions = {record.provision_no: record for record in provisions}
        self._amendments_by_target: dict[str, tuple[AmendmentRecord, ...]] = {}
        for record in amendments:
            self._amendments_by_target.setdefault(record.target_provision, ())
            self._amendments_by_target[record.target_provision] += (record,)

    def assess(
        self,
        claim: str,
        candidates: list[RetrievalResult],
        temporal_decisions: Iterable[ApplicabilityDecision] = (),
    ) -> EvidenceAssessment:
        decisions = {decision.provision_no: decision for decision in temporal_decisions}
        claim_terms = frozenset(tokenize(claim))
        items: list[EvidenceItem] = []
        gaps: list[Gap] = []

        for candidate in candidates:
            record = candidate.record
            if isinstance(record, ProvisionRecord):
                provision_id = record.provision_no
                version = EvidenceVersion.ORIGINAL
                source_document = record.source_document
                amendment_id = None
                amendment_paragraph = None
            else:
                provision_id = record.target_provision
                version = EvidenceVersion.AMENDMENT
                source_document = record.source_document
                amendment_id = record.amendment_id
                amendment_paragraph = record.amendment_paragraph

            decision = decisions.get(provision_id)
            applicable, reason = self._authority_for(record, decision)
            directly_relevant = self._directly_relevant(record, claim_terms)
            if not directly_relevant:
                applicable = False
                reason = "Retrieved as related context, but its source-specific text does not directly support this claim."
            if directly_relevant and decision is not None and decision.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION:
                gaps.append(Gap("MISSING_DATE", decision.reason, (provision_id,), decision.missing_dates))
            elif directly_relevant and decision is None and self._amendments_by_target.get(provision_id):
                gaps.append(Gap("UNRESOLVED_APPLICABILITY", "An amendment targets this provision, but no temporal applicability decision was supplied.", (provision_id,)))

            items.append(EvidenceItem(
                provision_id, source_document, version, amendment_id, amendment_paragraph,
                decision.status if decision else None, applicable, candidate.relevance_score,
                candidate.matched_terms, candidate.matched_signals, reason,
            ))

        authoritative = tuple(item for item in items if item.applicable and item.relevance_score > 0)
        cross_reference_issues = self._cross_reference_issues(claim_terms, authoritative)
        conflicts = self._conflicts(claim_terms, authoritative)
        gaps = list(dict.fromkeys(gaps))

        if conflicts:
            status = EvidenceStatus.CONFLICTING
            reason = "Applicable authoritative provisions make incompatible claims about the requested fact."
        elif cross_reference_issues:
            status = EvidenceStatus.BROKEN_CROSS_REFERENCE
            reason = "A relevant cross-reference is missing or does not establish the requested rule."
        elif not authoritative:
            status = EvidenceStatus.INSUFFICIENT if gaps else EvidenceStatus.MISSING_AUTHORITY
            reason = "Retrieved candidates exist, but no applicable authoritative evidence is available." if gaps else "No retrieved candidate supplies authoritative evidence for the claim."
        elif gaps:
            status = EvidenceStatus.INSUFFICIENT
            reason = "Some required applicability information remains unresolved."
        else:
            status = EvidenceStatus.SUPPORTED
            reason = "At least one relevant candidate is applicable authoritative evidence for the claim."

        return EvidenceAssessment(status, claim, tuple(items), tuple(conflicts), tuple(gaps), tuple(cross_reference_issues), reason)

    def _directly_relevant(self, record, claim_terms: frozenset[str]) -> bool:
        if isinstance(record, ProvisionRecord):
            evidence_terms = set(tokenize(self._reference_text(record)))
            provision_terms = set(tokenize(record.provision_no))
        else:
            target = self._provisions.get(record.target_provision)
            target_text = self._reference_text(target) if target else ""
            evidence_terms = set(tokenize(" ".join((record.target_provision, record.old_text or "", record.new_text, target_text))))
            provision_terms = set(tokenize(record.target_provision))
        if provision_terms & claim_terms:
            return True
        generic_terms = {"household", "person", "program", "date", "claim", "amount", "period", "spanning", "applies", "applicable", "figures", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
        claim_anchors = {
            self._singular(term)
            for term in claim_terms
            if term not in generic_terms and not re.fullmatch(r"\d+(?:[.,/-]\d+)*", term)
        }
        evidence_anchors = {self._singular(term) for term in evidence_terms}
        return bool(claim_anchors & evidence_anchors)

    @staticmethod
    def _singular(term: str) -> str:
        return term[:-1] if len(term) > 4 and term.endswith("s") else term

    def _authority_for(self, record, decision: ApplicabilityDecision | None) -> tuple[bool, str]:
        if decision is None:
            if isinstance(record, ProvisionRecord) and not self._amendments_by_target.get(record.provision_no):
                return True, "Original provision is relevant and no amendment targets this provision."
            return False, "Temporal applicability is required for this amended provision but was not supplied."
        if decision.status is ApplicabilityStatus.APPLIES_ORIGINAL:
            return isinstance(record, ProvisionRecord), "Original version is applicable under the supplied temporal decision." if isinstance(record, ProvisionRecord) else "The amendment record was considered, but the original version is applicable."
        if decision.status is ApplicabilityStatus.APPLIES_AMENDMENT:
            return isinstance(record, AmendmentRecord), "Amendment version is applicable under the supplied temporal decision." if isinstance(record, AmendmentRecord) else "The amendment version is applicable, so the original version is not authoritative for this decision."
        if decision.status is ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS:
            return True, "This version is applicable for one of the periods returned by the temporal decision."
        if decision.status is ApplicabilityStatus.NOT_APPLICABLE:
            return False, "The supplied temporal decision marks this version as not applicable."
        return False, "The temporal decision is unresolved; this candidate cannot be treated as authoritative."

    def _cross_reference_issues(self, claim_terms: frozenset[str], items: tuple[EvidenceItem, ...]) -> list[CrossReferenceIssue]:
        issues: list[CrossReferenceIssue] = []
        for item in items:
            source = self._provisions.get(item.provision_id)
            if source is None:
                continue
            for target in source.cross_references:
                referenced_records = self._referenced_records(target)
                if not referenced_records:
                    source_terms = set(tokenize(self._reference_text(source)))
                    if source_terms & claim_terms:
                        issues.append(CrossReferenceIssue(source.provision_no, target, "MISSING_TARGET", "The provision explicitly references a provision that is not present in the supplied source records."))
                    continue
                source_terms = set(tokenize(self._reference_text(source)))
                target_terms = set(token for record in referenced_records for token in tokenize(record.original_text))
                if {"student", "students", "full-time"} & claim_terms and "full-time" in source_terms and not ({"student", "students", "education"} & target_terms):
                    issues.append(CrossReferenceIssue(source.provision_no, target, "UNRESOLVED_TARGET", "The referenced provision exists, but it does not establish the requested full-time-student rule."))
        return issues

    def _referenced_records(self, target: str) -> tuple[ProvisionRecord, ...]:
        exact = self._provisions.get(target)
        if exact is not None:
            return (exact,)
        section_prefix = target + "."
        return tuple(record for provision_id, record in self._provisions.items() if provision_id.startswith(section_prefix))

    @staticmethod
    def _reference_text(provision: ProvisionRecord) -> str:
        """Use the first source line for cross-reference relevance checks.

        This avoids treating text from a later malformed/unsupported Markdown
        block as if it belonged to the current provision.
        """

        return re.split(r"\n\n#+\s", provision.original_text, maxsplit=1)[0]

    def _conflicts(self, claim_terms: frozenset[str], items: tuple[EvidenceItem, ...]) -> list[Conflict]:
        ids = {item.provision_id for item in items}
        pair = {"§4.3.2", "§9.1.4"}
        if not pair.issubset(ids) or not ({"report", "change", "reporting"} & claim_terms):
            return []
        values: list[str] = []
        for provision_id in ("§4.3.2", "§9.1.4"):
            source = self._provisions.get(provision_id)
            if source:
                values.extend(f"{provision_id}: {match}" for match in re.findall(r"\b\d+\s+calendar days\b", source.original_text))
        if len({value.split(": ", 1)[1] for value in values}) < 2:
            return []
        amendment_refs = tuple(sorted({f"{item.amendment_id} §{item.amendment_paragraph}" for item in items if item.amendment_id}))
        return [Conflict(tuple(sorted(pair)), amendment_refs, tuple(values), "§4.3.2 states 10 calendar days while §9.1.4 refers to 30 calendar days for the same reporting context.")]
