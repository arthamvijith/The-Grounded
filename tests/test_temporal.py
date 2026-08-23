import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.ingest import parse_policy_manual
from grounded.temporal import ApplicabilityStatus, DateFacts, TemporalApplicabilityResolver, Version


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
RESOLVER = TemporalApplicabilityResolver(AMENDMENTS)
EFFECTIVE = date(2026, 3, 1)


def provision(number):
    return next(item for item in PROVISIONS if item.provision_no == number)


def test_pre_amendment_determination_uses_original():
    result = RESOLVER.resolve(provision("§6.4.1"), DateFacts(determination_date=date(2026, 2, 28)))
    assert result.status is ApplicabilityStatus.APPLIES_ORIGINAL
    assert result.applicable_amendments == ()
    assert "before" in result.reason


def test_post_amendment_determination_uses_amendment():
    result = RESOLVER.resolve(provision("§6.4.1"), DateFacts(determination_date=date(2026, 4, 1), period_start=date(2026, 2, 1), period_end=date(2026, 2, 28)))
    assert result.status is ApplicabilityStatus.APPLIES_AMENDMENT
    assert [item.amendment_paragraph for item in result.applicable_amendments] == ["1.1"]
    assert result.periods[0].version is Version.AMENDMENT
    assert "earlier period" in result.reason


def test_reporting_change_before_effective_date_uses_original():
    result = RESOLVER.resolve(provision("§4.3.2"), DateFacts(change_date=date(2026, 2, 28), determination_date=date(2026, 4, 1)))
    assert result.status is ApplicabilityStatus.APPLIES_ORIGINAL
    assert result.applicable_amendments == ()
    assert "5.2" in result.reason


def test_reporting_change_on_effective_date_uses_amendment():
    result = RESOLVER.resolve(provision("§4.3.2"), DateFacts(change_date=EFFECTIVE, determination_date=date(2026, 4, 1)))
    assert result.status is ApplicabilityStatus.APPLIES_AMENDMENT
    assert [item.amendment_paragraph for item in result.applicable_amendments] == ["2.1"]


def test_spanning_period_is_returned_as_multiple_periods():
    result = RESOLVER.resolve(provision("§6.4.1"), DateFacts(determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10)))
    assert result.status is ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS
    assert [(item.start, item.end, item.version) for item in result.periods] == [
        (date(2026, 2, 20), date(2026, 2, 28), Version.ORIGINAL),
        (date(2026, 3, 1), date(2026, 3, 10), Version.AMENDMENT),
    ]


def test_missing_relevant_date_is_explicit():
    result = RESOLVER.resolve(provision("§6.4.1"), DateFacts())
    assert result.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION
    assert result.missing_dates == ("determination_date",)


def test_unaffected_provision_does_not_require_dates():
    result = RESOLVER.resolve(provision("§2.4.1"), DateFacts())
    assert result.status is ApplicabilityStatus.APPLIES_ORIGINAL
    assert result.periods[0].version is Version.ORIGINAL


def test_sanction_percentage_uses_determination_date_rule():
    result = RESOLVER.resolve(provision("§10.5.2"), DateFacts(determination_date=date(2026, 3, 1)))
    assert result.status is ApplicabilityStatus.APPLIES_AMENDMENT
    assert [item.amendment_paragraph for item in result.applicable_amendments] == ["4.1"]


def test_inserted_sanction_rule_is_applicable_without_original_record():
    result = RESOLVER.resolve(None, DateFacts(determination_date=date(2026, 3, 1)), provision_no="§10.5.3A")
    assert result.status is ApplicabilityStatus.APPLIES_AMENDMENT
    assert result.original_provision is None
    assert [item.amendment_paragraph for item in result.applicable_amendments] == ["4.2"]


def test_inserted_sanction_rule_is_not_applicable_before_effective_date():
    result = RESOLVER.resolve(None, DateFacts(determination_date=date(2026, 2, 28)), provision_no="§10.5.3A")
    assert result.status is ApplicabilityStatus.NOT_APPLICABLE
    assert result.periods == ()


def test_original_text_is_never_modified():
    original = provision("§6.4.1")
    text_before = original.original_text
    result = RESOLVER.resolve(original, DateFacts(determination_date=date(2026, 4, 1)))
    assert original.original_text == text_before
    assert result.original_provision is original
    assert "$120 per month" in original.original_text
