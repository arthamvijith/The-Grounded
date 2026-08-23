import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.ingest import parse_policy_manual
from grounded.retrieval import LexicalRetriever, tokenize


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")


def retriever():
    return LexicalRetriever(PROVISIONS, AMENDMENTS)


def ids(results):
    return [result.record.provision_no if hasattr(result.record, "provision_no") else result.record.target_provision for result in results]


def test_direct_provision_lookup():
    results = retriever().retrieve("§4.3.2")
    assert ids(results)[0] == "§4.3.2"
    assert "exact_provision:§4.3.2" in results[0].matched_signals


def test_normal_policy_question_finds_reporting_rule():
    results = retriever().retrieve("How many days must I report a change?")
    assert "§4.3.2" in ids(results)


def test_numeric_query_preserves_numeric_signal():
    results = retriever().retrieve("What is the $4,000 resource limit?")
    target = next(result for result in results if getattr(result.record, "provision_no", "") == "§2.4.1")
    assert "numeric_overlap:1" in target.matched_signals
    assert "$4,000" in target.record.original_text


def test_cross_reference_is_reported_without_resolving_it():
    results = retriever().retrieve("§10.5.1")
    target = next(result for result in results if getattr(result.record, "provision_no", "") == "§10.5.1")
    assert "§4.3.2" in target.cross_references
    assert all(getattr(result.record, "provision_no", "") != "§4.3.2" for result in results[:1])


def test_amendment_query_returns_amendment_evidence():
    results = retriever().retrieve("March 2026 earnings disregard $175")
    assert any(result.record in AMENDMENTS for result in results)
    amendment = next(result for result in results if result.record in AMENDMENTS)
    assert amendment.record.target_provision == "§6.4.1"


def test_multiple_relevant_reporting_provisions_are_returned():
    results = retriever().retrieve("report a change within days and overpayment")
    result_ids = ids(results)
    assert "§4.3.2" in result_ids
    assert "§9.1.4" in result_ids


def test_query_with_no_useful_evidence_returns_no_candidates():
    assert retriever().retrieve("municipal dog licensing quantum spacecraft") == []


def test_retrieval_does_not_apply_amendments():
    results = retriever().retrieve("earnings disregard")
    original = next(result for result in results if getattr(result.record, "provision_no", "") == "§6.4.1")
    assert "$120 per month" in original.record.original_text
    assert not any(getattr(result.record, "provision_no", "") == "§6.4.1" and "$175" in result.record.original_text for result in results)


def test_tokenization_is_case_and_punctuation_insensitive_but_keeps_numbers():
    assert tokenize("Report, CHANGE: $4,000 on 1 March 2026") == ("report", "change", "4,000", "1", "march", "2026")
