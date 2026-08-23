import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.evidence import EvidenceAnalyzer, EvidenceStatus
from grounded.ingest import parse_policy_manual
from grounded.retrieval import LexicalRetriever, RetrievalResult
from grounded.temporal import DateFacts, TemporalApplicabilityResolver

ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
RETRIEVER = LexicalRetriever(PROVISIONS, AMENDMENTS)
TEMPORAL = TemporalApplicabilityResolver(AMENDMENTS)
ANALYZER = EvidenceAnalyzer(PROVISIONS, AMENDMENTS)


def provision(number):
    suffix = ".".join(number.split(".")[-3:])
    return next(item for item in PROVISIONS if item.provision_no.endswith(suffix))


def decision(number, **kwargs):
    return TEMPORAL.resolve(provision(number), DateFacts(**kwargs))


def candidates(claim):
    return RETRIEVER.retrieve(claim, top_k=200)


def test_clearly_supported_claim():
    claim = "What is the household resource limit?"
    assessment = ANALYZER.assess(claim, candidates(claim))
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert any(item.applicable and item.provision_id.endswith("2.4.1") for item in assessment.items)


def test_clearly_unsupported_claim():
    claim = "municipal dog licensing quantum spacecraft"
    assessment = ANALYZER.assess(claim, candidates(claim), [decision("§6.4.1")])
    assert assessment.status is EvidenceStatus.MISSING_AUTHORITY
    assert assessment.items == ()


def test_missing_determination_date_is_insufficient():
    claim = "How much earnings can be disregarded?"
    assessment = ANALYZER.assess(claim, candidates(claim), [decision("§6.4.1")])
    assert assessment.status is EvidenceStatus.INSUFFICIENT
    assert any(gap.code == "MISSING_DATE" for gap in assessment.gaps)


def test_known_reporting_provisions_conflict_when_both_original_versions_apply():
    claim = "How many days must I report a change?"
    temporal = [decision("§4.3.2", change_date=date(2026, 2, 28)), decision("§9.1.4", change_date=date(2026, 2, 28))]
    assessment = ANALYZER.assess(claim, candidates(claim), temporal)
    assert assessment.status is EvidenceStatus.CONFLICTING
    assert assessment.conflicts[0].provision_ids == ("§4.3.2", "§9.1.4")
    values = " ".join(assessment.conflicts[0].claims_or_values)
    assert "10 calendar days" in values and "30 calendar days" in values


def test_applicable_amendment_is_authoritative_instead_of_original():
    claim = "What is the $175 earnings disregard?"
    assessment = ANALYZER.assess(claim, candidates(claim), [decision("§6.4.1", determination_date=date(2026, 4, 1))])
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert any(item.version.value == "amendment" and item.applicable for item in assessment.items)
    assert any(item.version.value == "original" and not item.applicable for item in assessment.items)


def test_original_remains_authoritative_before_amendment():
    claim = "What is the $175 earnings disregard?"
    assessment = ANALYZER.assess(claim, candidates(claim), [decision("§6.4.1", determination_date=date(2026, 2, 28))])
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert any(item.version.value == "original" and item.applicable for item in assessment.items)
    assert any(item.version.value == "amendment" and not item.applicable for item in assessment.items)


def test_broken_cross_reference_known_student_gap():
    claim = "How is a full-time student treated in the needs calculation?"
    assessment = ANALYZER.assess(claim, candidates(claim))
    assert assessment.status is EvidenceStatus.BROKEN_CROSS_REFERENCE
    assert any(issue.source_provision == "§7.1.3" and issue.target_provision == "§5.4" for issue in assessment.cross_reference_issues)


def test_missing_referenced_provision_is_reported():
    altered = replace(provision("§1.1.1"), cross_references=("§99.9.9",))
    analyzer = EvidenceAnalyzer(PROVISIONS + [altered], AMENDMENTS)
    candidate = RetrievalResult(altered, 1.0, ("household",), ("term_overlap:1",), 1, altered.cross_references)
    assessment = analyzer.assess("Household Support Program", [candidate])
    assert assessment.status is EvidenceStatus.BROKEN_CROSS_REFERENCE
    assert assessment.cross_reference_issues[0].target_provision == "§99.9.9"


def test_amendment_without_temporal_decision_is_a_gap():
    claim = "What is the $175 earnings disregard?"
    assessment = ANALYZER.assess(claim, candidates(claim))
    assert assessment.status is EvidenceStatus.INSUFFICIENT
    assert any(gap.code == "UNRESOLVED_APPLICABILITY" for gap in assessment.gaps)


def test_unaffected_provision_is_supported_without_temporal_decision():
    claim = "What is the household resource limit?"
    assessment = ANALYZER.assess(claim, candidates(claim))
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert any(item.provision_id.endswith("2.4.1") and item.applicable for item in assessment.items)


def test_spanning_period_keeps_both_applicable_versions():
    claim = "What $175 earnings disregard applies for a period spanning 1 March 2026?"
    temporal = [decision("§6.4.1", determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10))]
    assessment = ANALYZER.assess(claim, candidates(claim), temporal)
    applicable_versions = {item.version.value for item in assessment.items if item.applicable}
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert applicable_versions == {"original", "amendment"}


def test_original_source_text_is_not_modified():
    original = provision("§6.4.1")
    before = original.original_text
    claim = "What is the earnings disregard?"
    assessment = ANALYZER.assess(claim, candidates(claim), [decision("§6.4.1", determination_date=date(2026, 4, 1))])
    assert assessment.status is EvidenceStatus.SUPPORTED
    assert original.original_text == before
    assert "$120 per month" in original.original_text


def test_evidence_does_not_invent_missing_policy_content():
    claim = "What is the full-time student needs figure?"
    assessment = ANALYZER.assess(claim, candidates(claim))
    assert assessment.status is EvidenceStatus.BROKEN_CROSS_REFERENCE
    assert not any("needs figure" in item.reason.lower() for item in assessment.items)
