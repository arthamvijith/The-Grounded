# Architectural and Implementation Decisions

This document records decisions reflected in the implementation through Step
23. It describes the rationale and trade-offs of the current design; it does
not claim that planned features are already implemented.

## Decision: Use deterministic, offline processing

### Context

The supplied policy corpus is small, structured, date-sensitive, and required
to remain auditable. The system must not fill policy gaps with general
knowledge or depend on an external service at runtime.

### Decision

Use Python standard-library processing, deterministic lexical retrieval,
explicit temporal rules, typed intermediate results, and local JSON/JSONL
artifacts. The runtime does not call an LLM, network service, database, or
vector store.

### Consequences

The behavior is reproducible and explainable, and the project is simple to run
offline. Lexical retrieval is less flexible than semantic retrieval, so the
system may miss paraphrases and must prefer a safe refusal over an unsupported
match.

## Decision: Keep original policy and amendments separate

### Context

The original manual and Amendment No. 2026-01 have different provenance and
different applicability rules. Rewriting them into one manual would lose
historical meaning and make auditing difficult.

### Decision

Store original provisions as `ProvisionRecord` objects and amendment operations
as separate `AmendmentRecord` objects. Applicability is resolved for a query;
source documents are never rewritten or merged on disk.

### Consequences

Historical and amended evidence can be distinguished and cited. Consumers must
carry both stores and use the temporal resolver rather than assuming that the
latest amendment applies globally.

## Decision: Separate retrieval from the decision gate

### Context

A provision can be lexically relevant without being authoritative for the
question. Multiple relevant provisions may also conflict.

### Decision

`LexicalRetriever` returns ranked evidence candidates only. Evidence analysis
and `DecisionGate` independently determine relevance, authority, sufficiency,
conflict, and answerability.

### Consequences

Retrieval remains inspectable and cannot silently turn a high score into an
answer. The pipeline has more explicit stages, but each safety decision is
testable in isolation.

## Decision: Resolve temporal applicability before answering

### Context

Amendment No. 2026-01 distinguishes determination dates, change dates, and
periods spanning 1 March 2026. A claim date alone is not always sufficient.

### Decision

`TemporalApplicabilityResolver` runs after retrieval and before evidence and
answerability decisions. It returns structured original, amendment,
multiple-period, not-applicable, or insufficient-date outcomes.

### Consequences

The system can preserve historical rules and period-by-period applicability.
Missing dates block a safe conclusion instead of causing the system to assume
the latest rule.

## Decision: Refuse when evidence is insufficient

### Context

The policy corpus contains unsupported questions, an original reporting-rule
conflict, and a materially broken full-time-student cross-reference.

### Decision

Evidence that is merely related context, lacks required applicability facts, or
does not directly establish the requested rule is not sufficient authority.
The structured result is blocked with an appropriate status and next action.

### Consequences

The system may decline questions that a general chatbot might answer. This
preserves the central grounding guarantee and makes missing information
visible to a later user-facing layer.

## Decision: Preserve unresolved conflicting authority

### Context

The original manual contains the reporting mismatch between `§4.3.2` and
`§9.1.4`.

### Decision

Conflict detection records both provisions and their incompatible claims. The
decision layer returns `CONFLICTING_AUTHORITY` and does not choose a provision
based on rank, recency, or guesswork.

### Consequences

The result is safe and auditable, but it cannot provide a single deadline until
the applicable rule is established by the available policy evidence and dates.

## Decision: Treat broken cross-references as authority failures

### Context

The full-time-student path points through a reference that does not establish
the requested student rule.

### Decision

Cross-reference targets are extracted and checked. A missing target or a
target that does not establish the requested rule is represented structurally
and can produce `BROKEN_CROSS_REFERENCE`.

### Consequences

The system does not invent missing policy content from surrounding text. Some
definitions remain useful as context, but they cannot independently support a
conclusion.

## Decision: Preserve exact provenance and citations

### Context

Every substantive grounded result must be traceable to a provision or
amendment operation, including the source document and amendment paragraph
when applicable.

### Decision

Provision text, amendment text, source locations, provision identifiers,
amendment identifiers, and citation metadata remain in typed records and
structured responses. Answer sections are built from source excerpts and carry
citations.

### Consequences

Results can be inspected and audited at clause level. Source paths in
reproducible artifacts are canonical relative paths, while the original source
documents remain unchanged.

## Decision: Use append-only deterministic audit logging

### Context

Question executions need to be reproducible and explainable without requiring a
database or external service.

### Decision

`AuditLogger` writes one canonical UTF-8 JSON object per line. Records include
the question, intermediate outputs, decision, answer metadata, evidence,
citations, provisions, amendments, conflicts, and gaps. The execution ID is a
deterministic hash of the record content; timestamps and random identifiers are
not added.

### Consequences

Audit history is local, simple, and append-only. Log files can grow over time
and require normal operational retention management, which is outside the
current policy runtime.

## Decision: Use deterministic regression evaluation

### Context

The system must detect regressions in both answerable and refusal behavior.
Checking only for an answer string would not verify the safety boundary.

### Decision

The evaluation framework runs predefined questions through the public
interface and compares expected and actual status, answer permission, next
action, and selected provenance. A non-answerable response that permits an
answer is an explicit evaluation failure.

### Consequences

The evaluation output is stable and suitable for local regression checks. The
current built-in suite contains ten representative cases, including positive,
negative, historical, amended, multi-clause, and calculation cases.

## Decision: Add dedicated source stores and reproducible artifacts

### Context

The runtime originally rebuilt in-memory records and lexical indexes from
source files. Architecture requirements also call for an offline/build-time
workflow and reproducible source-derived artifacts.

### Decision

Step 15 introduced `ProvisionStore` and `AmendmentStore`, canonical JSON files
for provisions and amendments, a manifest, and a serialized lexical search
index. The pipeline and CLI can load these artifacts through `--artifacts`.

### Consequences

Builds can be inspected, repeated, and loaded without reparsing source files
for every runtime initialization. The artifacts are derived data, not policy
authority, and the default source-loading path remains available for backward
compatibility.

## Decision: Validate amendment `old_text` before acceptance

### Context

An amendment operation that targets the right provision but expects different
old text could silently apply to the wrong policy content.

### Decision

Amendment validation checks target existence and verifies every supplied
`old_text` against the targeted original or prior validated text. A mismatch
raises `ValueError`; artifact loading performs the same validation before
returning stores.

### Consequences

Invalid amendments fail closed and cannot silently alter policy behavior. The
validation is intentionally textual and deterministic; it does not create a
merged policy document or implement a future resolved-provision model.

## Decision: Keep the public interface and CLI structured

### Context

Callers need a stable interface without bypassing the decision gate, and the
project must be usable without importing internal modules.

### Decision

`GroundedPublicInterface` exposes structured responses. The CLI delegates to
that interface, supports human-readable and deterministic JSON output, and
uses distinct exit codes for blocked outcomes. Optional audit and artifact
paths are passed to existing components.

### Consequences

The interface is usable from scripts and PowerShell while preserving the same
pipeline decisions. Final conversational refusal wording and a web interface
are not part of the current implementation.

## Decision: Use deterministic Decimal arithmetic for the supported calculation

### Context

The corpus directly supports a monthly employment-earnings disregard, but it
does not support a general financial or award calculator.

### Decision

Step 20 uses Python `Decimal` arithmetic only after the existing pipeline,
decision gate, validation, temporal resolution, and `ResolvedProvision` have
established the applicable disregard. Missing or unsupported inputs fail
safely.

### Consequences

The demonstrated calculation is reproducible and preserves policy provenance.
Award, apportionment, and unrelated calculations remain outside the scope.

## Decision: Present structured answers and refusals

### Context

Demonstrations and callers need readable results without adding unconstrained
conversational generation.

### Decision

The public interface and CLI expose exact grounded sections, citations,
provenance, calculation details, blocking status, structured reasons, and next
actions. They never turn a blocked decision into an answer.

### Consequences

Results are easier to inspect while the decision gate and final validation
remain authoritative. Conversational refusal prose is still not generated.

## Decision: Make audit records reconstructive and append-only

### Context

An execution should be explainable across every existing pipeline stage,
including a blocked result and any supported calculation.

### Decision

Step 23 extends the existing JSONL record with retrieval metadata, resolved
provisions, answer and validation results, and calculation provenance. The
canonical serializer handles enums, dates, dataclasses, and `Decimal` values;
execution IDs remain deterministic hashes of record content.

### Consequences

One local record can reconstruct the execution without a database or second
logging mechanism. Records are larger and local retention remains an operator
responsibility.

## Explicitly deferred work

The following architecture ideas are not claimed as implemented by this
record:

- a general calculation engine for award arithmetic and period apportionment;
- unrestricted semantic post-generation claim validation;
- a dedicated citation formatter module;
- conversational refusal prose;
- packaging, web UI, database/service deployment, and runtime LLM integration;
- Step 25 final hardening and clean-clone verification.

`DECISIONS.md` and `AI-USAGE.md` are documentation artifacts and do not add
runtime behavior.
