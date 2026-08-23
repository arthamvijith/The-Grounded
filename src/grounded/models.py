"""Data contracts for source policy provisions and amendments.

These models describe source material only. In particular, ingestion does not
produce a merged or "current" policy text.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


OperationType = Literal["substitute", "replace_table", "insert"]


@dataclass(frozen=True)
class ProvisionRecord:
    """One numbered provision from the original policy manual."""

    provision_no: str
    original_text: str
    source_document: str
    source_kind: Literal["original"] = "original"
    source_version: str = "manual-2025-12-31"
    part: int | None = None
    part_heading: str | None = None
    section: str | None = None
    section_heading: str | None = None
    source_start: int | None = None
    source_end: int | None = None
    raw_text: str = ""
    cross_references: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ApplicabilityRule:
    """A preserved textual rule plus the dates it explicitly establishes."""

    source_paragraph: str
    raw_text: str
    determination_on_or_after: date | None = None
    change_on_or_after: date | None = None
    covered_period_rule: str | None = None


@dataclass(frozen=True)
class AmendmentRecord:
    """One independent operation from a numbered amendment."""

    amendment_id: str
    amendment_paragraph: str
    issued_on: date
    effective_on: date
    target_provision: str
    operation: OperationType
    old_text: str | None
    new_text: str
    applicability: tuple[ApplicabilityRule, ...]
    source_document: str
    source_start: int | None = None
    source_end: int | None = None
    insertion_after: str | None = None


@dataclass(frozen=True)
class AmendmentValidation:
    """Result of checking amendment targets against original provisions."""

    amendment_id: str
    record_count: int
    validated_targets: tuple[str, ...]

