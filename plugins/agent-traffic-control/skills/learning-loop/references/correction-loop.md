# A correction loop that can remove rules

The unit of learning is an evidenced correction to a decision, not another instruction. Keep private incident records in the project's existing lesson or decision store. Public skills contain generalized methods or clearly synthetic examples, not the identifying incident or its private trace.

## 1. Capture the discrepancy

At a material result or correction, record the intended outcome, observed outcome and exact artifact identities. Preserve the original owner wording and its scope. Separate an observation (a selected result was worse) from a proposed cause (the selector rewarded the wrong property).

Use the existing record format where possible. A compact record needs:

| Field | Purpose |
|---|---|
| ID, goal and scope | Stable reference; which decision and conditions it concerns |
| Expected / observed | Concrete discrepancy, not a vague success or failure |
| Evidence and versions | Private artifact pointers, inputs, labels, baseline and code identities |
| Cause status | Reproduced, supported but unconfirmed, or hypothesis; how to check it |
| Candidate correction | Smallest change that could prevent the mistake |
| Evaluation | Reproduction, legitimate counterexample, baseline comparison and outcome |
| Disposition | Candidate, tested, incorporated, superseded or retired; destination and reason |
| Revisit trigger | A condition that would invalidate it, rather than an arbitrary expiry date |

Missing evidence is unavailable, not a negative result. Prefer a bounded reproduction over another round of narration. No cause should become fact merely because several agents repeated it.

## 2. Locate the right correction

Ask whether the problem belongs in code, data, measurement, orchestration, a product decision or memory. A testable invariant often belongs in a test; a current project fact belongs in a project record; a general coordination failure may justify a skill reference. Use one canonical explanation with pointers elsewhere.

Search for existing guidance before adding a rule. Inspect the description, index entry, example and body for the same cause: correcting only the long explanation leaves retrieval pointing at the old mistake. Contradictory causes require checking evidence; recency alone does not choose the winner.

If a worker stalled, ask which exact precondition blocked it. Narrow an overbroad workflow preference when authorized rather than automatically creating another exception or another worker. Never relax an owner policy, safety requirement or release hold through an automatic lesson update.

## 3. Evaluate the proposed change

Choose the smallest useful evaluation for the risk:

- Reproduce the failure with pinned inputs when feasible. If it cannot be reproduced, retain uncertainty and avoid a strong causal rule.
- Include a legitimate case the new guidance must still allow. A missing named entity should fail; a genuine request for the largest entity should still select by rank and label the result correctly.
- For meaningful workflow changes, compare a baseline run with the proposed guidance on a fresh or held-out task. Give both the same tools, budget and raw evidence; do not tell the evaluator the desired verdict. Where only a tabletop review is possible, label it as such.
- Check completion quality, errors, unnecessary refusals/permission requests, elapsed work and context cost. A new safeguard that prevents an error but blocks all useful work has not passed.
- Small samples establish a local check, not a general performance claim. Preserve negative or mixed outcomes and don't select only the successes for the report.

Do not run a large review panel for every wording edit. A local structural check and focused reading are enough for low-risk prose; executable helpers need real tests. Do not claim a schema validator tested reasoning behavior.

## 4. Update, then verify

Within the current maintenance authorization, apply the narrowest supported edit and record its evidence, scope and rollback/revisit condition. Prefer clarifying or replacing an existing instruction to accumulating one-off rules. Recheck conflicting instructions, reference paths and discoverability. When a correction changes a claimed cause, mark the old claim as superseded in the private record; do not silently erase history or copy private retired wording into a public package.

Verify the installed version as well as the canonical source. A release number does not prove the loaded bytes changed. Before public publication, anonymize names, dates, IDs, paths and combinations of details that identify the incident, and inspect the full package. Publication of one update does not grant perpetual automatic publishing authority.

## 5. Revisit on evidence, not a timer

At a later relevant failure, changed dependency or review, ask: did this rule help a decision, duplicate a tool guarantee, cause a false stop, or become irrelevant? Keep, narrow, demote to a reference, replace with a test, or retire it with a reason. Lack of recent use alone does not disprove a rarely needed constraint.

The loop ends for this event when the correction is incorporated and checked, rejected with evidence, or explicitly left pending. Do not recursively run self-improvement because the skill describes self-improvement. Schedule future work only when the user requests it.

## Synthetic mechanism examples

| Discrepancy | Useful correction | Overreaction to avoid |
|---|---|---|
| A report labeled for one service silently measures the busiest service instead | Bind the named service by ID; add an unrelated busier service and a missing-ID regression | Ban ranking even when the question asks for the busiest service |
| Aggregate prediction improves but none of the displayed choices improve | Evaluate shortlist membership within each comparable candidate pool | Deploy based solely on the pooled benchmark |
| A prettier intermediate artifact changes during final conversion | Check exact identity through the delivery boundaries | Assume an intermediate screenshot proves served behavior |
| A user revises a grade on a transformed artifact | Preserve versioned labels and bind the correction to the exact artifact | Treat all historical grades as interchangeable |
| A search stops after its limit | Preserve evaluated coverage and best verified fallback | State that no better candidate exists |
| Several workers wait for the entire repository to become idle | Scope locks to owned objects and serialize only shared integration | Disable ownership checks completely |
| An archive links only to an expired temporary file | Preserve durable bytes and a verified manifest at the checkpoint | Repeat expensive experiments because a link expired |
