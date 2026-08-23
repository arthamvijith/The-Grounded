import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.decision import DecisionGate, DecisionStatus
from grounded.evidence import EvidenceAnalyzer, EvidenceStatus
from grounded.ingest import parse_policy_manual
from grounded.question import analyze_question
from grounded.retrieval import LexicalRetriever, RetrievalResult
from grounded.temporal import DateFacts, TemporalApplicabilityResolver


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
RETRIEVER = LexicalRetriever(PROVISIONS, AMENDMENTS)
ANALYZER = EvidenceAnalyzer(PROVISIONS, AMENDMENTS)
TEMPORAL = TemporalApplicabilityResolver(AMENDMENTS)
GATE = DecisionGate()


def provision(number):
    return next(item for item in PROVISIONS if item.provision_no == number)


def candidates(claim):
    return RETRIEVER.retrieve(claim, top_k=200)


def temporal(number, **kwargs):
    return TEMPORAL.resolve(provision(number), DateFacts(**kwargs))


def assess(claim, decisions=()):
    return ANALYZER.assess(claim, candidates(claim), decisions)


def test_supported_question_is_answerable():
    claim = "What is the household resource limit?"
    question = replace(analyze_question(claim), required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False)
    evidence = assess(claim)
    result = GATE.evaluate(question, evidence)
    assert result.status is DecisionStatus.ANSWERABLE
    assert result.answer_permitted is True
    assert result.next_action == "answer"


def test_missing_determination_date_needs_clarification():
    claim = "How much earnings can be disregarded?"
    result = GATE.evaluate(analyze_question(claim), assess(claim, [temporal("§6.4.1")]))
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert "determination_date" in result.missing_facts


def test_missing_change_date_needs_clarification():
    claim = "How many days must I report a change?"
    decisions = [temporal("§4.3.2")]
    result = GATE.evaluate(analyze_question(claim), assess(claim, decisions), decisions)
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert "change_date" in result.missing_facts


def test_insufficient_evidence_is_not_answerable():
    claim = "How much earnings can be disregarded?"
    result = GATE.evaluate(analyze_question(claim), assess(claim))
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert result.answer_permitted is False


def test_reporting_conflict_blocks_answer():
    claim = "How many days must I report a change occurring on 28 February 2026?"
    decisions = [temporal("§4.3.2", change_date=date(2026, 2, 28)), temporal("§9.1.4", change_date=date(2026, 2, 28))]
    evidence = assess(claim, decisions)
    result = GATE.evaluate(analyze_question(claim), evidence, decisions)
    assert result.status is DecisionStatus.CONFLICTING_AUTHORITY
    assert result.answer_permitted is False
    assert result.conflicts
    assert result.conflicts[0].claims_or_values == (
        "§4.3.2: 10 calendar days",
        "§9.1.4: 30 calendar days",
    )


def test_broken_student_cross_reference_blocks_answer():
    claim = "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?"
    result = GATE.evaluate(analyze_question(claim), assess(claim))
    assert result.status is DecisionStatus.BROKEN_CROSS_REFERENCE
    assert result.answer_permitted is False
    assert result.gaps == () or result.evidence_status is EvidenceStatus.BROKEN_CROSS_REFERENCE


def test_explicitly_out_of_scope_question():
    claim = "Can you give me a weather forecast?"
    result = GATE.evaluate(analyze_question(claim), assess(claim))
    assert result.status is DecisionStatus.OUT_OF_SCOPE
    assert result.next_action == "explain_out_of_scope"


def test_multiple_subquestions_all_supported():
    claim = "What is the household resource limit for a determination on 1 March 2026; what is the earnings disregard for a determination on 1 March 2026?"
    question = analyze_question(claim)
    first = assess("What is the household resource limit?")
    second = assess("What is the earnings disregard?", [temporal("§6.4.1", determination_date=date(2026, 2, 28))])
    # Combine the structured evidence without changing either prior layer.
    evidence = replace(first, claim=claim, items=first.items + second.items, status=EvidenceStatus.SUPPORTED)
    result = GATE.evaluate(question, evidence)
    assert result.status is DecisionStatus.ANSWERABLE


def test_multiple_subquestions_one_unsupported_blocks_whole_question():
    claim = "What is the household resource limit; what is the policy for an unfamiliar topic?"
    question = replace(analyze_question(claim), required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False)
    evidence = assess("What is the household resource limit?")
    result = GATE.evaluate(question, replace(evidence, claim=claim))
    assert result.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert "what is the policy for an unfamiliar topic?" in result.unanswered_sub_questions


def test_priority_is_deterministic_for_multiple_blockers():
    claim = "How much earnings can be disregarded?"
    decisions = [temporal("§6.4.1")]
    result = GATE.evaluate(analyze_question(claim), assess(claim, decisions), decisions)
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert result.next_action == "request_missing_facts"


def test_multiple_periods_can_remain_answerable():
    claim = "What $175 earnings disregard applies for a period spanning 1 March 2026?"
    decisions = [temporal("§6.4.1", determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10))]
    question = replace(
        analyze_question(claim),
        required_facts=(),
        determination_date=date(2026, 4, 1),
        period_start=date(2026, 2, 20),
        period_end=date(2026, 3, 10),
        missing_required_facts=(),
        ambiguity_flags=(),
        clarification_may_be_required=False,
    )
    result = GATE.evaluate(question, assess(claim, decisions), decisions)
    assert result.status is DecisionStatus.ANSWERABLE


def test_retrieval_score_alone_cannot_pass_gate():
    claim = "What is the household resource limit?"
    evidence = assess(claim)
    evidence = replace(evidence, status=EvidenceStatus.MISSING_AUTHORITY, reason="Only a ranked candidate was supplied.")
    result = GATE.evaluate(replace(analyze_question(claim), required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False), evidence)
    assert result.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert result.answer_permitted is False


def test_missing_authority_is_not_converted_to_answer():
    claim = "What is a unicorn rule?"
    result = GATE.evaluate(analyze_question(claim), assess(claim))
    assert result.status is DecisionStatus.INSUFFICIENT_EVIDENCE
    assert result.next_action == "explain_insufficient_evidence"


def test_no_missing_date_is_inferred():
    claim = "How much earnings can be disregarded?"
    result = GATE.evaluate(analyze_question(claim), assess(claim, [temporal("§6.4.1")]))
    assert result.status is DecisionStatus.NEEDS_CLARIFICATION
    assert result.missing_facts == ("determination_date",)


def test_result_contains_structured_reasons_and_action():
    claim = "What is the household resource limit?"
    result = GATE.evaluate(replace(analyze_question(claim), required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False), assess(claim))
    assert isinstance(result.reasons, tuple)
    assert result.reasons
    assert isinstance(result.relevant_provisions, tuple)
    assert result.next_action == "answer"
