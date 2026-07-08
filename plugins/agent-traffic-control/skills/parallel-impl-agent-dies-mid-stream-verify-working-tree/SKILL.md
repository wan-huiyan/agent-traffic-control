---
name: parallel-impl-agent-dies-mid-stream-verify-working-tree
description: |
  A dispatched parallel implementation subagent can die mid-stream and leave ZERO durable
  output while the harness still reports the task "completed". Use when: (1) you fanned out
  2+ foreground impl agents (Agent/Task tool) to edit code in one repo, (2) one returns
  `API Error: Response stalled mid-stream` / an empty or truncated final message, possibly
  alongside a background "<task> completed (exit code 0)" notification, (3) you're about to
  integrate or commit their combined work. The "completed" status is a LIE here — the agent
  may have written nothing (target file untouched, no test created, its self-made todos all
  still pending). ALWAYS reconcile each agent's CLAIMED work against the actual working tree
  (`git status`, grep the target file for the expected change) before integrating; the
  healthy sibling's work is usually intact, so just finish the dead agent's task yourself.
  Sister to subagent-reports-complete-but-pr-unmerged (work done, integration skipped) and
  credit-stall-mid-orchestration-revive-collision (stalled then auto-revives and races).
  Pairs with shared-file-redesign-parallel-author-serial-integrate (the no-commit → serial
  path-scoped integrate pattern that makes this degrade gracefully).
author: Claude Code
version: 1.0.0
date: 2026-06-26
disable-model-invocation: true
---

# Parallel impl agent dies mid-stream — verify the working tree, not "completed"

## Problem
You dispatch N foreground implementation agents in parallel (disjoint files). One comes
back with `API Error: Response stalled mid-stream` (or an empty/truncated report), and the
harness may even emit a background "<task> completed (exit code 0)" line. If you trust that
and integrate, you ship a hole: the agent wrote NOTHING — its target route is untouched, no
test file exists, the todos it created for itself are all still `pending`.

## Context / Trigger Conditions
- 2+ parallel `Agent`/`Task` impl agents editing code in one repo.
- One returns a stall/timeout/empty final message; `subagent_tokens` ~0; a "completed" status.
- You're about to run a combined `git add`/commit or a whole-repo check across both outputs.

## Solution
1. **Reconcile claimed-vs-actual before integrating.** For each agent: `git status --short`
   and grep its target for the expected change (e.g. `grep -n generateChineseText route.ts`).
   A missing edit + no new test file = the agent died; "completed (exit 0)" was the harness
   reporting the shell wrapper exited, NOT the work landing.
2. **Don't try to revive a dead foreground agent — finish its task yourself.** Unlike a
   credit-stall suspension, a mid-stream API death leaves no resumable state. You have full
   context; do it in the main loop (or redispatch a fresh agent with the same brief).
3. **It degrades gracefully because of the orchestration guardrails:** agents do NOT commit
   and do NOT run whole-repo type-check (avoids git-index races + cross-agent `tsc`
   false-positives on half-written files); the orchestrator does path-scoped
   `git add <exact files>` per unit + the full check at integration. So the survivor's work
   is clean and committable independent of the casualty.

## Verification
`git status` + a grep of each target shows exactly the expected edits from the SURVIVING
agents and nothing from the dead one; after you finish the dead one's task, the full suite +
type-check pass before any commit.

## Notes
- TRAP, surfaced reactively (`disable-model-invocation`): recall by grepping lessons/skills
  when a parallel agent returns a stall, or via the `/name` invocation.
- The lie is specifically "completed (exit 0)" on the shell *wrapper*, not on the agent's
  work. Same family as subagent-reports-complete-but-pr-unmerged — different gap: there the
  code exists but the PR isn't merged; here the code was never written.

## References
- See also: credit-stall-mid-orchestration-revive-collision,
  subagent-reports-complete-but-pr-unmerged,
  shared-file-redesign-parallel-author-serial-integrate.
