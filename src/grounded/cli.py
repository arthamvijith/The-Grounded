"""Production-style command-line interface for THE GROUNDED."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields, is_dataclass
from datetime import date, datetime
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


def _print_response(response: PublicGroundedResponse, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response_to_dict(response), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return

    print(f"question: {response.question}")
    print(f"status: {response.status.value}")
    print(f"answer permitted: {response.answer_permitted}")
    print(f"answer sections: {response.sections}")
    print(f"citations: {response.citations}")
    print(f"source provisions: {response.source_provisions}")
    print(f"source amendments: {response.source_amendments}")
    print(f"missing facts: {response.missing_facts}")
    print(f"conflicts: {response.conflicts}")
    print(f"gaps: {response.gaps}")
    print(f"refusal reason: {response.refusal_reason}")
    print(f"next action: {response.next_action}")


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

    evaluate = subparsers.add_parser("evaluate", help="run the deterministic regression suite")
    evaluate.add_argument("--json", action="store_true", help="print the evaluation report as JSON")
    evaluate.add_argument("--audit", type=Path, help="append each evaluation execution to a local JSONL audit file")
    evaluate.add_argument("--artifacts", type=Path, help="load provisions, amendments, and index from an artifact directory")
    return parser


def _run_ask(args: argparse.Namespace) -> int:
    pipeline = GroundedPipeline(artifact_root=args.artifacts) if args.artifacts is not None else None
    if args.audit is None:
        response = GroundedPublicInterface(pipeline).answer_question(args.question)
    else:
        response = AuditLogger(args.audit, pipeline).record_question(args.question).response
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
