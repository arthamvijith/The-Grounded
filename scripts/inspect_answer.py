"""Print deterministic examples of Step 9 grounded answer generation."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.amendments import parse_amendment
from grounded.answer import GroundedAnswerGenerator
from grounded.decision import DecisionGate
from grounded.evidence import EvidenceAnalyzer
from grounded.ingest import parse_policy_manual
from grounded.question import analyze_question
from grounded.retrieval import LexicalRetriever
from grounded.temporal import DateFacts, TemporalApplicabilityResolver


PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
RETRIEVER = LexicalRetriever(PROVISIONS, AMENDMENTS)
EVIDENCE = EvidenceAnalyzer(PROVISIONS, AMENDMENTS)
TEMPORAL = TemporalApplicabilityResolver(AMENDMENTS)
GATE = DecisionGate()
ANSWER = GroundedAnswerGenerator(PROVISIONS, AMENDMENTS)


def provision(number):
    return next(item for item in PROVISIONS if item.provision_no == number)


def run(label, question, temporal_numbers=(), gate_question=None, date_facts=None, evidence_question=None):
    spec = analyze_question(question)
    if gate_question is not None:
        spec_for_gate = gate_question
    else:
        spec_for_gate = spec
    evidence_claim = evidence_question or question
    candidates = RETRIEVER.retrieve(evidence_claim, top_k=200)
    facts = date_facts or spec.to_date_facts()
    decisions = tuple(TEMPORAL.resolve(provision(number), facts) for number in temporal_numbers)
    evidence = EVIDENCE.assess(evidence_claim, candidates, decisions)
    decision = GATE.evaluate(spec_for_gate, evidence, decisions, candidates)
    result = ANSWER.generate(spec_for_gate, decision, evidence, decisions)
    print(f"\n=== {label} ===")
    print(f"question: {question}")
    print(f"answer_status: {result.status.value}")
    print(f"answer_permitted: {result.answer_permitted}")
    print(f"sections: {result.sections}")
    print(f"citations: {result.citations}")
    print(f"source_provisions: {result.source_provisions}")
    print(f"source_amendments: {result.source_amendments}")
    print(f"refusal_reason: {result.refusal_reason}")
    print(f"warnings: {result.warnings}")


supported_gate_question = replace(
    analyze_question("What is the household resource limit?"),
    required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False,
)
run("supported question", "What is the household resource limit?", gate_question=supported_gate_question)
amended_gate_question = replace(
    analyze_question("What is the $175 earnings disregard for a determination on 1 April 2026?"),
    required_facts=("determination_date",), determination_date=date(2026, 4, 1),
    missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False,
)
run("amended provision", "What is the $175 earnings disregard for a determination on 1 April 2026?", ("§6.4.1",), gate_question=amended_gate_question, date_facts=DateFacts(determination_date=date(2026, 4, 1)), evidence_question="What is the $175 earnings disregard?")
multi_gate_question = replace(
    analyze_question("What $175 earnings disregard applies for a period spanning 1 March 2026?"),
    required_facts=(), determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10),
    missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False,
)
run("multiple periods", "What $175 earnings disregard applies for a period spanning 1 March 2026?", ("§6.4.1",), gate_question=multi_gate_question, date_facts=DateFacts(determination_date=date(2026, 4, 1), period_start=date(2026, 2, 20), period_end=date(2026, 3, 10)))
run("missing date", "How much earnings can be disregarded?", ("§6.4.1",))
run("reporting conflict", "How many days must I report a change occurring on 28 February 2026?", ("§4.3.2", "§9.1.4"))
run("broken student reference", "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?")
run("insufficient evidence", "What is a unicorn rule?")
