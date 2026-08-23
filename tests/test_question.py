from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.question import PolicyIntent, analyze_question


ROOT = Path(__file__).parents[1]


def test_simple_policy_question():
    spec = analyze_question("What is the household resource limit?")
    assert PolicyIntent.ELIGIBILITY in spec.intents
    assert spec.raw_question == "What is the household resource limit?"


def test_explicit_provision_reference():
    section = chr(0xA7)
    for question in (section + "4.3.2", "4.3.2", "What does section 4.3.2 say?"):
        assert analyze_question(question).requested_provision == section + "4.3.2"


def test_determination_date_extraction():
    spec = analyze_question("What is the earnings disregard for a determination on 1 March 2026?")
    assert spec.determination_date == date(2026, 3, 1)
    assert spec.change_date is None


def test_change_date_extraction():
    spec = analyze_question("The change occurred on March 1, 2026. How many days must I report it?")
    assert spec.change_date == date(2026, 3, 1)
    assert spec.determination_date is None


def test_reporting_date_extraction():
    spec = analyze_question("I reported the change on 2026-03-02; what rule applies?")
    assert spec.reporting_date == date(2026, 3, 2)
    assert spec.change_date is None


def test_period_start_and_end_extraction():
    spec = analyze_question("What applies for the period from 20 February 2026 to 10 March 2026?")
    assert spec.period_start == date(2026, 2, 20)
    assert spec.period_end == date(2026, 3, 10)


def test_money_extraction():
    spec = analyze_question("Can I disregard $175 of earnings?")
    assert any(f.kind == "money" and f.value == "$175" for f in spec.facts_present)


def test_multiple_numerical_values_are_preserved():
    spec = analyze_question("Was the limit $4,000 or $1,225 for 2 members?")
    values = [fact.value for fact in spec.facts_present if fact.kind in {"money", "number"}]
    assert "$4,000" in values
    assert "$1,225" in values
    assert "2" in values


def test_multiple_intents():
    spec = analyze_question("What is the earnings disregard and what sanction applies for failure to report?")
    assert PolicyIntent.DISREGARD in spec.intents
    assert PolicyIntent.EARNINGS_INCOME in spec.intents
    assert PolicyIntent.SANCTION in spec.intents
    assert PolicyIntent.REPORTING_OBLIGATION in spec.intents


def test_multiple_subquestions():
    spec = analyze_question("What is the earnings disregard and when must I report a change?")
    assert len(spec.sub_questions) == 2
    assert PolicyIntent.DISREGARD in spec.sub_questions[0].intents
    assert PolicyIntent.REPORTING_OBLIGATION in spec.sub_questions[1].intents


def test_missing_determination_date():
    spec = analyze_question("How much earnings can be disregarded?")
    assert "determination_date" in spec.required_facts
    assert "determination_date" in spec.missing_required_facts


def test_missing_change_date():
    spec = analyze_question("How many days must I report a change?")
    assert "change_date" in spec.required_facts
    assert "change_date" in spec.missing_required_facts


def test_ambiguous_date_role_is_not_guessed():
    spec = analyze_question("What rule applies to 1 March 2026?")
    assert spec.determination_date is None
    assert spec.change_date is None
    assert spec.reporting_date is None
    assert spec.clarification_may_be_required
    assert any("role" in reason.lower() for reason in spec.ambiguity_flags)


def test_explicit_amendment_reference():
    spec = analyze_question("Compare Amendment No. 2026-01 for §6.4.1.")
    assert spec.requested_version == "Amendment No. 2026-01"
    assert spec.requested_provision == chr(0xA7) + "6.4.1"
    assert PolicyIntent.AMENDMENT_COMPARISON in spec.intents


def test_unknown_question_gets_unknown_intent():
    spec = analyze_question("Tell me something unrelated about municipal licensing.")
    assert spec.intents == (PolicyIntent.UNKNOWN,)


def test_no_date_is_inferred():
    spec = analyze_question("What is the earnings disregard?")
    assert spec.determination_date is None
    assert spec.change_date is None
    assert spec.reporting_date is None
    assert spec.period_start is None
    assert spec.period_end is None


def test_today_is_never_injected():
    spec = analyze_question("How much earnings can be disregarded?")
    assert date.today() not in {spec.determination_date, spec.change_date, spec.reporting_date, spec.period_start, spec.period_end}


def test_source_files_are_untouched():
    manual = ROOT / "source/original/policy-manual.md"
    amendment = ROOT / "source/amendment/Amendment No. 2026-01.md"
    before_manual = manual.read_bytes()
    before_amendment = amendment.read_bytes()
    analyze_question("What is the earnings disregard for 1 March 2026?")
    assert manual.read_bytes() == before_manual
    assert amendment.read_bytes() == before_amendment
