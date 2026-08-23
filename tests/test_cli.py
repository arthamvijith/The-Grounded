import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.cli import EXIT_EVALUATION_FAILED, main
from grounded.decision import DecisionStatus


def run_cli(*args, capsys):
    code = main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_answerable_question_has_structured_output(capsys):
    code, output, error = run_cli("ask", "What is the household resource limit?", capsys=capsys)
    assert code == 0
    assert error == ""
    assert "THE GROUNDED" in output
    assert "STATUS: ANSWERABLE" in output
    assert "ANSWER:" in output
    assert "SOURCE:" in output
    assert "GROUNDING:" in output
    assert "Citation(" not in output
    assert "section-1" not in output
    assert "source_document=" not in output
    assert "C:\\Users\\" not in output


def test_non_answerable_statuses_have_distinct_exit_codes(capsys):
    cases = (
        ("How much earnings can be disregarded?", "NEEDS_CLARIFICATION", 2),
        ("How many days must I report a change occurring on 28 February 2026?", "CONFLICTING_AUTHORITY", 3),
        ("How is a full-time student treated in the needs calculation for a determination on 1 March 2026?", "BROKEN_CROSS_REFERENCE", 4),
        ("What is a unicorn rule?", "INSUFFICIENT_EVIDENCE", 5),
    )
    for question, status, exit_code in cases:
        code, output, _ = run_cli("ask", question, capsys=capsys)
        assert code == exit_code
        assert f"STATUS: {status}" in output
        assert "RESULT:" in output
        assert "NEXT ACTION:" in output
        assert "Citation(" not in output


def test_amended_question_preserves_provenance(capsys):
    code, output, _ = run_cli(
        "ask",
        "What is the $175 earnings disregard for a determination on 1 April 2026?",
        capsys=capsys,
    )
    assert code == 0
    assert "STATUS: ANSWERABLE" in output
    assert "§6.4.1 — Amendment 2026-01 §1.1" in output
    assert "Citation(" not in output


def test_human_calculation_output_is_concise_and_grounded(capsys):
    code, output, _ = run_cli(
        "ask",
        "What is the $175 earnings disregard for a determination on 1 April 2026?",
        "--gross-monthly-earnings",
        "500",
        capsys=capsys,
    )
    assert code == 0
    assert "CALCULATION:" in output
    assert "Gross monthly earnings:  $500" in output
    assert "Earnings disregard:    -$175" in output
    assert "Countable earnings:     $325" in output
    assert "§6.4.1 — Amendment 2026-01 §1.1" in output
    assert "C:\\Users\\" not in output


def test_json_output_is_serializable_and_structured(capsys):
    code, output, error = run_cli("ask", "What is a unicorn rule?", "--json", capsys=capsys)
    assert code == 5
    assert error == ""
    payload = json.loads(output)
    assert payload["status"] == "INSUFFICIENT_EVIDENCE"
    assert payload["answer_permitted"] is False
    assert payload["sections"] == []
    assert payload["next_action"] == "explain_insufficient_evidence"


def test_json_output_remains_machine_readable_after_human_formatting(capsys):
    code, output, error = run_cli("ask", "What is the household resource limit?", "--json", capsys=capsys)
    assert code == 0
    assert error == ""
    payload = json.loads(output)
    assert payload["status"] == "ANSWERABLE"
    assert payload["answer_permitted"] is True
    assert payload["sections"]
    assert payload["citations"]
    assert payload["citations"][0]["source_document"]


def test_evaluation_command_passes(capsys):
    code, output, error = run_cli("evaluate", capsys=capsys)
    assert code == 0
    assert error == ""
    assert "total cases: 10" in output
    assert "passed: 10" in output
    assert "failed: 0" in output


def test_evaluation_json_contains_case_results(capsys):
    code, output, _ = run_cli("evaluate", "--json", capsys=capsys)
    payload = json.loads(output)
    assert code == 0
    assert payload["all_passed"] is True
    assert payload["results"][0]["case_id"] == "supported-household-resource-limit"
    assert payload["results"][0]["actual_status"] == "ANSWERABLE"


def test_evaluation_failure_has_nonzero_exit_code(capsys):
    with patch("grounded.cli.GroundedEvaluator") as evaluator_class:
        evaluator_class.return_value.run.return_value = type(
            "Report", (), {"total": 1, "passed": 0, "failed": 1, "all_passed": False, "results": ()}
        )()
        code, output, _ = run_cli("evaluate", capsys=capsys)
    assert code == EXIT_EVALUATION_FAILED
    assert "failed: 1" in output


def test_audit_option_reuses_audit_logger(capsys):
    with patch("grounded.cli.AuditLogger") as logger_class:
        logger_class.return_value.record_question.return_value.response = type(
            "Response", (), {"status": DecisionStatus.INSUFFICIENT_EVIDENCE, "answer_permitted": False}
        )()
        with patch("grounded.cli._print_response") as print_response:
            run_cli("ask", "What is a unicorn rule?", "--audit", "audit.jsonl", capsys=capsys)
    logger_class.assert_called_once()
    logger_class.return_value.record_question.assert_called_once_with("What is a unicorn rule?")
    print_response.assert_called_once()
