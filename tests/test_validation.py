import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.answer import AnswerSection, Citation
from grounded.decision import DecisionStatus
from grounded.pipeline import GroundedPipeline
from grounded.validation import ValidationStatus, fail_closed_answer, validate_answer


PIPELINE = GroundedPipeline()


def test_valid_original_answer_passes():
    result = PIPELINE.run("What is the household resource limit?")
    assert result.validation.status is ValidationStatus.VALID
    assert result.validation.valid
    assert result.answer.answer_permitted


def test_valid_amended_answer_passes_and_keeps_provenance():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert result.validation.valid
    assert any(
        citation.amendment_id == "2026-01" and citation.amendment_paragraph == "1.1"
        for citation in result.answer.citations
    )


def test_amendment_paragraph_mismatch_is_rejected():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    citation = result.answer.sections[0].citations[0]
    tampered = replace(citation, amendment_paragraph="9.9")
    section = replace(result.answer.sections[0], citations=(tampered,))
    answer = replace(result.answer, sections=(section,), citations=(tampered,))
    validation = validate_answer(
        answer, result.decision, result.evidence_assessment,
        result.temporal_decisions, result.resolved_provisions,
    )
    assert validation.status is ValidationStatus.REJECTED
    assert "CITATION_NOT_AUTHORITATIVE" in validation.reasons


def test_amendment_id_mismatch_is_rejected():
    result = PIPELINE.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    citation = result.answer.sections[0].citations[0]
    tampered = replace(citation, amendment_id="2099-01")
    section = replace(result.answer.sections[0], citations=(tampered,))
    answer = replace(result.answer, sections=(section,), citations=(tampered,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED


def test_source_document_mismatch_is_rejected():
    result = PIPELINE.run("What is the household resource limit?")
    citation = result.answer.sections[0].citations[0]
    tampered = replace(citation, source_document="source/other-policy.md")
    section = replace(result.answer.sections[0], citations=(tampered,))
    answer = replace(result.answer, sections=(section,), citations=(tampered,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED


def test_provision_id_mismatch_is_rejected():
    result = PIPELINE.run("What is the household resource limit?")
    citation = result.answer.sections[0].citations[0]
    tampered = replace(citation, provision_id="§99.9.9")
    section = replace(result.answer.sections[0], citations=(tampered,))
    answer = replace(result.answer, sections=(section,), citations=(tampered,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED


def test_altered_answer_text_is_rejected():
    result = PIPELINE.run("What is the household resource limit?")
    section = replace(result.answer.sections[0], content=result.answer.sections[0].content + " altered")
    answer = replace(result.answer, sections=(section,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED
    assert "ANSWER_TEXT_DOES_NOT_MATCH_SOURCE_EVIDENCE" in validation.reasons


def test_missing_citation_is_rejected():
    result = PIPELINE.run("What is the household resource limit?")
    section = replace(result.answer.sections[0], citations=())
    answer = replace(result.answer, sections=(section,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED
    assert "SECTION_MISSING_CITATION" in validation.reasons


def test_context_only_citation_is_rejected():
    result = PIPELINE.run("What is the household resource limit?")
    non_authoritative = next(
        item for item in result.evidence_assessment.items
        if not item.applicable or item.relevance_score <= 0
    )
    citation = Citation(
        non_authoritative.provision_id,
        non_authoritative.amendment_id,
        non_authoritative.amendment_paragraph,
        non_authoritative.source_document,
    )
    section = replace(result.answer.sections[0], citations=(citation,))
    answer = replace(result.answer, sections=(section,), citations=(citation,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED
    assert "CITATION_NOT_AUTHORITATIVE" in validation.reasons


def test_non_answerable_sections_fail_closed():
    result = PIPELINE.run("What is a unicorn rule?")
    fake = AnswerSection("fake", "unsupported", (), version="original")
    answer = replace(result.answer, sections=(fake,))
    validation = validate_answer(answer, result.decision, result.evidence_assessment, result.temporal_decisions, result.resolved_provisions)
    assert validation.status is ValidationStatus.REJECTED
    closed = fail_closed_answer(answer, result.decision, validation)
    assert not closed.answer_permitted
    assert closed.sections == ()


def test_multi_period_period_mismatch_is_rejected():
    from datetime import date
    from dataclasses import replace as dc_replace
    from grounded.amendments import parse_amendment
    from grounded.evidence import EvidenceAnalyzer
    from grounded.ingest import parse_policy_manual
    from grounded.question import analyze_question
    from grounded.retrieval import LexicalRetriever
    from grounded.temporal import DateFacts, TemporalApplicabilityResolver
    from grounded.decision import DecisionGate

    root = Path(__file__).parents[1]
    provisions = parse_policy_manual(root / "source/original/policy-manual.md")
    amendments = parse_amendment(root / "source/amendment/Amendment No. 2026-01.md")
    claim = "What $175 earnings disregard applies for a period spanning 1 March 2026?"
    question = dc_replace(analyze_question(claim), determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10), required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False)
    retriever = LexicalRetriever(provisions, amendments)
    results = retriever.retrieve(claim, top_k=200)
    decision = TemporalApplicabilityResolver(amendments).resolve(next(p for p in provisions if p.provision_no == "§6.4.1"), DateFacts(determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10)))
    evidence = EvidenceAnalyzer(provisions, amendments).assess(claim, results, (decision,))
    gate = DecisionGate().evaluate(question, evidence, (decision,), results)
    from grounded.answer import GroundedAnswerGenerator
    answer = GroundedAnswerGenerator(provisions, amendments).generate(question, gate, evidence, (decision,))
    from grounded.resolved import project_resolved_provisions
    resolved = project_resolved_provisions((decision,), provisions, amendments)
    assert gate.status is DecisionStatus.ANSWERABLE
    section = next(section for section in answer.sections if section.period_start is not None)
    tampered = replace(section, period_end=date(2099, 1, 1))
    answer = replace(answer, sections=(tampered, *tuple(item for item in answer.sections if item is not section)))
    validation = validate_answer(answer, gate, evidence, (decision,), resolved)
    assert validation.status is ValidationStatus.REJECTED
    assert "ANSWER_PERIOD_DOES_NOT_MATCH_RESOLVED_PERIOD" in validation.reasons


def test_artifact_loaded_validation_matches_source_loaded(tmp_path):
    from grounded.build import build_artifacts
    root = Path(__file__).parents[1]
    artifact_root = tmp_path / "artifacts"
    build_artifacts(root, artifact_root)
    question = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    source = PIPELINE.run(question)
    loaded = GroundedPipeline(artifact_root=artifact_root).run(question)
    assert source.validation == loaded.validation
    assert source.answer.status == loaded.answer.status
    assert source.answer.answer_permitted == loaded.answer.answer_permitted
    assert tuple(section.content for section in source.answer.sections) == tuple(
        section.content for section in loaded.answer.sections
    )


def test_all_existing_non_answer_cases_remain_non_answerable():
    cases = (
        ("How much earnings can be disregarded?", DecisionStatus.NEEDS_CLARIFICATION),
        ("How many days must I report a change occurring on 28 February 2026?", DecisionStatus.CONFLICTING_AUTHORITY),
        ("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?", DecisionStatus.BROKEN_CROSS_REFERENCE),
        ("What is a unicorn rule?", DecisionStatus.INSUFFICIENT_EVIDENCE),
    )
    for question, status in cases:
        result = PIPELINE.run(question)
        assert result.answer.status is status
        assert result.answer.answer_permitted is False
        assert result.answer.sections == ()
