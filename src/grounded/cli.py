"""Production-style command-line interface for THE GROUNDED."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from .audit import AuditLogger
from .decision import DecisionStatus
from .evaluation import GroundedEvaluator
from .pipeline import GroundedPipeline
from .public import GroundedPublicInterface, PublicGroundedResponse


EXIT_OK = 0
EXIT_USAGE = 10
EXIT_EVALUATION_FAILED = 11
EXIT_STATUS_CODES = {
    DecisionStatus.NEEDS_CLARIFICATION: 2,
    DecisionStatus.CONFLICTING_AUTHORITY: 3,
    DecisionStatus.BROKEN_CROSS_REFERENCE: 4,
    DecisionStatus.INSUFFICIENT_EVIDENCE: 5,
    DecisionStatus.OUT_OF_SCOPE: 6,
}


def _json_value(value: Any) -> Any:
    """Convert grounded dataclasses to deterministic JSON-compatible values."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    return value


def response_to_dict(response: PublicGroundedResponse) -> dict[str, Any]:
    """Return the public response in the CLI's stable field order."""

    return _json_value(response)


def _print_calculation(calculation: Any) -> None:
    print(f"calculation status: {calculation.status.value}")
    if calculation.calculation is None:
        print(f"calculation reason: {calculation.reason}")
        print(f"calculation missing inputs: {calculation.missing_inputs}")
        return
    calculated = calculation.calculation
    provenance = calculated.provenance
    print(f"calculation gross monthly earnings: {calculated.gross_monthly_earnings}")
    print(f"calculation disregard: {calculated.disregard}")
    print(f"calculation countable monthly earnings: {calculated.countable_monthly_earnings}")
    print(
        "calculation provenance: "
        f"{provenance.provision_id}, version={provenance.version}, "
        f"amendment={provenance.amendment_id} §{provenance.amendment_paragraph}"
    )


def _print_response(response: PublicGroundedResponse, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response_to_dict(response), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return

    print(f"question: {response.question}")
    print(f"status: {response.status.value}")
    print(f"answer permitted: {response.answer_permitted}")
    if response.answer_permitted:
        print("grounded answer:")
        for section in response.sections:
            scope = []
            if section.version:
                scope.append(f"version={section.version}")
            if section.period_start is not None or section.period_end is not None:
                scope.append(f"period={section.period_start}/{section.period_end}")
            suffix = f" ({', '.join(scope)})" if scope else ""
            print(f"  {section.section_id}{suffix}: {section.content}")
            print(f"    citations: {section.citations}")
        if response.calculation is not None:
            _print_calculation(response.calculation)
    else:
        print("grounded answer: [not permitted]")
        print(f"blocking reason: {response.refusal_reason}")
        print(f"missing facts: {response.missing_facts}")
        print(f"conflicts: {response.conflicts}")
        print(f"gaps: {response.gaps}")
        print(f"next action: {response.next_action}")
    print(f"source provisions: {response.source_provisions}")
    print(f"source amendments: {response.source_amendments}")
    print(f"citations: {response.citations}")


def _money(value: Any, negative: bool = False) -> str:
    amount = str(value)
    if amount.endswith(".0"):
        amount = amount[:-2]
    return f"{'-' if negative else ''}${amount}"


def _source_name(source_document: str) -> str:
    source_name = Path(source_document).name.lower()
    if "amendment" in source_name:
        return "Amendment source"
    if "policy-manual" in source_name:
        return "Original Policy Manual"
    return "Supplied policy source"


def _citation_text(citation: Any) -> str:
    if citation.amendment_id is not None:
        paragraph = ""
        if citation.amendment_paragraph is not None:
            paragraph = f" {chr(0xA7)}{citation.amendment_paragraph}"
        return f"{citation.provision_id} — Amendment {citation.amendment_id}{paragraph}"
    return f"{citation.provision_id} — {_source_name(citation.source_document)}"


def _print_calculation(calculation: Any) -> None:
    if calculation.calculation is None:
        print("CALCULATION:")
        print(f"Not available: {calculation.reason}")
        return
    calculated = calculation.calculation
    provenance = calculated.provenance
    print("CALCULATION:")
    print(f"Gross monthly earnings:  {_money(calculated.gross_monthly_earnings)}")
    print(f"Earnings disregard:    {_money(calculated.disregard, negative=True)}")
    print(f"Countable earnings:     {_money(calculated.countable_monthly_earnings)}")
    print("Calculation source:")
    if provenance.amendment_id is not None:
        print(
            f"{provenance.provision_id} — Amendment {provenance.amendment_id}"
            f" {chr(0xA7)}{provenance.amendment_paragraph}"
        )
    else:
        print(f"{provenance.provision_id} — {_source_name(provenance.source_document)}")


def _blocking_reason(response: PublicGroundedResponse) -> str:
    reasons = {
        DecisionStatus.NEEDS_CLARIFICATION: "Required information is missing.",
        DecisionStatus.CONFLICTING_AUTHORITY: "Applicable policy provisions conflict.",
        DecisionStatus.BROKEN_CROSS_REFERENCE: "A material policy cross-reference cannot be resolved.",
        DecisionStatus.INSUFFICIENT_EVIDENCE: "No authoritative policy evidence supports the requested conclusion.",
        DecisionStatus.OUT_OF_SCOPE: "The question is outside the supplied policy scope.",
    }
    return reasons.get(response.status, response.refusal_reason or response.status.value)


def _print_conflicts(conflicts: Sequence[Any]) -> None:
    for conflict in conflicts:
        provision_ids = getattr(conflict, "provision_ids", ())
        reason = getattr(conflict, "reason", "")
        print(f"- {' / '.join(provision_ids)}: {reason}")


def _print_gaps(gaps: Sequence[Any]) -> None:
    for gap in gaps:
        code = getattr(gap, "code", "GAP")
        provision_ids = getattr(gap, "provision_ids", ())
        suffix = f" ({', '.join(provision_ids)})" if provision_ids else ""
        print(f"- {code}{suffix}")


def _print_response(response: PublicGroundedResponse, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response_to_dict(response), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return

    print("=" * 50)
    print("THE GROUNDED")
    print("Policy Decision Assistant")
    print("=" * 50)
    print()
    print("Question:")
    print(response.question)
    print()
    print(f"STATUS: {response.status.value}")
    print()
    if response.answer_permitted:
        print("ANSWER:")
        for section in response.sections:
            scope = []
            if section.version:
                scope.append(f"Version: {section.version}")
            if section.period_start is not None or section.period_end is not None:
                scope.append(f"Period: {section.period_start or '—'} to {section.period_end or '—'}")
            if scope:
                print(f"[{'; '.join(scope)}]")
            print(section.content.strip())
            print()
        if response.calculation is not None:
            _print_calculation(response.calculation)
            print()
        print("SOURCE:")
        seen = set()
        for citation in response.citations:
            label = _citation_text(citation)
            if label not in seen:
                print(label)
                seen.add(label)
        print()
        print("GROUNDING:")
        print("Answer supported by authoritative policy evidence.")
    else:
        print("RESULT:")
        print("The system cannot answer this question from the supplied policy evidence.")
        print()
        print("REASON:")
        print(_blocking_reason(response))
        if response.missing_facts:
            print(f"Missing information: {', '.join(response.missing_facts)}")
        if response.conflicts:
            print("Conflicting provisions:")
            _print_conflicts(response.conflicts)
        if response.gaps:
            print("Evidence gaps:")
            _print_gaps(response.gaps)
        print()
        print("NEXT ACTION:")
        if response.next_action:
            print(response.next_action.replace("_", " ").capitalize())
        else:
            print("No answer provided.")
    print("=" * 50)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grounded",
        description="Run THE GROUNDED policy system through its safe public interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="ask one policy question")
    ask.add_argument("question", help="the question to evaluate")
    ask.add_argument("--json", action="store_true", help="print one deterministic JSON response")
    ask.add_argument("--audit", type=Path, help="append the execution to a local JSONL audit file")
    ask.add_argument("--artifacts", type=Path, help="load provisions, amendments, and index from an artifact directory")
    ask.add_argument(
        "--gross-monthly-earnings",
        help="optional gross amount for the supported earnings-disregard calculation",
    )

    evaluate = subparsers.add_parser("evaluate", help="run the deterministic regression suite")
    evaluate.add_argument("--json", action="store_true", help="print the evaluation report as JSON")
    evaluate.add_argument("--audit", type=Path, help="append each evaluation execution to a local JSONL audit file")
    evaluate.add_argument("--artifacts", type=Path, help="load provisions, amendments, and index from an artifact directory")
    return parser


def _run_ask(args: argparse.Namespace) -> int:
    pipeline = GroundedPipeline(artifact_root=args.artifacts) if args.artifacts is not None else None
    if args.audit is None:
        response = GroundedPublicInterface(pipeline).answer_question(
            args.question,
            args.gross_monthly_earnings,
        )
    else:
        logger = AuditLogger(args.audit, pipeline)
        if args.gross_monthly_earnings is None:
            response = logger.record_question(args.question).response
        else:
            response = logger.record_question(args.question, args.gross_monthly_earnings).response
    _print_response(response, args.json)
    return EXIT_OK if response.status is DecisionStatus.ANSWERABLE else EXIT_STATUS_CODES[response.status]


def _run_evaluate(args: argparse.Namespace) -> int:
    pipeline = GroundedPipeline(artifact_root=args.artifacts) if args.artifacts is not None else None
    interface = GroundedPublicInterface(pipeline)
    if args.audit is None:
        report = GroundedEvaluator(interface=interface).run()
    else:
        report = GroundedEvaluator(interface=interface, audit_logger=AuditLogger(args.audit, pipeline)).run()

    if args.json:
        payload = {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "all_passed": report.all_passed,
            "results": report.results,
        }
        print(json.dumps(_json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(f"total cases: {report.total}")
        print(f"passed: {report.passed}")
        print(f"failed: {report.failed}")
        for result in report.results:
            state = "PASS" if result.passed else "FAIL"
            print(
                f"{state} {result.case_id}: "
                f"expected={result.expected_status.value}, "
                f"actual={result.actual_status.value}, "
                f"answer_permitted={result.answer_permitted}, "
                f"next_action={result.next_action}"
            )
            for failure in result.failures:
                print(f"  failure: {failure}")
    return EXIT_OK if report.all_passed else EXIT_EVALUATION_FAILED


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "ask":
            return _run_ask(args)
        if args.command == "evaluate":
            return _run_evaluate(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_USAGE
