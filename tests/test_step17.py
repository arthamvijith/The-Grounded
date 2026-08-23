import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.build import build_artifacts
from grounded.ingest import parse_policy_manual
from grounded.amendments import parse_amendment
from grounded.pipeline import GroundedPipeline
from grounded.resolved import ResolvedProvision, project_resolved_provisions
from grounded.temporal import (
    ApplicabilityStatus,
    DateFacts,
    TemporalApplicabilityResolver,
    Version,
)


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")
BY_ID = {record.provision_no: record for record in PROVISIONS}
TEMPORAL = TemporalApplicabilityResolver(AMENDMENTS)


def project(provision_id, facts):
    decision = TEMPORAL.resolve(BY_ID.get(provision_id), facts, provision_no=provision_id)
    return decision, project_resolved_provisions((decision,), PROVISIONS, AMENDMENTS)


def test_original_provision_resolution():
    decision, resolved = project("§2.4.1", DateFacts())
    selected = next(item for item in resolved if item.applicable)
    assert decision.status is ApplicabilityStatus.APPLIES_ORIGINAL
    assert isinstance(selected, ResolvedProvision)
    assert selected.version is Version.ORIGINAL
    assert selected.provision_id == "§2.4.1"
    assert "$4,000" in selected.text
    assert selected.amendment_id is None


def test_amendment_resolution_preserves_provenance():
    decision, resolved = project("§6.4.1", DateFacts(determination_date=date(2026, 4, 1)))
    selected = next(item for item in resolved if item.applicable)
    assert decision.status is ApplicabilityStatus.APPLIES_AMENDMENT
    assert selected.version is Version.AMENDMENT
    assert selected.text == "$175 per month"
    assert selected.amendment_id == "2026-01"
    assert selected.amendment_paragraph == "1.1"
    assert selected.provenance.source_document.endswith("Amendment No. 2026-01.md")


def test_missing_determination_date_is_preserved_as_unresolved():
    decision, resolved = project("§6.4.1", DateFacts())
    assert decision.status is ApplicabilityStatus.INSUFFICIENT_DATE_INFORMATION
    assert resolved
    assert all(item.applicable is False for item in resolved)
    assert all(item.temporal_status is decision.status for item in resolved)


def test_multiple_period_transition_produces_separate_versions():
    decision, resolved = project(
        "§6.4.1",
        DateFacts(
            determination_date=date(2026, 3, 2),
            period_start=date(2026, 2, 28),
            period_end=date(2026, 3, 2),
        ),
    )
    applicable = tuple(item for item in resolved if item.applicable)
    assert decision.status is ApplicabilityStatus.APPLIES_MULTIPLE_PERIODS
    assert {item.version for item in applicable} == {Version.ORIGINAL, Version.AMENDMENT}
    assert {(item.period_start, item.period_end, item.version) for item in applicable} == {
        (date(2026, 2, 28), date(2026, 2, 28), Version.ORIGINAL),
        (date(2026, 3, 1), date(2026, 3, 2), Version.AMENDMENT),
    }


def test_inserted_provision_is_non_applicable_before_effective_date():
    decision = TEMPORAL.resolve(
        None,
        DateFacts(determination_date=date(2026, 2, 28)),
        provision_no="§10.5.3A",
    )
    resolved = project_resolved_provisions((decision,), PROVISIONS, AMENDMENTS)
    assert decision.status is ApplicabilityStatus.NOT_APPLICABLE
    assert len(resolved) == 1
    assert resolved[0].applicable is False
    assert resolved[0].version is Version.AMENDMENT
    assert resolved[0].amendment_paragraph == "4.2"


def test_pipeline_exposes_resolved_provisions_without_changing_status():
    pipeline = GroundedPipeline()
    result = pipeline.run("What is the $175 earnings disregard for a determination on 1 April 2026?")
    assert result.decision.status.value == "ANSWERABLE"
    assert result.answer.answer_permitted is True
    assert any(item.applicable and item.amendment_paragraph == "1.1" for item in result.resolved_provisions)


def test_artifact_loaded_pipeline_exposes_same_resolved_provenance(tmp_path):
    artifact_root = tmp_path / "artifacts"
    build_artifacts(ROOT, artifact_root)
    result = GroundedPipeline(artifact_root=artifact_root).run(
        "What is the $175 earnings disregard for a determination on 1 April 2026?"
    )
    selected = next(item for item in result.resolved_provisions if item.applicable)
    assert selected.amendment_id == "2026-01"
    assert selected.amendment_paragraph == "1.1"
    assert result.answer.answer_permitted is True
