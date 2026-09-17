---
name: fan-out-cost-control
description: Control agent fan-out cost through deliberate model selection, bounded context, useful checkpoints and limits on nested consultations.
author: Claude Code
version: 1.3.0
date: 2026-09-17
disable-model-invocation: true
---
# Fan-Out Cost Control

Use when a parallel investigation's cost, context or nested work needs control. Agent count alone misses expensive consultations, inherited models and repeated context. A successful run can still exceed the intended budget.

## Choose the model and scale before launch

Check the actual launcher: omitting its model option may inherit the parent's model. Setting reasoning effort alone does not necessarily select a cheaper model. Specify the intended model through supported controls; if the host forbids an override for a full-history fork, choose an allowed dispatch or report the limitation. Do not assume every host inherits identically.

Before a substantial fan-out, state the model/tier, effort, planned count or ceiling, and purpose. Account for nested agents, external reviewers and consultations. Use efficient models for bounded extraction or formatting when appropriate, stronger ones where the uncertainty warrants them. Consult the current decision record before launching a search for an answer already settled there.

Where a coordinator owns shared timing or resources, reconcile the plan with that owner. An existing grant can cover the work; do not invent a fresh mandatory approval for each authorized launch. A peer's agreement controls timing and ownership, not the user's release or spending authority.

## Control consultation multiplication

A helper that forwards each worker's transcript to a stronger model can cost much more than its call count suggests. Check its actual payload and usage. A standing review preference applied inside every shard can multiply the entire fan-out again.

For independent extraction shards, aggregate evidence and uncertainty before commissioning a shared review where that is sufficient. Set this scope in the initial brief. Do not suppress required independent checks or override a worker's higher-priority instructions to save tokens. A confidence label is useful uncertainty, not a substitute for necessary verification.

If investigating cost, inspect calls made by children and consultation tools as well as the root's visible agent count. Shared rate-limit failures can be a clue to shared-resource contention, not proof that a particular session caused it.

## Choose context deliberately

Repeated turns may process substantial prior context. The amount actually retained, cached and billed depends on the host. Track input, reasoning, output and tool work where available; do not infer cost solely from turn count or insist that all resumes resend an entire transcript.

When useful evidence is durable, a new helper with a focused brief can cost less than resuming a large history. If the active worker has irreplaceable useful context, continuing may be cheaper. Compare the remaining work and evidence needed, not the habit of always restarting or always resuming. Do not forbid necessary exploration just to reduce the number of turns.

## Preserve useful partial work

For long or interruptible jobs, ask workers to save independently usable results as they complete them, with exact input identities and completion state. Use separate files or atomic replacement where multiple writers could collide. Do not expose a partial artifact as complete.

Checkpointing is easiest to arrange before launch. If a running job needs it, weigh a safe checkpoint against the interruption cost rather than assuming the instruction always arrives too late. Short atomic tasks may need no extra checkpoint machinery.

A hard stop limit belongs to this section too: a job timeout, a wall-clock ceiling, a watchdog kill. Size it from the work's own declared budgets and its real concurrency, not from an estimate of how long the work ought to take. Where a unit runs several internal stages in sequence, each holding a budget of its own, the unit's floor is their sum; a limit set below that sum kills the unit at the same point on every attempt, which reads as a flaky job rather than as a limit chosen too tight. Check whether the runner applies the limit per task or per unit, and whether a retry inherits it.

When a limit fires, the task ends where it stands. Whatever was held only in memory or on a local scratch path goes with it, and only what was already written to durable storage survives — so a limit set below the work's floor converts completed work into a charge with no output. Changing that limit is usually a change to the job definition rather than to a running task, so read the definition back after the change and compare it to what you intended, and confirm nothing else in the definition moved with it.

## Stop based on authority and remaining value

Honor an explicit stop or budget limit. When choosing whether to continue within authorization, inspect saved progress and remaining cost. Sunk cost is not a reason to spend through a limit. Cancellation and rate-limit recovery differ by host; neither guarantees retained transcripts or lost outputs. Save what can be saved safely, and record the real continuation state.

Observe meaningful progress, tool failures and deadlines. In row-producing work, new valid rows can be useful evidence; other diagnoses can progress without writing rows. Prefer host event notifications or bounded status checks. A filesystem watcher avoids repeated model calls but still consumes compute; it is not literally cost-free and does not authorize a background scheduler.

## Check the outcome

- Compare planned model, effort and width with what actually launched, including nested consultations.
- Check the expected evidence was saved and that incomplete workers are not reported as clean reviewers.
- Compare total cost and completion quality, including retries and integration. Parallelism can reduce elapsed time without reducing tokens.
- Preserve the limiting evidence if the run stopped. Do not turn a bounded search into a claim that no solution exists.
- A run that was stopped still costs whatever it consumed before stopping. Price a cancellation as spend, and do not read a missing completion time as evidence that the work never ran: a record with no completion timestamp is as consistent with a task that was killed late as with one that never started. `poll-loop-treats-an-unreadable-status-as-finished` covers the reader-side half of that, where an unparseable status is taken for a terminal one.

For difficult research reasoning, read [Research Garden's dispatch guidance](../research-lane-coordinator/references/dispatch-and-effort.md). For a demonstrated workflow failure, use [Learning Loop](../learning-loop/SKILL.md) to test a narrow correction rather than imposing a permanent model or agent-count rule.

## Synthetic example

A coordinator intends a small team of economical extraction workers. Its launcher specifies high effort but no model, and the workers each invoke a separate premium reviewer. Every output looks correct while usage exceeds the plan. The correction is to verify launcher inheritance, choose supported model controls, cap nested work and review the combined evidence when that meets the requirement. A task that actually requires independent specialist review remains allowed.
