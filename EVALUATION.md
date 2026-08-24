# Evaluation Set

This evaluation set is a deliberate 10-case behavioral test set for the grounded policy assistant. It checks grounding, refusal behavior, temporal policy resolution, conflict handling, broken references, paraphrasing, multi-clause questions, and calculations. A passing result means the implementation produced the expected behavior for these cases; it is not a claim that ten examples exhaustively prove policy correctness.

## How to run

From the repository root, run:

```powershell
python scripts\grounded.py evaluate
```

The evaluation uses the existing public interface and checks structured outcomes, including status, answer permission, next action, provenance, and calculation results where applicable.

## Cases

| Case | Question | Behavior checked | Expected behavior | Actual result |
|---|---|---|---|---|
| 1. `supported-household-resource-limit` | `What is the household resource limit?` | A directly supported original-policy question is answerable. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`. |
| 2. `missing-earnings-determination-date` | `How much earnings can be disregarded?` | A determination-sensitive question without the required date requests clarification. | `NEEDS_CLARIFICATION`; `answer_permitted=False`; next action `request_missing_facts`. | PASS — actual status `NEEDS_CLARIFICATION`, permitted `False`, next action `request_missing_facts`. |
| 3. `reporting-rule-conflict` | `How many days must I report a change occurring on 28 February 2026?` | The historical reporting provisions produce conflicting authority. | `CONFLICTING_AUTHORITY`; `answer_permitted=False`; next action `escalate_conflict`. | PASS — actual status `CONFLICTING_AUTHORITY`, permitted `False`, next action `escalate_conflict`. |
| 4. `broken-student-cross-reference` | `How is a full-time student treated in the needs calculation for a determination on 1 March 2026?` | A materially broken or unrelated policy cross-reference blocks a conclusion. | `BROKEN_CROSS_REFERENCE`; `answer_permitted=False`; next action `explain_broken_cross_reference`. | PASS — actual status `BROKEN_CROSS_REFERENCE`, permitted `False`, next action `explain_broken_cross_reference`. |
| 5. `unsupported-unicorn-rule` | `What is a unicorn rule?` | A question outside the supplied policy evidence is not answered from general knowledge. | `INSUFFICIENT_EVIDENCE`; `answer_permitted=False`; next action `explain_insufficient_evidence`. | PASS — actual status `INSUFFICIENT_EVIDENCE`, permitted `False`, next action `explain_insufficient_evidence`. |
| 6. `amended-earnings-disregard` | `What is the $175 earnings disregard for a determination on 1 April 2026?` | A post-effective-date question uses the amendment and preserves its provenance. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`; source amendment `2026-01 §1.1`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`, amendment provenance preserved. |
| 7. `paraphrased-household-resources` | `How much money can a household have in resources?` | A paraphrased supported question remains retrievable and answerable. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`. |
| 8. `historical-original-earnings-disregard` | `What is the earnings disregard for a determination on 1 February 2026?` | A pre-effective-date question uses the historical original provision. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`; source provision `§6.4.1`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`, original provision provenance preserved. |
| 9. `multi-clause-resource-and-earnings` | `What is the household resource limit and what earnings disregard applies for a determination on 1 April 2026?` | A multi-clause question retains coverage for both requested policy issues. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`. |
| 10. `calculated-amended-earnings` | `What is the $175 earnings disregard for a determination on 1 April 2026?` | The supported deterministic calculation uses the amended disregard and preserves calculation provenance. | `ANSWERABLE`; `answer_permitted=True`; next action `answer`; calculation status `CALCULATED`; gross earnings `500`; countable earnings `325`; amendment `2026-01`. | PASS — actual status `ANSWERABLE`, permitted `True`, next action `answer`, calculation and amendment provenance preserved. |

## Verified result

The evaluation was run with the repository command shown above.

- Total cases: **10**
- Passed: **10**
- Failed: **0**

This set is a deterministic regression check for the listed behaviors. It does not exhaustively establish that every possible policy question is answerable or that ten examples alone prove complete policy correctness. The system remains fail-closed when required facts are missing, evidence is insufficient, authority conflicts, or a material cross-reference is broken.
