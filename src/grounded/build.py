"""Offline deterministic source parsing and artifact building."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .amendments import parse_amendment, validate_amendment_targets
from .ingest import parse_policy_manual
from .retrieval import LexicalRetriever
from .store import AmendmentStore, ArtifactBundle, ProvisionStore, write_artifacts


def build_artifacts(
    source_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> ArtifactBundle:
    """Parse source files, validate them, and write canonical local artifacts."""

    root = Path(source_root) if source_root is not None else Path(__file__).parents[2]
    output = Path(artifact_root) if artifact_root is not None else root / "build" / "artifacts"
    original_path = root / "source" / "original" / "policy-manual.md"
    amendment_path = root / "source" / "amendment" / "Amendment No. 2026-01.md"

    provisions = tuple(
        replace(record, source_document="source/original/policy-manual.md")
        for record in parse_policy_manual(original_path)
    )
    amendments = tuple(
        replace(record, source_document="source/amendment/Amendment No. 2026-01.md")
        for record in parse_amendment(amendment_path)
    )
    validate_amendment_targets(list(amendments), list(provisions))
    provision_store = ProvisionStore(provisions)
    amendment_store = AmendmentStore(amendments)
    retriever = LexicalRetriever(list(provision_store), list(amendment_store))
    return write_artifacts(
        output,
        provision_store,
        amendment_store,
        retriever.export_index(),
        ("source/original/policy-manual.md", "source/amendment/Amendment No. 2026-01.md"),
    )


if __name__ == "__main__":
    build_artifacts()
