# THE GROUNDED

THE GROUNDED is a deterministic, offline, policy-evidence-based grounded RAG
system and policy decision aid. It answers only when supplied policy evidence
is applicable, authoritative, sufficient, and validated. Retrieval alone never
authorizes an answer.

## Runtime flow

```text
Question → retrieval → temporal applicability → evidence
→ decision gate → ResolvedProvision → grounded answer/refusal
→ output validation → public/CLI result → optional audit
```

The original policy manual and amendments remain separate authoritative source
artifacts. The system does not use an LLM, network service, database,
embeddings, or vector search at runtime.

## Quick start

From the repository root in Windows PowerShell:

```powershell
python scripts\grounded.py ask "What is the household resource limit?"
python scripts\grounded.py ask "What is a unicorn rule?" --json
```

Blocked results have distinct exit codes: clarification `2`, conflict `3`,
broken cross-reference `4`, insufficient evidence `5`, and out of scope `6`.
Answerable results exit `0`.

For the supported earnings calculation, provide the gross amount explicitly:

```powershell
python scripts\grounded.py ask 'What is the $175 earnings disregard for a determination on 1 April 2026?' --gross-monthly-earnings 500
```

This uses the applicable policy disregard and reports the countable monthly
amount with amendment provenance. It is not a general-purpose calculator.

## Evaluation and audit

The deterministic regression suite contains ten cases:

```powershell
python scripts\grounded.py evaluate
python scripts\grounded.py evaluate --json
python scripts\grounded.py evaluate --audit audit\evaluation.jsonl
```

Record one execution in append-only JSONL, including complete pipeline-stage
information:

```powershell
python scripts\grounded.py ask "What is the household resource limit?" --audit audit\executions.jsonl
python -X utf8 scripts\inspect_audit.py
```

## Offline artifacts

Build and inspect reproducible source-derived artifacts:

```powershell
python scripts\build_artifacts.py
python scripts\inspect_artifacts.py
python scripts\grounded.py ask "What is the household resource limit?" --artifacts build\artifacts
```

## Validation and tests

```powershell
python -X utf8 scripts\inspect_validation.py
python -m pytest tests -q -p no:cacheprovider
```

Validation is the final safety boundary before public/CLI exposure. Invalid
citations, altered source excerpts, mismatched provenance, unresolved
conflicts, missing required facts, and broken authority remain non-answerable
outcomes. The current environment may report Windows temporary-directory
`PermissionError` / `WinError 5` failures in audit and artifact tests; these are
test-environment cleanup limitations, not an instruction to weaken assertions
or policy safeguards.
