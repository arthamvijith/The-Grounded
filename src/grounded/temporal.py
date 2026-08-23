"""Date-sensitive applicability resolution for policy amendments.

This module produces applicability metadata only. It never rewrites a
provision, applies amendment text, resolves conflicts, or answers a policy
question.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from .models import AmendmentRecord, ProvisionRecord


class ApplicabilityStatus(str, Enum):
    APPLIES_ORIGINAL = "APPLIES_ORIGINAL"
    APPLIES_AMENDMENT = "APPLIES_AMENDMENT"
    APPLIES_MULTIPLE_PERIODS = "APPLIES_MULTIPLE_PERIODS"
    INSUFFICIENT_DATE_INFORMATION = "INSUFFICIENT_DATE_INFORMATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class DateFacts:
    """Dates supplied for the specific claim or policy issue.

    ``reporting_date`` is retained separately for callers, but Amendment
    No. 2026-01 makes reporting applicability depend on ``change_date``.
    """

    determination_date: date | None = None
    change_date: date | None = None
    reporting_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None


class Version(str, Enum):
    ORIGINAL = "original"
    AMENDMENT = "amendment"


@dataclass(frozen=True)
class ApplicablePeriod:
    """An inclusive period and the source version applicable to it."""

    start: date | None
    end: date | None
    version: Version
    amendment_paragraphs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ApplicabilityDecision:
    """Explainable result of resolving one provision against date facts."""

    status: ApplicabilityStatus
    provision_no: str
    original_provision: ProvisionRecord | None
    considered_amendments: tuple[AmendmentRecord, ...]
    applicable_amendments: tuple[AmendmentRecord, ...]
    periods: tuple[ApplicablePeriod, ...]
    reason: str
    missing_dates: tuple[str, ...] = ()


class TemporalApplicabilityResolver:
    """Resolve amendment applicability without producing merged policy text."""

    def __init__(self, amendments: list[AmendmentRecord]):
        self._amendments = tuple(amendments)

    def resolve(
        self,
        provision: ProvisionRecord | None,
        dates: DateFacts,
        provision_no: str | None = None,
    ) -> ApplicabilityDecision:
        """Return the applicable source version(s) for one provision.

        ``provision_no`` is required when resolving an inserted amendment
        provision that has no original ``ProvisionRecord``.
        """

        resolved_no = provision_no or (provision.provision_no if provision else None)
        if not resolved_no:
            raise ValueError("A provision record or provision_no is required")

        considered = tuple(record for record in self._amendments if record.target_provision == resolved_no)
        if not considered:
            if provision is None:
                return ApplicabilityDecision(
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    provision_no=resolved_no,
                    original_provision=None,
                    considered_amendments=(),
                    applicable_amendments=(),
                    periods=(),
                    reason="No original provision or amendment record exists for this provision.",
                )
            return ApplicabilityDecision(
                status=ApplicabilityStatus.APPLIES_ORIGINAL,
                provision_no=resolved_no,
                original_provision=provision,
                considered_amendments=(),
                applicable_amendments=(),
                periods=(self._original_period(dates, "No amendment targets this provision; the original provision applies."),),
                reason="No amendment targets this provision; the original provision applies.",
            )

        reporting_rules = tuple(record for record in considered if any(rule.change_on_or_after for rule in record.applicability))
        if reporting_rules:
            return self._resolve_reporting(provision, resolved_no, dates, considered, reporting_rules)
        return self._resolve_determination(provision, resolved_no, dates, considered)

    def _resolve_reporting(self, provision, provision_no, dates, considered, reporting):
        if dates.change_date is None:
            return self._insufficient(provision, provision_no, considered, "change_date", "Amendment paragraph 5.2 makes reporting applicability depend on the date the change occurred.")
        effective = min(record.effective_on for record in reporting)
        if dates.change_date < effective:
            reason = f"The change occurred on {dates.change_date.isoformat()}, before the amendment effective date {effective.isoformat()}; the original reporting rule applies under Amendment paragraph 5.2."
            return self._decision(ApplicabilityStatus.APPLIES_ORIGINAL, provision, provision_no, considered, (), self._original_period(dates, reason), reason)
        reason = f"The change occurred on {dates.change_date.isoformat()}, on or after the amendment effective date {effective.isoformat()}; the amendment reporting rule applies under Amendment paragraph 5.2."
        return self._decision(ApplicabilityStatus.APPLIES_AMENDMENT, provision, provision_no, considered, reporting, self._amendment_period(dates, reporting, reason), reason)

    def _resolve_determination(self, provision, provision_no, dates, considered):
        if dates.determination_date is None:
            return self._insufficient(provision, provision_no, considered, "determination_date", "Amendment paragraph 5.1 makes applicability depend on the determination date.")
        effective = min(record.effective_on for record in considered)
        if dates.determination_date < effective:
            reason = f"The determination date {dates.determination_date.isoformat()} is before the amendment effective date {effective.isoformat()}; the original provision applies under Amendment paragraph 5.1."
            if provision is None:
                reason = f"The determination date {dates.determination_date.isoformat()} is before the amendment effective date {effective.isoformat()}; the inserted provision has no original version and the amendment is not yet applicable."
                return self._decision(ApplicabilityStatus.NOT_APPLICABLE, provision, provision_no, considered, (), (), reason)
            return self._decision(ApplicabilityStatus.APPLIES_ORIGINAL, provision, provision_no, considered, (), self._original_period(dates, reason), reason)

        span = self._spans_effective_date(dates, effective)
        has_period_rule = any(any(rule.source_paragraph == "5.3" and rule.covered_period_rule for rule in record.applicability) for record in considered)
        if span and has_period_rule and provision is not None:
            before_end = effective - timedelta(days=1)
            after_reason = f"The determination is on or after {effective.isoformat()}, and Amendment paragraph 5.3 requires figures to be applied by day across the spanning period."
            periods = (
                ApplicablePeriod(dates.period_start, before_end, Version.ORIGINAL, (), after_reason),
                ApplicablePeriod(effective, dates.period_end, Version.AMENDMENT, tuple(record.amendment_paragraph for record in considered), after_reason),
            )
            return self._decision(ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS, provision, provision_no, considered, considered, periods, after_reason)

        reason = f"The determination date {dates.determination_date.isoformat()} is on or after the amendment effective date {effective.isoformat()}; Amendment paragraph 5.1 applies the amendment, including to an earlier period."
        if provision is None:
            periods = self._amendment_period(dates, considered, reason)
        else:
            periods = self._amendment_period(dates, considered, reason)
        return self._decision(ApplicabilityStatus.APPLIES_AMENDMENT, provision, provision_no, considered, considered, periods, reason)

    @staticmethod
    def _spans_effective_date(dates: DateFacts, effective: date) -> bool:
        return dates.period_start is not None and dates.period_end is not None and dates.period_start < effective <= dates.period_end

    @staticmethod
    def _original_period(dates: DateFacts, reason: str) -> ApplicablePeriod:
        return ApplicablePeriod(dates.period_start, dates.period_end, Version.ORIGINAL, (), reason)

    @staticmethod
    def _amendment_period(dates: DateFacts, records: tuple[AmendmentRecord, ...], reason: str) -> ApplicablePeriod:
        return ApplicablePeriod(dates.period_start, dates.period_end, Version.AMENDMENT, tuple(record.amendment_paragraph for record in records), reason)

    @staticmethod
    def _insufficient(provision, provision_no, considered, missing, reason):
        return ApplicabilityDecision(ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION, provision_no, provision, considered, (), (), reason, (missing,))

    @staticmethod
    def _decision(status, provision, provision_no, considered, applicable, periods, reason):
        if isinstance(periods, ApplicablePeriod):
            periods = (periods,)
        return ApplicabilityDecision(status, provision_no, provision, considered, applicable, tuple(periods), reason)
