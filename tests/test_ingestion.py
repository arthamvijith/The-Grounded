import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment, validate_amendment_targets
from grounded.ingest import parse_policy_manual
from grounded.models import ProvisionRecord


ROOT = Path(__file__).parents[1]
MANUAL = ROOT / "source/original/policy-manual.md"
AMENDMENT = ROOT / "source/amendment/Amendment No. 2026-01.md"


def test_provisions_are_numbered_and_contextualized():
    provisions = parse_policy_manual(MANUAL)
    assert len(provisions) == 137
    assert provisions[0].provision_no == "§1.1.1"
    assert provisions[-1].provision_no == "§12.3.3"
    target = next(p for p in provisions if p.provision_no == "§4.3.2")
    assert target.part == 4
    assert target.section == "4.3"
    assert target.section_heading == "## 4.3 Recipient obligations"


def test_exact_text_and_source_offsets_are_preserved():
    source = MANUAL.read_text(encoding="utf-8")
    target = next(p for p in parse_policy_manual(MANUAL) if p.provision_no == "§4.3.2")
    assert target.raw_text == source[target.source_start:target.source_end]
    assert "within **10 calendar days**" in target.original_text
    assert target.raw_text.startswith("**4.3.2**")


def test_cross_reference_extraction():
    target = next(p for p in parse_policy_manual(MANUAL) if p.provision_no == "§10.5.1")
    assert "§4.3.2" in target.cross_references
    assert "§8.5" in target.cross_references


def test_amendments_parse_with_dates_and_operations():
    records = parse_amendment(AMENDMENT)
    assert len(records) == 6
    assert {r.amendment_paragraph for r in records} == {"1.1", "2.1", "2.2", "3.1", "4.1", "4.2"}
    assert all(r.issued_on.isoformat() == "2026-02-12" for r in records)
    assert all(r.effective_on.isoformat() == "2026-03-01" for r in records)
    earnings = next(r for r in records if r.amendment_paragraph == "1.1")
    assert earnings.target_provision == "§6.4.1"
    assert earnings.old_text == "$120 per month"
    assert earnings.new_text == "$175 per month"
    assert earnings.applicability[0].determination_on_or_after.isoformat() == "2026-03-01"
    assert any(rule.source_paragraph == "5.3" and rule.covered_period_rule for rule in earnings.applicability)


def test_amendment_insertion_is_preserved_separately():
    insertion = next(r for r in parse_amendment(AMENDMENT) if r.amendment_paragraph == "4.2")
    assert insertion.operation == "insert"
    assert insertion.target_provision == "§10.5.3A"
    assert insertion.insertion_after == "§10.5.3"
    assert "increased the award" in insertion.new_text
    assert insertion.old_text is None


def test_amendment_targets_validate_against_original_provisions():
    provisions = parse_policy_manual(MANUAL)
    records = parse_amendment(AMENDMENT)
    validate_amendment_targets(records, provisions)

    bad = records[0].__class__(**{**records[0].__dict__, "target_provision": "§99.9.9"})
    with pytest.raises(ValueError, match="unknown provision"):
        validate_amendment_targets([bad], provisions)


def test_unknown_insertion_target_is_allowed_but_anchor_is_validated():
    records = parse_amendment(AMENDMENT)
    provisions = parse_policy_manual(MANUAL)
    insertion = next(r for r in records if r.operation == "insert")
    assert insertion.target_provision not in {p.provision_no for p in provisions}
    validate_amendment_targets([insertion], provisions)
