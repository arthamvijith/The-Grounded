# Analysis — Problem 1: The Grounded Answer

## Scope reviewed

I inspected all provided source material before any application code was written:

- `source/original/README.md`
- `source/original/1 - The Grounded Answer.docx`
- `source/original/policy-manual.md`
- `source/amendment/READ ME FIRST.md`
- `source/amendment/Amendment No. 2026-01.md`

There were no existing application files, tests, labels, or question set in the workspace.

## Required outcome

The requested system is a one-question, command-line policy assistant. It must:

1. Answer plain-language policy questions using only the supplied corpus.
2. Support every substantive claim with an exact, clause-level citation such as `§4.3.2`.
3. Refuse visibly when the manual does not cover the question or is ambiguous, explain that it cannot settle the issue, and indicate who should be consulted next.
4. Include a self-authored ten-question evaluation set, including refusal cases, with honest pass/fail results.
5. Run from a clean clone using the README alone.
6. Include a running demo, real commit history, `DECISIONS.md`, and `AI-USAGE.md`.

The brief explicitly says that a web interface, multi-turn memory, training/fine-tuning, support for other documents, and latency optimization are not required.

## Corpus authority and citation model

The policy manual is the complete authority. General benefits-program knowledge must not be used to fill gaps. The stable clause numbering in the manual is the citation boundary and should be preserved in any indexed or rendered representation.

The original manual is consolidated through 31 December 2025. Amendment No. 2026-01 is part of the corpus and must be applied as an amendment to that manual, not treated as a replacement document.

## Material policy structure

- Parts 1–5: scope, definitions, eligibility, residence, exclusions, and special household circumstances.
- Parts 6–7: countable income, disregards, thresholds, needs figures, adjustments, and payments.
- Parts 8–10: applications, evidence, determinations, overpayments, recovery, suspension, termination, and sanctions.
- Parts 11–12: review and appeal.

Important operational anchors include:

- Eligibility is assessed at household level (§§2.1.1–2.1.3).
- Residence, age, income, resources, exclusions, and valid application are cumulative eligibility conditions (§2.1.2).
- The resource limit is $4,000, subject to listed exclusions (§2.4).
- Income thresholds and award calculations depend on household size/composition and applicable disregards (§§6.4, 6.6, 7.1–7.3).
- Changes of circumstances, evidence requests, determinations, overpayments, sanctions, review, and appeal have separate procedural rules and deadlines.

## Conflicts, gaps, and traps identified

### 1. Original reporting-period conflict

The original manual says a recipient must report a change within 10 calendar days in §4.3.2. However, original §9.1.4 refers to the “30 calendar days required under §4.3” when limiting an overpayment. Those provisions cannot both describe the same reporting requirement. The amendment resolves this going forward, but historical questions still require date-sensitive treatment.

### 2. Amendment changes are not globally effective in the same way

Amendment No. 2026-01 was issued 12 February 2026 and is effective 1 March 2026.

- Earnings disregard: `$120` becomes `$175`.
- Income thresholds change to `$1,225`, `$1,650`, `$2,075`, `$2,500`, `$2,925`, then `+$425` per additional member.
- Sanction reduction changes from `20%` to `15%`.
- A new §10.5.3A bars a sanction for a failure to report when the change would have increased the award.
- The reporting deadline changes from 10 to 14 calendar days.
- The §9.1.4 overpayment protection reference changes from 30 to 14 calendar days.

Transitional treatment must be explicit:

- Paragraphs 1, 3, and 4 apply to determinations made on or after 1 March 2026, including determinations about an earlier period.
- Paragraph 2 applies only to changes occurring on or after 1 March 2026. A pre-1 March change keeps the reporting period in force when that change occurred, regardless of determination date.
- A period spanning 1 March uses the figures in force on each day and is apportioned under §7.4.3.

Therefore, “claim date” alone is not always sufficient as a temporal key. The answer logic needs to distinguish at least determination date, change-of-circumstances date, and the dates covered by an award/claim period. If the user omits a date that changes the answer, the safe behavior is to request it or refuse to settle the issue.

### 3. Apparent full-time-student gap / bad cross-reference

§1.4.6 defines a full-time student. §§3.2.3 and 5.2.3 say full-time education is addressed separately, but the apparent destination in §7.1.3 is `§5.4`; §5.4 actually concerns care allowances and contains no student rule. The manual therefore does not clearly state the needs calculation or household treatment for full-time students. An answer that invents a student rule from the surrounding text should refuse and identify the ambiguity.

### 4. Deliberate-misrepresentation boundary

The manual permits a higher recovery rate and temporary exclusion for deliberate misrepresentation or deliberate nondisclosure (§9.6.1), but expressly says that failure to report alone is not evidence of deliberate misrepresentation (§9.6.2). This is a likely refusal/qualification test: lateness alone cannot support the stronger conclusion.

### 5. Other ambiguity-sensitive areas

The manual contains discretionary language (`may`) and fact-dependent standards, including ordinary residence, fair reflection of irregular earnings, reasonable evidence, good cause, hardship, and whether an absence was outside the recipient’s control. These should be presented as conditional decisions tied to the relevant clause, not as unconditional outcomes.

## Proposed answer/refusal boundary

Answer only when the applicable version of the manual supplies a sufficiently direct rule and the facts needed to apply it are present. Refuse or request clarification when:

- the issue is outside the manual;
- a necessary date/version is missing;
- the manual’s relevant provisions conflict or contain a broken cross-reference;
- a conclusion depends on an unresolved factual or discretionary assessment; or
- the available passages are merely adjacent context rather than authority for the requested conclusion.

Refusals should cite the relevant clauses showing the gap or conflict and direct the user to a supervisor, the Department, or the appropriate review/appeal route as applicable. This boundary and its rationale must also be recorded in `DECISIONS.md` when implementation begins.

## Evaluation implications

The eventual ten-question test set should cover ordinary eligibility, resource exclusions, income/disregards, award calculation, deadlines, amendment transitions, the §4.3.2/§9.1.4 history, the full-time-student cross-reference gap, and at least one deliberate refusal. Results must report failures rather than selecting only easy passing questions.

## Implementation deliberately not started

No application code, indexing pipeline, retrieval logic, answer generator, tests, or other implementation artifacts were created in this step. Per instruction, work stops after this analysis document.
