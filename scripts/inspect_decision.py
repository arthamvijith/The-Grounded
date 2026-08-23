"""Print deterministic examples of the Step 8 answerability gate."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grounded.amendments import parse_amendment
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


def provision(number):
    return next(item for item in PROVISIONS if item.provision_no == number)


def run(label, question, temporal_numbers=(), gate_spec=None):
    spec = analyze_question(question)
    candidates = RETRIEVER.retrieve(question, top_k=200)
    decisions = tuple(
        TEMPORAL.resolve(provision(number), spec.to_date_facts())
        for number in temporal_numbers
    )
    assessment = EVIDENCE.assess(question, candidates, decisions)
    result = GATE.evaluate(gate_spec or spec, assessment, decisions, candidates)
    print(f"\n=== {label} ===")
    print(f"question: {question}")
    print(f"status: {result.status.value}")
    print(f"answer_permitted: {result.answer_permitted}")
    print(f"reasons: {result.reasons}")
    print(f"missing_facts: {result.missing_facts}")
    print(f"conflicts: {result.conflicts}")
    print(f"gaps: {result.gaps}")
    print(f"relevant_provisions: {result.relevant_provisions}")
    print(f"applicable_amendments: {result.applicable_amendments}")
    print(f"next_action: {result.next_action}")


supported_question = replace(
    analyze_question("What is the household resource limit?"),
    required_facts=(), missing_required_facts=(), ambiguity_flags=(), clarification_may_be_required=False,
)
run("supported policy question", "What is the household resource limit?", gate_spec=supported_question)
run("missing date", "How much earnings can be disregarded?", ("§6.4.1",))
run(
    "reporting-rule conflict",
    "How many days must I report a change occurring on 28 February 2026?",
    ("§4.3.2", "§9.1.4"),
)
run("broken full-time-student cross-reference", "How is a full-time student treated in the needs calculation for a determination on 1 March 2026?")
run("insufficient evidence", "What is a unicorn rule?")
run("out of scope", "Can you give me a weather forecast?")
