# THE GROUNDED — Project Status

This is the current continuity record for THE GROUNDED. It reflects the
repository through Step 25 and should be read before future development.

## 1. Identity and safety boundary

THE GROUNDED is a deterministic, offline, policy-evidence-based grounded RAG
system and policy decision aid. It is not a generic chatbot. Supplied policy
source documents are authoritative; generated text is not policy authority.

```text
Question
→ Question analysis
→ Deterministic lexical retrieval
→ Temporal applicability
→ Evidence assessment
→ Decision gate
→ ResolvedProvision projection
→ Grounded answer / structured refusal
→ Output validation
→ Public, CLI, and optional audit result
```

Retrieval supplies candidates but never authorizes an answer. Conflicts,
missing facts, insufficient authority, and material broken cross-references
remain fail-closed outcomes.

## 2. Implementation status

Steps 1–25 are complete as implemented/documented work:

- Original and amendment sources remain separate, with exact provision text,
  source metadata, cross-references, and provenance preserved.
- Amendment operations, applicability metadata, target validation, and
  `old_text` integrity validation are implemented.
- Deterministic `ProvisionStore`, `AmendmentStore`, offline artifact building,
  persisted lexical indexes, and artifact loading are implemented.
- Lexical retrieval is deterministic, bounded, duplicate-resistant, and
  supports explicit cross-reference/related-provision expansion where the
  corpus provides the relationship.
- Question analysis extracts intents, sub-questions, facts, dates, provision
  identifiers, numbers, and required slots.
- Temporal applicability distinguishes determination, change, reporting, and
  period dates, including the 1 March 2026 transition rules.
- Evidence, conflict, gap, and cross-reference checks feed the decision gate.
- `ResolvedProvision` / `ResolvedProvenance` projects query-specific
  applicable evidence without rewriting source documents.
- Answers are structured exact-source excerpts with citations. Blocked results
  contain structured status, reasons, missing facts, conflicts, gaps, and next
  actions, with no substantive answer sections.
- Step 18 validation checks source excerpts, citations, provenance, temporal
  alignment, and resolved provisions, and fails closed on invalid output.
- Step 20 provides one policy-backed deterministic Decimal calculation:
  countable monthly employment earnings after the applicable monthly earnings
  disregard.
- Step 21 provides ten deterministic evaluation cases, including supported,
  paraphrased, historical, amended, conflict, broken-reference, unsupported,
  multi-clause, and calculation cases.
- Step 22 provides clearer public and CLI answer/refusal presentation and
  optional calculation presentation.
- Step 23 extends append-only JSONL audit records so executions include
  retrieval results, temporal decisions, evidence, decision, resolved
  provisions, answer, validation, and calculation provenance.
- Step 25 completed final hardening: artifact reproducibility, validation and
  tamper checks, ten-case evaluation, representative CLI demonstrations,
  documentation consistency review, and generated-file/ignore-rule review.

## 3. Current architecture

The runtime modules are:

| Module | Responsibility |
|---|---|
| `ingest.py`, `amendments.py` | Parse immutable source artifacts. |
| `store.py`, `build.py` | Store records and build/load deterministic artifacts. |
| `retrieval.py` | Bounded deterministic lexical candidate retrieval. |
| `question.py` | Deterministic question and fact-slot analysis. |
| `temporal.py` | Query-date applicability resolution. |
| `evidence.py` | Authority, sufficiency, conflict, gap, and reference checks. |
| `decision.py` | Conservative answerability gate. |
| `resolved.py` | Query-specific resolved provision projection. |
| `answer.py` | Exact source-excerpt answer/non-answer structures. |
| `validation.py` | Final deterministic output validation and fail-closed behavior. |
| `pipeline.py` | Orchestrates all runtime stages. |
| `public.py`, `cli.py` | Structured public and command-line interfaces. |
| `calculation.py` | Small evidence-backed earnings calculation. |
| `audit.py` | Append-only deterministic JSONL execution records. |
| `evaluation.py` | Ten-case deterministic regression suite. |

There is no runtime LLM, database, vector store, web service, dedicated
`citations.py` module, conversational refusal generator, or general-purpose
calculation engine.

## 4. Verification state

Evaluation:

```text
10 cases, 10 passed, 0 failed
```

Latest full-suite command:

```text
python -m pytest tests -q -p no:cacheprovider
```

Latest observed result:

```text
170 passed, 7 failed, 8 errors
```

The seven failures and eight errors are Windows `PermissionError` / `WinError
5` failures involving disposable pytest, audit, and artifact temporary
directories. They are environment/test-cleanup limitations, not policy or
application assertion failures. Focused Step 23 tests and the relevant public,
CLI, and evaluation tests pass.

Artifact inspection remains available through `scripts\inspect_artifacts.py`;
audit inspection succeeds when run with permission to create its disposable
temporary JSONL file.

## 5. Known corpus edge cases

- Original `§4.3.2` and `§9.1.4` contain incompatible reporting claims. Both
  remain visible and the decision is `CONFLICTING_AUTHORITY` when unresolved.
- The full-time-student path includes a materially unrelated/broken
  `§7.1.3 → §5.4` reference. The system does not invent the missing student
  calculation rule.

## 6. Current limitations

- The calculation layer supports only the demonstrated monthly earnings
  disregard calculation; it does not calculate awards or period apportionment.
- Exact-source-excerpt validation is implemented, not unrestricted semantic
  claim validation.
- Refusal output is structured rather than conversational prose.
- Packaging, installed console entry points, web UI, database/service
  deployment, multi-turn memory, external documents, LLM runtime integration,
  embeddings, and automatic legal interpretation are not implemented.
- The audit record is reconstructive local JSONL, not a database or remote
  observability service.

## 7. Non-goals

The project does not provide generic chatbot behavior, uncited general
knowledge, best-guess policy completion, silent conflict resolution, rewritten
policy manuals, or LLM-based policy authority.

## 8. Roadmap

Step 25 final hardening is complete. There are no additional roadmap steps:

### Step 25 — Final Hardening

Final regression testing, artifact reproducibility checks, tamper testing,
edge-case testing, documentation verification, and final project review are
complete. The known Windows temporary-directory permission limitation remains
environment-only.

## 9. Rules for future development

Read this file first. Preserve source authority, amendment provenance,
temporal semantics, decision gating, validation, fail-closed behavior, and
deterministic tests. Never treat retrieval rank as authority or invent policy
content. Do not modify authoritative source documents.

## 10. Repository truth

```text
Current completed step: Step 25
Next planned step: none
Evaluation: 10 passed, 0 failed
Latest full-suite result: 170 passed, 7 failed, 8 errors (Windows permissions)
Retrieval: deterministic lexical with bounded expansion
Calculation: monthly earnings disregard only
Policy authority: supplied source documents
Safety boundary: evidence + temporal applicability + decision gate + validation
Artifact reproducibility: identical across consecutive builds
Validation/tamper checks: passed
```
