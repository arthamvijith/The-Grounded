"""Deterministic source stores and persisted artifact loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator

from .models import AmendmentRecord, ApplicabilityRule, ProvisionRecord


ARTIFACT_SCHEMA_VERSION = 1
PROVISIONS_FILE = "provisions.json"
AMENDMENTS_FILE = "amendments.json"
INDEX_FILE = "search_index.json"
MANIFEST_FILE = "manifest.json"


class ProvisionStore:
    """Immutable, deterministically ordered provision records."""

    def __init__(self, provisions: Iterable[ProvisionRecord] = ()):
        records = tuple(provisions)
        if len({record.provision_no for record in records}) != len(records):
            raise ValueError("ProvisionStore cannot contain duplicate provision IDs")
        self._records = tuple(sorted(records, key=_provision_sort_key))
        self._by_id = {record.provision_no: record for record in self._records}

    def get(self, provision_no: str) -> ProvisionRecord | None:
        return self._by_id.get(provision_no)

    def __getitem__(self, provision_no: str) -> ProvisionRecord:
        return self._by_id[provision_no]

    def __iter__(self) -> Iterator[ProvisionRecord]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    @property
    def records(self) -> tuple[ProvisionRecord, ...]:
        return self._records


class AmendmentStore:
    """Immutable, deterministically ordered amendment records."""

    def __init__(self, amendments: Iterable[AmendmentRecord] = ()):
        records = tuple(amendments)
        keys = [(record.amendment_id, record.amendment_paragraph) for record in records]
        if len(set(keys)) != len(keys):
            raise ValueError("AmendmentStore cannot contain duplicate amendment records")
        self._records = tuple(sorted(records, key=_amendment_sort_key))
        self._by_key = {
            (record.amendment_id, record.amendment_paragraph): record
            for record in self._records
        }

    def get(self, amendment_id: str, amendment_paragraph: str) -> AmendmentRecord | None:
        return self._by_key.get((amendment_id, amendment_paragraph))

    def for_target(self, target_provision: str) -> tuple[AmendmentRecord, ...]:
        return tuple(record for record in self._records if record.target_provision == target_provision)

    def __iter__(self) -> Iterator[AmendmentRecord]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    @property
    def records(self) -> tuple[AmendmentRecord, ...]:
        return self._records


@dataclass(frozen=True)
class ArtifactBundle:
    """Loaded stores plus the serialized lexical index used by retrieval."""

    provisions: ProvisionStore
    amendments: AmendmentStore
    search_index: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]


def write_artifacts(
    artifact_root: str | Path,
    provisions: ProvisionStore,
    amendments: AmendmentStore,
    search_index: Iterable[dict[str, Any]],
    source_documents: tuple[str, ...],
) -> ArtifactBundle:
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    index = tuple(search_index)
    manifest = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "amendment_count": len(amendments),
        "amendments_file": AMENDMENTS_FILE,
        "index_count": len(index),
        "index_file": INDEX_FILE,
        "provision_count": len(provisions),
        "provisions_file": PROVISIONS_FILE,
        "source_documents": list(source_documents),
    }
    _write_json(root / PROVISIONS_FILE, [_provision_to_dict(record) for record in provisions])
    _write_json(root / AMENDMENTS_FILE, [_amendment_to_dict(record) for record in amendments])
    _write_json(root / INDEX_FILE, list(index))
    _write_json(root / MANIFEST_FILE, manifest)
    return ArtifactBundle(provisions, amendments, index, manifest)


def load_artifacts(artifact_root: str | Path) -> ArtifactBundle:
    root = Path(artifact_root)
    manifest = _read_json(root / MANIFEST_FILE)
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("Unsupported artifact schema version")
    provisions = ProvisionStore(
        _provision_from_dict(item) for item in _read_json(root / manifest["provisions_file"])
    )
    amendments = AmendmentStore(
        _amendment_from_dict(item) for item in _read_json(root / manifest["amendments_file"])
    )
    from .amendments import validate_amendment_targets

    validate_amendment_targets(list(amendments), list(provisions))
    search_index = tuple(_read_json(root / manifest["index_file"]))
    if len(provisions) != manifest["provision_count"] or len(amendments) != manifest["amendment_count"]:
        raise ValueError("Artifact manifest counts do not match stored records")
    if len(search_index) != manifest["index_count"]:
        raise ValueError("Artifact manifest index count does not match stored index")
    return ArtifactBundle(provisions, amendments, search_index, manifest)


def _provision_sort_key(record: ProvisionRecord) -> tuple[int, int, str]:
    return (record.source_start is None, record.source_start or 0, record.provision_no)


def _amendment_sort_key(record: AmendmentRecord) -> tuple[int, str, str, str]:
    return (record.source_start is None, record.source_start or 0, record.amendment_id, record.amendment_paragraph)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _provision_to_dict(record: ProvisionRecord) -> dict[str, Any]:
    return {
        "cross_references": list(record.cross_references),
        "original_text": record.original_text,
        "part": record.part,
        "part_heading": record.part_heading,
        "provision_no": record.provision_no,
        "raw_text": record.raw_text,
        "section": record.section,
        "section_heading": record.section_heading,
        "source_document": record.source_document,
        "source_end": record.source_end,
        "source_kind": record.source_kind,
        "source_start": record.source_start,
        "source_version": record.source_version,
    }


def _provision_from_dict(value: dict[str, Any]) -> ProvisionRecord:
    return ProvisionRecord(
        provision_no=value["provision_no"],
        original_text=value["original_text"],
        source_document=value["source_document"],
        source_kind=value["source_kind"],
        source_version=value["source_version"],
        part=value["part"],
        part_heading=value["part_heading"],
        section=value["section"],
        section_heading=value["section_heading"],
        source_start=value["source_start"],
        source_end=value["source_end"],
        raw_text=value["raw_text"],
        cross_references=tuple(value["cross_references"]),
    )


def _rule_to_dict(rule: ApplicabilityRule) -> dict[str, Any]:
    return {
        "change_on_or_after": _date_value(rule.change_on_or_after),
        "covered_period_rule": rule.covered_period_rule,
        "determination_on_or_after": _date_value(rule.determination_on_or_after),
        "raw_text": rule.raw_text,
        "source_paragraph": rule.source_paragraph,
    }


def _rule_from_dict(value: dict[str, Any]) -> ApplicabilityRule:
    return ApplicabilityRule(
        source_paragraph=value["source_paragraph"],
        raw_text=value["raw_text"],
        determination_on_or_after=_date_value(value["determination_on_or_after"]),
        change_on_or_after=_date_value(value["change_on_or_after"]),
        covered_period_rule=value["covered_period_rule"],
    )


def _amendment_to_dict(record: AmendmentRecord) -> dict[str, Any]:
    return {
        "amendment_id": record.amendment_id,
        "amendment_paragraph": record.amendment_paragraph,
        "applicability": [_rule_to_dict(rule) for rule in record.applicability],
        "effective_on": record.effective_on.isoformat(),
        "insertion_after": record.insertion_after,
        "issued_on": record.issued_on.isoformat(),
        "new_text": record.new_text,
        "old_text": record.old_text,
        "operation": record.operation,
        "source_document": record.source_document,
        "source_end": record.source_end,
        "source_start": record.source_start,
        "target_provision": record.target_provision,
    }


def _amendment_from_dict(value: dict[str, Any]) -> AmendmentRecord:
    return AmendmentRecord(
        amendment_id=value["amendment_id"],
        amendment_paragraph=value["amendment_paragraph"],
        issued_on=date.fromisoformat(value["issued_on"]),
        effective_on=date.fromisoformat(value["effective_on"]),
        target_provision=value["target_provision"],
        operation=value["operation"],
        old_text=value["old_text"],
        new_text=value["new_text"],
        applicability=tuple(_rule_from_dict(rule) for rule in value["applicability"]),
        source_document=value["source_document"],
        source_start=value["source_start"],
        source_end=value["source_end"],
        insertion_after=value["insertion_after"],
    )


def _date_value(value: date | str | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else value
