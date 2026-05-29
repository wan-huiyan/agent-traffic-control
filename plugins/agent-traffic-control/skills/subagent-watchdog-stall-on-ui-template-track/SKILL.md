---
name: subagent-watchdog-stall-on-ui-template-track
description: |
  Recognise the failure mode where a `general-purpose` (or similar)
  subagent dispatched to do UI/template-heavy work stalls and gets killed
  by the no-streamed-output watchdog (~600s of silence → terminate). Use
  when: (1) you dispatched a subagent for UI work (new page route +
  Jinja/template authoring + per-step iterative tests + small CSS),
  (2) the agent reports `failed: Agent stalled: no progress for 600s
  (stream watchdog did not recover)` with a partial result fragment like
  "Now let me look at the routes..." indicating it died mid-investigation,
  (3) the worktree contains uncommitted changes (the agent edited files
  before going silent and the work is salvageable), (4) you're considering
  re-dispatching with the same prompt or a "tighter" version — DON'T,
  because the stall is structural to dispatching this shape of work, not
  the prompt's fault. The fix is to switch to inline execution for the
  remainder of THIS task and bias toward inline for future UI/template
  tracks even though they cost more main-context tokens.

  Sister skill: `parallel-subagent-ui-from-contract-table-design-anemic`
  (a different UI-subagent failure mode: agents complete but produce
  design-anemic HTML). This skill covers the OPERATIONAL stall;
  the sister skill covers the QUALITY anemia. Same dispatch antipattern,
  two distinct failure modes.
author: Claude Code
version: 1.0.0
date: 2026-05-27
---

# Subagent watchdog stall on UI/template tracks

## Problem

You dispatched a `general-purpose` subagent (or any agent running in the
background via the Agent tool) to write a new UI screen — a route +
Jinja template + a few tests. The agent reads existing patterns, plans
template structure, drafts the template, iterates on test failures...
and stalls. You get:

```
status: failed
summary: Agent "Phase C: Screen 03 live workspace" failed: Agent stalled:
  no progress for 600s (stream watchdog did not recover)
result: "Now let me look at the routes I'll consume (render, bundle,
  upload) and existing templates."
```

The result fragment shows it was mid-investigation. The worktree may
contain partial edits.

## Context / Trigger Conditions

Recognise this trap when:

- The dispatched task is UI/template-heavy. Specifically: lots of file
  reads (template patterns, view models, helpers) + Jinja/HTML/CSS
  authoring + iterative test-write → run → fix → repeat loops.
- The agent's last reported output is "Now let me ..." or similar —
  i.e. a tool-call prefix, not a result.
- Total elapsed time before stall is in the 10-15 minute range.
- Re-running the same prompt produces the same stall (verified on the
  S16 Phase C retry — second attempt died at "Now let me look at the
  routes I'll consume...").
- Comparable backend-only subagents in the same session completed
  successfully (e.g. Phase B render path took ~16 minutes and emitted
  101 tool uses without stalling).

## Why the stall happens (theory, not guaranteed)

The watchdog kills the agent when stdout is silent for ~600 seconds.
On UI tracks the agent spends meaningful contiguous time in:

- Multi-file reads scanning template macros + view_models
- Pydantic introspection / route-spec reading
- Mental modelling of step-state machines

These phases sometimes do not emit streamed tokens to the orchestrating
host — the agent is computing, not narrating. The watchdog sees no
output, kills the task, and reports a stall.

Backend tasks emit more constant streamed output: pytest runs, gh CLI
commands, git operations all produce stdout naturally.

## Solution

### Stop dispatching this task. Do it inline.

1. **Salvage partial work.** `cd` into the worktree the stalled agent
   was using and run `git status --short`. If files are modified, the
   agent did real work before going silent — diff them and finish
   inline (`Read`, `Edit`, `Write`, `Bash` tool calls all stream output
   naturally and never trigger the watchdog).

2. **Don't re-dispatch with the same prompt.** Even with "tighter scope"
   or "commit every N minutes" hints in the prompt, the stall is
   structural. Two consecutive S16 Phase C dispatches both stalled.

3. **Don't re-dispatch with a different subagent type either.** The
   watchdog is at the Agent-tool layer; switching `general-purpose` to
   `feature-dev` or similar will not help.

4. **Inline cost:** higher main-context token usage (you do the reads
   yourself, you do the edits, you maintain the test loop). For a
   typical UI screen that's ~300-500 lines, expect ~20-30 tool calls
   inline. Worth it: 100% completion reliability vs ~0% subagent.

### When IS subagent dispatch fine for UI work?

Subagents complete reliably when:

- The UI work is well-bounded and has minimal back-and-forth
  (e.g. "add a single field to an existing form, copy the pattern from
  X.html, one test")
- The agent has a small "files to read" surface (≤ 3-4 files)
- The agent's test-write loop is single-iteration (write test, expect
  it to pass first try based on the contract)

Subagents fail (stall) when:

- The agent needs to scan many template files to understand the design
  system before authoring
- The iterative test loop has 3+ rounds (test fails → fix template →
  test fails again → fix CSS → retest)
- The agent has to make many small UX judgement calls (whitespace,
  class names, button states) that don't produce streamed output

## Verification

After switching to inline:

- Tool calls visibly emit results
- File state updates between calls match expectations
- Tests run in seconds, results visible
- Commit succeeds, push succeeds, PR opens

Done. UI track shipped.

## Example (real)

S16 Phase C — Screen 03 live workspace in the-handover-repo:

- **Attempt 1:** Dispatched `general-purpose` subagent with comprehensive
  prompt. Stalled at 600s; result fragment: "Now let me check the design
  doc for Screen 03 to understand UX, and existing tests for render/bundle
  to see fake patterns:"
- **Attempt 2:** Re-dispatched with explicit "work efficiently — don't
  spend more than 5 minutes reading reference docs before starting to
  write code" guidance. Stalled at 600s; result fragment: "Now let me
  look at the routes I'll consume (render, bundle, upload) and existing
  templates."
- **Resolution:** Switched to inline. ~25 tool calls (Read template
  patterns, write route, write template, write tests, fix FileRef
  validation, fix assertion). Total ~10 min. Shipped as PR #76.

Same session, Phase D polish (test edits + runbook write) also stalled
once at 600s with partial work in the worktree (`src/config.py`,
`src/ui/upload_routes.py`, `tests/test_ui/test_upload_csv.py` already
modified by the subagent). Salvaged inline; finished the work + added
the runbook. Shipped as PR #75.

## Notes

- **The salvage path is the more important takeaway.** Even when a
  subagent stalls, the partial work may be ~80% correct. Diff and finish
  inline.
- This isn't a Claude-Code-bug to file. The watchdog is doing the right
  thing for stalled-for-real tasks (genuine crashes, infinite loops,
  network deadlocks). The cost is the false-positive on long-think UI
  tracks.
- The lesson is dispatch-ergonomic: prefer backend tracks for parallel
  dispatch (high streamed-output density); prefer inline for UI/template
  tracks (low streamed-output density).
- See also: `parallel-subagent-ui-from-contract-table-design-anemic` —
  a different UI-subagent failure where the agents complete cleanly but
  produce design-anemic HTML. That skill's fix (mockup-first inline
  build) compounds with this skill's fix (inline execution for UI).

## References

- the-handover-repo Session 16 handoff doc references the original incidents:
  Phase C (2 stalls before going inline → PR #76) and Phase D (1 stall,
  salvaged from partial worktree state → PR #75)
- Sister skill: `parallel-subagent-ui-from-contract-table-design-anemic`
