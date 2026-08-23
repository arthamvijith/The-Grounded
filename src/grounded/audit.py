"""Local deterministic JSONL audit records for grounded executions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .models import AmendmentRecord, ProvisionRecord
from .public import GroundedPublicInterface, PublicGroundedResponse

if TYPE_CHECKING:
    from .pipeline import GroundedPipeline, PipelineResult


def _json_value(value: Any) -> Any:
    """Convert project dataclasses into stable JSON-compatible values."""

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


def _record_identifier(record: ProvisionRecord | AmendmentRecord) -> str:
    if isinstance(record, ProvisionRecord):
        return record.provision_no
    return f"{record.target_provision} ({record.amendment_id} §{record.amendment_paragraph})"


@dataclass(frozen=True)
class AuditRecord:
    """One complete, append-only snapshot of a grounded execution."""

    schema_version: int
    execution_id: str
    question: str
    status: str
    answer_permitted: bool
    next_action: str | None
    refusal_reason: str | None
    missing_facts: tuple[str, ...]
    conflicts: Any
    gaps: Any
    retrieved_provisions: tuple[str, ...]
    source_provisions: tuple[str, ...]
    source_amendments: tuple[str, ...]
    citations: Any
    answer_sections: Any
    question_spec: Any
    temporal_decisions: Any
    evidence_assessment: Any
    decision_result: Any

    @classmethod
    def from_execution(cls, pipeline_result: PipelineResult, response: PublicGroundedResponse) -> "AuditRecord":
        payload = {
            "schema_version": 1,
            "question": pipeline_result.question,
            "status": response.status,
            "answer_permitted": response.answer_permitted,
            "next_action": response.next_action,
            "refusal_reason": response.refusal_reason,
            "missing_facts": response.missing_facts,
            "conflicts": response.conflicts,
            "gaps": response.gaps,
            "retrieved_provisions": tuple(_record_identifier(item.record) for item in pipeline_result.retrieval_results),
            "source_provisions": response.source_provisions,
            "source_amendments": response.source_amendments,
            "citations": response.citations,
            "answer_sections": response.sections,
            "question_spec": pipeline_result.question_spec,
            "temporal_decisions": pipeline_result.temporal_decisions,
            "evidence_assessment": pipeline_result.evidence_assessment,
            "decision_result": pipeline_result.decision,
        }
        canonical = json.dumps(_json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        execution_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(execution_id=execution_id, **payload)

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)


class _SingleResultPipeline:
    """Adapter allowing the public interface to consume one existing result."""

    def __init__(self, result: PipelineResult):
        self.result = result

    def run(self, question: str) -> PipelineResult:
        return self.result


@dataclass(frozen=True)
class AuditedExecution:
    response: PublicGroundedResponse
    record: AuditRecord


class AuditLogger:
    """Append deterministic audit records to a local UTF-8 JSONL file."""

    def __init__(self, path: str | Path, pipeline: GroundedPipeline | None = None):
        self.path = Path(path)
        self.pipeline = pipeline

    def record_question(self, question: str) -> AuditedExecution:
        from .pipeline import GroundedPipeline

        pipeline = self.pipeline or GroundedPipeline()
        pipeline_result = pipeline.run(question)
        response = GroundedPublicInterface(_SingleResultPipeline(pipeline_result)).answer_question(question)
        record = AuditRecord.from_execution(pipeline_result, response)
        self.append(record)
        return AuditedExecution(response=response, record=record)

    def append(self, record: AuditRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")

    def read_records(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        with self.path.open("r", encoding="utf-8") as stream:
            return tuple(json.loads(line) for line in stream if line.strip())


def record_execution(
    question: str,
    path: str | Path,
    pipeline: GroundedPipeline | None = None,
) -> AuditedExecution:
    """Run one question through the existing public interface and audit it."""

    return AuditLogger(path, pipeline).record_question(question)
