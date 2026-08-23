"""Query-specific projections of temporally resolved policy provisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .models import AmendmentRecord, ProvisionRecord
from .temporal import ApplicabilityDecision, ApplicabilityStatus, Version


@dataclass(frozen=True)
class ResolvedProvenance:
    """Source identity retained by one resolved provision projection."""

    source_document: str
    provision_id: str
    source_start: int | None
    source_end: int | None
    source_version: str
    amendment_id: str | None = None
    amendment_paragraph: str | None = None


@dataclass(frozen=True)
class ResolvedProvision:
    """One source version projected for one temporal applicability decision.

    The object is a view over existing source records and resolver output. It
    is never written back into the original policy or amendment documents.
    ``applicable`` distinguishes the selected version from non-applicable or
    unresolved candidate versions retained for auditability.
    """

    provision_id: str
    version: Version
    text: str
    source_document: str
    amendment_id: str | None
    amendment_paragraph: str | None
    temporal_status: ApplicabilityStatus
    applicable: bool
    period_start: date | None
    period_end: date | None
    applicability_reason: str
    provenance: ResolvedProvenance
    temporal_decision: ApplicabilityDecision


class ResolvedProvisionProjector:
    """Project existing temporal decisions without resolving them again."""

    def __init__(
        self,
        provisions: Iterable[ProvisionRecord],
        amendments: Iterable[AmendmentRecord],
    ):
        self._provisions = {record.provision_no: record for record in provisions}
        self._amendments = {
            (record.amendment_id, record.amendment_paragraph): record
            for record in amendments
        }

    def project(
        self,
        decisions: Iterable[ApplicabilityDecision],
    ) -> tuple[ResolvedProvision, ...]:
        """Return deterministic source-version projections for decisions."""

        resolved: list[ResolvedProvision] = []
        for decision in decisions:
            resolved.extend(self._project_decision(decision))
        return tuple(resolved)

    def _project_decision(self, decision: ApplicabilityDecision) -> tuple[ResolvedProvision, ...]:
        original = self._provisions.get(decision.provision_no)
        considered = tuple(
            record for record in decision.considered_amendments
            if (record.amendment_id, record.amendment_paragraph) in self._amendments
        )
        output: list[ResolvedProvision] = []

        if decision.status is ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS:
            for period in decision.periods:
                if period.version is Version.ORIGINAL:
                    if original is not None:
                        output.append(self._original(original, decision, True, period.start, period.end, period.reason))
                else:
                    records = self._period_amendments(period.amendment_paragraphs, considered)
                    for record in records:
                        output.append(self._amendment(record, decision, True, period.start, period.end, period.reason))
            return tuple(output)

        if decision.status is ApplicabilityStatus.APPLIES_ORIGINAL:
            if original is not None:
                period = decision.periods[0] if decision.periods else None
                output.append(self._original(
                    original, decision, True,
                    period.start if period else None,
                    period.end if period else None,
                    decision.reason,
                ))
            for record in considered:
                output.append(self._amendment(record, decision, False, None, None, decision.reason))
            return tuple(output)

        if decision.status is ApplicabilityStatus.APPLIES_AMENDMENT:
            if original is not None:
                output.append(self._original(original, decision, False, None, None, decision.reason))
            for record in decision.applicable_amendments:
                output.append(self._amendment(record, decision, True, self._period_start(decision), self._period_end(decision), decision.reason))
            return tuple(output)

        if original is not None:
            output.append(self._original(original, decision, False, None, None, decision.reason))
        for record in considered:
            output.append(self._amendment(record, decision, False, None, None, decision.reason))
        return tuple(output)

    @staticmethod
    def _period_amendments(
        paragraphs: tuple[str, ...],
        records: tuple[AmendmentRecord, ...],
    ) -> tuple[AmendmentRecord, ...]:
        if not paragraphs:
            return records
        selected = tuple(record for record in records if record.amendment_paragraph in paragraphs)
        return selected or records

    @staticmethod
    def _period_start(decision: ApplicabilityDecision) -> date | None:
        return decision.periods[0].start if decision.periods else None

    @staticmethod
    def _period_end(decision: ApplicabilityDecision) -> date | None:
        return decision.periods[0].end if decision.periods else None

    @staticmethod
    def _original(
        record: ProvisionRecord,
        decision: ApplicabilityDecision,
        applicable: bool,
        period_start: date | None,
        period_end: date | None,
        reason: str,
    ) -> ResolvedProvision:
        provenance = ResolvedProvenance(
            source_document=record.source_document,
            provision_id=record.provision_no,
            source_start=record.source_start,
            source_end=record.source_end,
            source_version=record.source_version,
        )
        return ResolvedProvisions._make(
            record.provision_no, Version.ORIGINAL, record.original_text,
            record.source_document, None, None, decision, applicable,
            period_start, period_end, reason, provenance,
        )

    @staticmethod
    def _amendment(
        record: AmendmentRecord,
        decision: ApplicabilityDecision,
        applicable: bool,
        period_start: date | None,
        period_end: date | None,
        reason: str,
    ) -> ResolvedProvision:
        provenance = ResolvedProvenance(
            source_document=record.source_document,
            provision_id=record.target_provision,
            source_start=record.source_start,
            source_end=record.source_end,
            source_version=f"Amendment No. {record.amendment_id}",
            amendment_id=record.amendment_id,
            amendment_paragraph=record.amendment_paragraph,
        )
        return ResolvedProvisions._make(
            record.target_provision, Version.AMENDMENT, record.new_text,
            record.source_document, record.amendment_id, record.amendment_paragraph,
            decision, applicable, period_start, period_end, reason, provenance,
        )


class ResolvedProvisions:
    """Small construction helper kept private to the projection module."""

    @staticmethod
    def _make(
        provision_id: str,
        version: Version,
        text: str,
        source_document: str,
        amendment_id: str | None,
        amendment_paragraph: str | None,
        decision: ApplicabilityDecision,
        applicable: bool,
        period_start: date | None,
        period_end: date | None,
        reason: str,
        provenance: ResolvedProvenance,
    ) -> ResolvedProvision:
        return ResolvedProvision(
            provision_id=provision_id,
            version=version,
            text=text,
            source_document=source_document,
            amendment_id=amendment_id,
            amendment_paragraph=amendment_paragraph,
            temporal_status=decision.status,
            applicable=applicable,
            period_start=period_start,
            period_end=period_end,
            applicability_reason=reason,
            provenance=provenance,
            temporal_decision=decision,
        )


def project_resolved_provisions(
    decisions: Iterable[ApplicabilityDecision],
    provisions: Iterable[ProvisionRecord],
    amendments: Iterable[AmendmentRecord],
) -> tuple[ResolvedProvision, ...]:
    """Convenience wrapper for the deterministic temporal projection."""

    return ResolvedProvisionProjector(provisions, amendments).project(decisions)
