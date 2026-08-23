# THE GROUNDED

THE GROUNDED is a deterministic, policy-evidence-based system. It answers
only when the existing retrieval, temporal, evidence, and decision layers
permit an answer.

## Command-line interface

Run the CLI from the repository root with the included launcher:

```powershell
python scripts\grounded.py ask "What is the household resource limit?"
```

The CLI uses the existing public interface and prints structured human-readable
output. Use `--json` for deterministic machine-readable output:

```powershell
python scripts\grounded.py ask "What is a unicorn rule?" --json
```

Non-answerable outcomes have distinct exit codes. An answerable question exits
with `0`; clarification, conflict, broken cross-reference, insufficient
evidence, and out-of-scope results exit with `2`, `3`, `4`, `5`, and `6`.

To append an execution to the existing local JSONL audit log:

```powershell
python scripts\grounded.py ask "What is the $175 earnings disregard for a determination on 1 April 2026?" --audit audit\executions.jsonl
```

Run the deterministic regression suite with:

```powershell
python scripts\grounded.py evaluate
python scripts\grounded.py evaluate --json
python scripts\grounded.py evaluate --audit audit\evaluation.jsonl
```

Build reproducible offline source and search artifacts with:

```powershell
python scripts\build_artifacts.py
```

The default output is `build\artifacts`. Load those artifacts at runtime with:

```powershell
python scripts\grounded.py ask "What is the household resource limit?" --artifacts build\artifacts
```

Inspect the build/load equivalence and amendment integrity validation with:

```powershell
python scripts\inspect_artifacts.py
```

The evaluation command exits `0` when all cases pass and `11` when a
regression case fails. Use `python scripts\grounded.py --help` and
`python scripts\grounded.py ask --help` for concise usage information.
