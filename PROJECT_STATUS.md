# THE GROUNDED — Project Status

This document is the current continuity record for THE GROUNDED. It describes
the repository as implemented at Step 18 and is intended to be read before
future development work.

## 1. Project Identity

THE GROUNDED is a deterministic, policy-evidence-based policy decision aid and
grounded RAG system. It is not a generic chatbot. Its safety-critical flow is:

```text
retrieval
→ temporal applicability
→ evidence assessment
→ decision gate
→ ResolvedProvision projection
→ answer generation
→ deterministic validation
→ grounded answer or refusal
```

Retrieval supplies candidates; it never authorizes an answer by itself. The
supplied original policy manual and amendment files remain the authoritative
policy inputs. AI-generated content is not policy authority.

## 2. Current Implementation Status

Steps 1–18 are complete. The repository currently provides:

- Separate original-policy and amendment source artifacts.
- Provision-level ingestion with exact source text preservation, headings,
  source offsets, cross-references, and provenance.
- Amendment parsing with issue/effective dates, operations, applicability rules,
  target validation, and `old_text` integrity validation.
- Deterministic `ProvisionStore` and `AmendmentStore` implementations.
- Offline artifact building with persisted provisions, amendments, manifest, and
  lexical search index.
- Artifact loading for runtime use while retaining source-based compatibility.
- Deterministic lexical retrieval with provision, amendment, numeric, date,
  heading, and signal-aware scoring.
- Deterministic question analysis, intent classification, sub-question
  detection, date extraction, and fact-slot extraction.
- Temporal applicability resolution for determination dates, change dates,
  reporting rules, effective dates, and periods spanning 1 March 2026.
- Formal `ResolvedProvision` / `ResolvedProvenance` query-specific projection.
- Evidence sufficiency assessment, known reporting-conflict detection, and
  broken or materially unrelated cross-reference detection.
- A deterministic decision/answerability gate.
- Structured source-excerpt answers and structured non-answer/refusal results.
- Public interface, human-readable CLI output, and deterministic JSON CLI
  output.
- Append-only local JSONL audit logging.
- A deterministic six-case evaluation/regression framework.
- Artifact-aware runtime loading.
- Step 18 deterministic output/citation validation with fail-closed behavior.

## 3. Step-by-Step History

| Step | Status | Main outcome |
|------|--------|--------------|
| 1 | COMPLETE | Source analysis and preservation of the supplied policy corpus as separate authoritative artifacts. |
| 2 | COMPLETE | Provision-level policy ingestion and typed source records. |
| 3 | COMPLETE | Amendment parsing, target validation, and amendment metadata preservation. |
| 4 | COMPLETE | Deterministic lexical retrieval of provisions and amendments. |
| 5 | COMPLETE | Temporal applicability resolution for amendment-effective and transitional dates. |
| 6 | COMPLETE | Evidence sufficiency, conflict detection, gap detection, and cross-reference validation. |
| 7 | COMPLETE | Deterministic question analysis, intent detection, date roles, fact slots, and sub-questions. |
| 8 | COMPLETE | Decision/answerability gate with clarification, insufficiency, conflict, broken-reference, and scope outcomes. |
| 9 | COMPLETE | Grounded structured answer generation from exact source excerpts with citations. |
| 10 | COMPLETE | End-to-end orchestration connecting the existing pipeline layers. |
| 11 | COMPLETE | Public structured interface for safe grounded responses. |
| 12 | COMPLETE | Local append-only deterministic JSONL audit logging. |
| 13 | COMPLETE | Deterministic evaluation/regression framework with six representative cases. |
| 14 | COMPLETE | Production-style CLI with question, evaluation, JSON, audit, and artifact-loading options. |
| 15 | COMPLETE | Deterministic offline stores, artifact build/load workflow, persisted lexical index, and amendment `old_text` integrity validation. |
| 16 | COMPLETE | `DECISIONS.md` and `AI-USAGE.md` governance documentation. |
| 17 | COMPLETE | Formal `ResolvedProvision` / `ResolvedProvenance` projection integrated with temporal resolution without rewriting source policy. |
| 18 | COMPLETE | Deterministic grounded answer validation after generation and before public/CLI exposure. |

## 4. Current Architecture

The implemented components are:

- `ingest.py`: parses the original manual into provision records while
  preserving exact text and source metadata.
- `amendments.py`: parses amendment records and validates targets and supplied
  old text.
- `store.py` and `build.py`: provide deterministic stores and reproducible
  offline artifacts.
- `retrieval.py`: performs deterministic lexical retrieval over stored or
  source-loaded records.
- `question.py`: extracts policy intents, sub-questions, facts, date roles,
  and required slots.
- `temporal.py`: consumes date facts and amendment records to return original,
  amendment, multiple-period, not-applicable, or insufficient-date decisions.
- `evidence.py`: determines whether retrieved candidates are authoritative,
  sufficient, conflicting, or affected by a material gap/reference issue.
- `decision.py`: applies the answerability boundary without selecting a winner
  in a conflict or filling a policy gap.
- `resolved.py`: projects temporal decisions into query-specific
  `ResolvedProvision` records with provenance and applicable periods.
- `answer.py`: generates structured exact source excerpts only after the gate
  permits an answer; non-answer results contain structured refusal metadata,
  not conversational refusal prose.
- `validation.py`: validates answer sections, citations, source excerpts,
  provenance, temporal alignment, and resolved provisions under the current
  exact-source-excerpt contract.
- `pipeline.py`: orchestrates analysis, retrieval, temporal resolution,
  evidence, decision, resolved projection, answer generation, and validation.
- `public.py`: exposes a safe structured public response while preserving the
  decision gate boundary.
- `audit.py`: writes deterministic local JSONL execution records.
- `evaluation.py`: runs and compares the six built-in regression cases.
- `cli.py` and `scripts/grounded.py`: provide the command-line interface.

The architecture document also describes planned or conceptual components that
are not fully implemented as separate modules. In particular, there is no
dedicated `citations.py` formatter, no deterministic calculation engine, no
natural-language refusal prose generator, and no post-generation free-form
claim validator beyond the current exact-source-excerpt validation contract.

## 5. Current Safety Model

1. Supplied source policy documents are authoritative.
2. Amendments remain separate and are selected according to explicit temporal
   applicability rules.
3. Retrieval provides evidence candidates, not authority.
4. Evidence must directly support the requested conclusion.
5. Temporal applicability must be resolved where it affects the evidence.
6. Known conflicts and broken or materially unrelated references can block an
   answer.
7. Unsupported questions are returned as insufficient evidence or out of
   scope, rather than answered from general knowledge.
8. Missing required facts or dates can produce clarification.
9. Answer output is validated after generation.
10. Validation failure fails closed using the existing
    `INSUFFICIENT_EVIDENCE` safety status when an otherwise answerable result
    violates the output contract.
11. Citations must correspond to authoritative evidence and matching source
    provenance.
12. The original policy is never rewritten into a combined policy manual.

## 6. Current Runtime Flow

The actual pipeline flow is:

```text
Question
↓
Question Analysis
↓
Deterministic Lexical Retrieval
↓
Temporal Applicability Resolution
↓
Evidence Assessment
↓
Decision Gate
↓
ResolvedProvision Projection
↓
Answer Generation
↓
Output/Citation Validation
↓
Public/CLI Result
```

For blocked decisions, the answer layer produces no substantive sections and
the public interface preserves the structured blocking status and next action.

## 7. Current CLI and Build Commands

From the repository root in Windows PowerShell:

```powershell
python scripts\grounded.py ask "What is the household resource limit?"
python scripts\grounded.py ask "What is a unicorn rule?" --json
python scripts\grounded.py evaluate
python scripts\grounded.py evaluate --json
python scripts\grounded.py evaluate --audit audit\evaluation.jsonl
python scripts\build_artifacts.py
python scripts\inspect_artifacts.py
python scripts\inspect_validation.py
python -m pytest tests -q -p no:cacheprovider
```

The CLI also supports `--artifacts build\artifacts` for runtime loading of
offline artifacts and `--audit` for optional JSONL recording on question
execution. Non-answerable statuses have distinct non-zero exit codes.

## 8. Current Verification State

Latest verified test command:

```text
python -m pytest tests -q -p no:cacheprovider
153 passed
```

Latest artifact build reported:

- provisions: 137
- amendments: 6
- index records: 143

Step 18 validation inspection demonstrated:

- valid original: `VALID`
- valid amended: `VALID`
- tampered citation: `REJECTED`
- altered excerpt: `REJECTED`
- existing conflict: `CONFLICTING_AUTHORITY permitted=False sections=0`

Artifact-loaded validation was verified equivalent to source-loaded validation.

## 9. Current Evaluation Cases

The evaluation framework currently contains six representative cases, not ten:

1. Household resource limit — verifies a supported answerable question.
2. Missing determination date — verifies clarification rather than guessing
   the applicable earnings rule.
3. Reporting conflict — preserves the original reporting authority conflict.
4. Broken student cross-reference — blocks an unsupported full-time-student
   calculation conclusion.
5. Unsupported question — verifies insufficient-evidence behavior.
6. Amended earnings disregard — verifies answerability and Amendment 2026-01
   provenance for the `$175` rule.

These cases check status, answer permission, next action, and selected
provenance rather than merely checking whether answer text exists.

## 10. Known Policy/Corpus Edge Cases

- The original `§4.3.2` reporting provision says 10 calendar days, while
  original `§9.1.4` refers to 30 calendar days. The system preserves both
  claims and treats the unresolved authority conflict as a safety case.
- The full-time-student path involves `§1.4.6` and `§7.1.3 → §5.4`. The
  referenced provision is missing or materially unrelated to the requested
  student calculation. The system reports a broken/material cross-reference
  rather than inventing the missing rule.

These source issues must not be silently resolved or rewritten.

## 11. Current Limitations

The following capabilities are not fully implemented:

- Full second-stage retrieval expansion for every explicit cross-reference,
  definition, and related provision is not complete.
- A deterministic calculation engine is not fully implemented.
- Award and period-apportionment calculations are not fully implemented.
- Post-generation natural-language claim validation is not implemented beyond
  the current exact-source-excerpt validation contract.
- A dedicated citation formatter/validator module is not implemented; current
  validation is in `validation.py` and citation structures are in `answer.py`.
- Conversational refusal prose is not implemented.
- The ten-question evaluation corpus is not implemented; the current framework
  has six cases.
- Packaging metadata and an installed console entry point are not implemented.
- A web UI, database, and service deployment are not implemented.
- Runtime LLM integration is not implemented.
- Embeddings and vector search are not implemented.
- Multi-turn memory is not implemented.
- External document support is not implemented.
- Automatic legal or statutory interpretation is not implemented.

## 12. Explicit Non-Goals

The project does not seek to provide:

- Generic chatbot behavior.
- Uncited general knowledge.
- Best-guess policy completion.
- Automatic legal interpretation.
- Rewriting of the original policy manual.
- Silent resolution of source contradictions.
- Treating retrieval similarity as policy authority.
- Using an LLM as the policy authority.

## 13. Future Roadmap

The intended continuation is:

### Step 19 — Retrieval Strengthening

Improve deterministic retrieval coverage, especially explicit cross-reference
expansion, definition expansion, related-provision retrieval, and multi-clause
retrieval, while keeping retrieval auditable and deterministic.

### Step 20 — Deterministic Calculation Engine

Introduce policy-backed deterministic calculations for applicable numeric rules,
thresholds, disregards, and period/apportionment calculations where supported
by the policy evidence. Calculations must use resolved evidence and must not
rely on an LLM to perform policy arithmetic.

### Step 21 — Expanded Evaluation Corpus

Expand the current six-case evaluation framework into a stronger 10+ case
regression corpus covering normal questions, paraphrases, missing facts, dates,
amendments, historical transitions, conflicts, broken references, unsupported
questions, and calculations.

### Step 22 — Structured Answer and Refusal Layer

Improve user-facing grounded answers and refusal explanations while preserving
the existing evidence and validation boundary.

### Step 23 — Audit Completeness

Ensure an execution can be reconstructed from audit data across:

```text
question → retrieval → temporal applicability → evidence → decision
→ resolved provisions → answer → validation
```

### Step 24 — Documentation and Governance Refresh

Update stale documentation so it accurately reflects Steps 16–23 and the
current implementation. Review `README.md`, `ARCHITECTURE.md`, `DECISIONS.md`,
`AI-USAGE.md`, and `ANALYSIS.md`; keep historical documents clearly identified
as historical where appropriate.

### Step 25 — Final Hardening

Perform final regression testing, clean-clone verification, artifact
reproducibility checks, tamper testing, edge-case testing, documentation
verification, and final project review.

This section records intended future direction only. None of Steps 19–25 is
implemented by this documentation change.

## 14. Rules for Future Development

1. Read `PROJECT_STATUS.md` before making changes.
2. Read relevant source code and tests before modifying behavior.
3. Do not skip existing safety gates.
4. Do not make retrieval rank equivalent to policy authority.
5. Do not silently rewrite policy source documents.
6. Preserve amendment provenance.
7. Preserve temporal applicability semantics.
8. Preserve fail-closed behavior.
9. Add deterministic tests for new behavior.
10. Run the full test suite before declaring a step complete.
11. Do not mark a roadmap feature implemented until it actually exists and is tested.
12. Prefer minimal, modular changes.
13. Do not introduce an LLM where deterministic logic is required.
14. Do not invent policy rules when the supplied corpus is insufficient.
15. When evidence is insufficient, refuse or request the missing information.
16. Maintain backward compatibility of the existing CLI unless a step explicitly requires a change.
17. Never modify authoritative source policy documents as part of implementation.
18. Every new safety-sensitive output path must pass through the appropriate validation boundary.

## 15. Current Repository Truth

```text
Current completed step: Step 18
Next planned step: Step 19
Current test count: 153 passing
Current policy provisions: 137
Current amendments: 6
Current index records: 143
Runtime model dependency: none
Retrieval: deterministic lexical
Policy authority: supplied source documents
Answer safety boundary: evidence + temporal applicability + decision gate + output validation
```

