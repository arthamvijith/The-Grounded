import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.answer import GroundedAnswerGenerator
from grounded.decision import DecisionGate, DecisionStatus
from grounded.evidence import EvidenceAnalyzer, EvidenceStatus
from grounded.ingest import parse_policy_manual
from grounded.question import analyze_question
from grounded.retrieval import LexicalRetriever
from grounded.temporal import DateFacts, TemporalApplicabilityResolver


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
RETRIEVER = LexicalRetriever(PROVISIONS, AMENDMENTS)
EVIDENCE = EvidenceAnalyzer(PROVISIONS, AMENDMENTS)
TEMPORAL = TemporalApplicabilityResolver(AMENDMENTS)
GATE = DecisionGate()
GENERATOR = GroundedAnswerGenerator(PROVISIONS, AMENDMENTS)


def provision(number):
    return next(item for item in PROVISIONS if item.provision_no == number)


def candidates(claim):
    return RETRIEVER.retrieve(claim, top_k=200)


def temporal(number, **kwargs):
    return TEMPORAL.resolve(provision(number), DateFacts(**kwargs))


def make(claim, decisions=(), gate_question=None, retrieval_claim=None):
    question = analyze_question(claim)
    evidence_claim = retrieval_claim or claim
    evidence = EVIDENCE.assess(evidence_claim, candidates(evidence_claim), decisions)
    gate_result = GATE.evaluate(gate_question or question, evidence, decisions)
    return GENERATOR.generate(gate_question or question, gate_result, evidence, decisions)


def answerable_question(claim):
    question = analyze_question(claim)
    return replace(question, required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False)


def test_answerable_question_produces_grounded_output():
    claim = "What is the household resource limit?"
    result = make(claim, gate_question=answerable_question(claim))
    assert result.status is DecisionStatus.ANSWERABLE
    assert result.answer_permitted
    assert result.sections
    assert all(section.content for section in result.sections)


def test_every_substantive_section_has_citations():
    claim = "What is the household resource limit?"
    result = make(claim, gate_question=answerable_question(claim))
    assert all(section.citations for section in result.sections)


def test_original_provision_answer_cites_original_provision():
    claim = "What is the household resource limit?"
    result = make(claim, gate_question=answerable_question(claim))
    assert any(citation.provision_id == "§2.4.1" and citation.amendment_id is None for citation in result.citations)


def test_amended_provision_answer_cites_amendment():
    claim = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    decision = temporal("§6.4.1", determination_date=date(2026, 4, 1))
    result = make(claim, [decision], retrieval_claim="What is the $175 earnings disregard?")
    assert result.status is DecisionStatus.ANSWERABLE
    assert any(citation.amendment_id == "2026-01" and citation.amendment_paragraph == "1.1" for citation in result.citations)
    assert "$175" in " ".join(section.content for section in result.sections)


def test_multiple_periods_create_separate_sections():
    claim = "What $175 earnings disregard applies for a period spanning 1 March 2026?"
    decision = temporal("§6.4.1", determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10))
    question = replace(answerable_question(claim), determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10))
    result = make(claim, [decision], question)
    periods = {(section.period_start, section.period_end) for section in result.sections if section.period_start is not None}
    assert result.status is DecisionStatus.ANSWERABLE
    assert len(periods) >= 2


def test_non_answer_statuses_produce_no_substantive_answer():
    cases = (
        ("How much earnings can be disregarded?", [temporal("§6.4.1")], DecisionStatus.NEEDS_CLARIFICATION, None),
        ("How many days must I report a change occurring on 28 February 2026?", [temporal("§4.3.2", change_date=date(2026, 2, 28)), temporal("§9.1.4", change_date=date(2026, 2, 28))], DecisionStatus.CONFLICTING_AUTHORITY, None),
        ("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?", [], DecisionStatus.BROKEN_CROSS_REFERENCE, None),
        ("What is a unicorn rule?", [], DecisionStatus.INSUFFICIENT_EVIDENCE, None),
        ("Can you give me a weather forecast?", [], DecisionStatus.OUT_OF_SCOPE, None),
    )
    for claim, decisions, expected, gate_question in cases:
        result = make(claim, decisions, gate_question)
        assert result.status is expected
        assert result.answer_permitted is False
        assert result.sections == ()


def test_multi_subquestion_answer_has_separate_sections():
    claim = "What is the household resource limit; what is the earnings disregard?"
    question = replace(answerable_question(claim), sub_questions=analyze_question("What is the household resource limit; what is the earnings disregard?").sub_questions)
    first = EVIDENCE.assess("What is the household resource limit?", candidates("What is the household resource limit?"))
    second_decision = temporal("§6.4.1", determination_date=date(2026, 2, 28))
    second = EVIDENCE.assess("What is the earnings disregard?", candidates("What is the earnings disregard?"), [second_decision])
    evidence = replace(first, claim=claim, items=first.items + second.items, status=EvidenceStatus.SUPPORTED)
    decision = GATE.evaluate(question, evidence, [second_decision])
    result = GENERATOR.generate(question, decision, evidence, [second_decision])
    assert result.status is DecisionStatus.ANSWERABLE
    assert {section.sub_question_id for section in result.sections} == {1, 2}


def test_no_missing_date_is_inferred():
    result = make("How much earnings can be disregarded?", [temporal("§6.4.1")])
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert result.missing_facts == ("determination_date",)
    assert result.sections == ()


def test_conflict_is_not_resolved():
    claim = "How many days must I report a change occurring on 28 February 2026?"
    decisions = [temporal("§4.3.2", change_date=date(2026, 2, 28)), temporal("§9.1.4", change_date=date(2026, 2, 28))]
    result = make(claim, decisions)
    assert result.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert result.sections == ()
    assert len(result.conflicts) == 1


def test_broken_reference_is_not_resolved():
    claim = "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?"
    result = make(claim)
    assert result.status is DecisionStatus.BROKEN_CROSS_REFERENCE
    assert result.sections == ()


def test_amendment_provenance_and_inserted_provision_are_preserved():
    claim = "What does §10.5.2 say?"
    decision = temporal("§10.5.2", determination_date=date(2026, 3, 1))
    result = make(claim, [decision])
    assert result.status is DecisionStatus.ANSWERABLE
    assert any(citation.amendment_paragraph == "4.1" for citation in result.citations)


def test_inserted_provision_retains_amendment_provenance():
    claim = "What does §10.5.3A say?"
    decision = TEMPORAL.resolve(None, DateFacts(determination_date=date(2026, 3, 1)), provision_no="§10.5.3A")
    result = make(claim, [decision])
    assert result.status is DecisionStatus.ANSWERABLE
    assert any(citation.provision_id == "§10.5.3A" and citation.amendment_paragraph == "4.2" for citation in result.citations)


def test_retrieval_rank_alone_cannot_generate_answer():
    claim = "What is the household resource limit?"
    evidence = EVIDENCE.assess(claim, candidates(claim))
    evidence = replace(evidence, status=EvidenceStatus.MISSING_AUTHORITY)
    question = answerable_question(claim)
    decision = GATE.evaluate(question, evidence)
    result = GENERATOR.generate(question, decision, evidence)
    assert result.answer_permitted is False
    assert result.sections == ()


def test_original_text_is_used_without_modification():
    original = provision("§6.4.1")
    before = original.original_text
    claim = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    result = make(claim, [temporal("§6.4.1", determination_date=date(2026, 4, 1))], retrieval_claim="What is the $175 earnings disregard?")
    assert result.status is DecisionStatus.ANSWERABLE
    assert original.original_text == before
    assert "$120 per month" in original.original_text
