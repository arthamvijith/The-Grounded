import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from grounded.amendments import parse_amendment, validate_amendment_targets
from grounded.build import build_artifacts
from grounded.ingest import parse_policy_manual
from grounded.pipeline import GroundedPipeline
from grounded.store import AmendmentStore, ProvisionStore, load_artifacts


ROOT = Path(__file__).parents[1]
PROVISIONS = parse_policy_manual(ROOT / "source/original/policy-manual.md")
AMENDMENTS = parse_amendment(ROOT / "source/amendment/Amendment No. 2026-01.md")


def test_provision_store_lookup_and_deterministic_iteration():
    store = ProvisionStore(PROVISIONS)
    assert store.get("§4.3.2") == next(record for record in PROVISIONS if record.provision_no == "§4.3.2")
    assert tuple(record.provision_no for record in store) == tuple(record.provision_no for record in PROVISIONS)
    assert tuple(store) == tuple(ProvisionStore(reversed(PROVISIONS)))


def test_amendment_store_lookup_and_deterministic_iteration():
    store = AmendmentStore(AMENDMENTS)
    assert store.get("2026-01", "1.1") == next(record for record in AMENDMENTS if record.amendment_paragraph == "1.1")
    assert store.for_target("§4.3.2")[0].amendment_paragraph == "2.1"
    assert tuple(store) == tuple(AmendmentStore(reversed(AMENDMENTS)))


def test_build_writes_expected_artifacts_and_loads_them(tmp_path):
    output = tmp_path / "artifacts"
    bundle = build_artifacts(ROOT, output)
    assert {path.name for path in output.iterdir()} == {
        "manifest.json", "provisions.json", "amendments.json", "search_index.json"
    }
    loaded = load_artifacts(output)
    assert len(loaded.provisions) == len(PROVISIONS)
    assert len(loaded.amendments) == len(AMENDMENTS)
    assert len(loaded.search_index) == len(PROVISIONS) + len(AMENDMENTS)
    assert bundle.manifest == loaded.manifest


def test_build_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_artifacts(ROOT, first)
    build_artifacts(ROOT, second)
    for name in ("manifest.json", "provisions.json", "amendments.json", "search_index.json"):
        first_bytes = (first / name).read_bytes()
        second_bytes = (second / name).read_bytes()
        assert first_bytes == second_bytes
        assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()


def test_loaded_pipeline_matches_existing_runtime_semantics(tmp_path):
    build_artifacts(ROOT, tmp_path / "artifacts")
    current = GroundedPipeline()
    loaded = GroundedPipeline(artifact_root=tmp_path / "artifacts")
    question = "What is the $175 earnings disregard for a determination on 1 April 2026?"
    current_result = current.run(question)
    loaded_result = loaded.run(question)
    assert current_result.decision.status == loaded_result.decision.status
    assert current_result.answer.answer_permitted == loaded_result.answer.answer_permitted
    assert current_result.answer.source_provisions == loaded_result.answer.source_provisions
    assert current_result.answer.source_amendments == loaded_result.answer.source_amendments
    assert tuple(section.content for section in current_result.answer.sections) == tuple(section.content for section in loaded_result.answer.sections)


def test_valid_old_text_is_accepted():
    validate_amendment_targets(AMENDMENTS, PROVISIONS)


def test_invalid_old_text_is_rejected_safely():
    invalid = replace(AMENDMENTS[0], old_text="text not present")
    with pytest.raises(ValueError, match="old_text does not match"):
        validate_amendment_targets([invalid, *AMENDMENTS[1:]], PROVISIONS)


def test_loaded_artifact_rejects_tampered_old_text(tmp_path):
    output = tmp_path / "artifacts"
    build_artifacts(ROOT, output)
    amendments_path = output / "amendments.json"
    records = json.loads(amendments_path.read_text(encoding="utf-8"))
    records[0]["old_text"] = "tampered text"
    amendments_path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="old_text does not match"):
        load_artifacts(output)


def test_unknown_target_validation_remains_enforced():
    invalid = replace(AMENDMENTS[0], target_provision="§99.9.9")
    with pytest.raises(ValueError, match="targets unknown provision"):
        validate_amendment_targets([invalid, *AMENDMENTS[1:]], PROVISIONS)


def test_public_and_cli_compatibility_paths_remain_available(tmp_path):
    build_artifacts(ROOT, tmp_path / "artifacts")
    result = GroundedPipeline(artifact_root=tmp_path / "artifacts").run("What is the household resource limit?")
    assert result.final_answer.answer_permitted is True
