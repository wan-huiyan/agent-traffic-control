---
name: handoff-prompt-stale-user-hint-newer-state
description: |
  Gate execution of a structured runbook/handoff/plan prompt behind an AskUserQuestion
  when the user explicitly hints that newer state (issues filed, PRs merged, probes
  shipped) has landed since the prompt was authored. Use when: (1) the user invokes
  "execute docs/handoffs/session_NNN_*.md" or "run this plan" or "implement this ADR"
  AND adds an inline aside like "but please be aware of #A, #B, #C" / "watch out
  for PR #N" / "FYI #issue landed since this was written"; (2) before executing, a
  scan reveals issues/PRs in the user's hint list were filed/merged AFTER the prompt's
  authoring timestamp; (3) the newer artifacts could materially change what the prompt
  should do (e.g., a P1 issue surfacing that the prompt's design decision needs
  revisiting, a probe correction flipping a verdict, a sibling PR's merge claiming an
  ID the prompt reserved). Default behavior to avoid: execute the prompt verbatim and
  paper over the divergence in a post-merge comment. Correct behavior: pause, fetch
  current state of each hinted artifact, then AskUserQuestion with concrete options
  for how scope should shift. Generalises the probe-block case captured by
  `feedback_brief_says_probe_dont_close_on_permission_block` (project-feedback) — same
  root principle (don't barrel forward when brief's premise has changed) but the
  trigger is "user hint about newer issues" rather than "sandbox blocks probe".
author: Claude Code
version: 1.0.0
date: 2026-05-10
disable-model-invocation: true
---

# Stale handoff prompt: user hints newer state landed since authoring

## Problem

You're asked to execute a structured prompt (handoff, runbook, plan, ADR, implementation
spec) that was authored at time `T0`. The user's invocation includes a casual aside —
"but please be aware of #X, #Y, #Z" / "watch out for PR #N" / "FYI X landed". Between
`T0` and execution, those artifacts were filed or merged and they materially change
what the prompt should do.

The default behavior is to execute the prompt verbatim and surface any divergence in a
post-execution comment. That's wrong: the user is telling you the premise has changed
and is asking you to re-evaluate scope **before** executing.

Failure mode: you ship the prompt's original plan, the newer state's implications get
documented retroactively, and the user has to file a follow-up PR (or worse — a fix-up
PR after auto-deploy) to reconcile.

## Trigger conditions

Activate this skill when **all** of these hold:

1. The user's instruction has two parts: (a) "execute / run / implement [structured
   prompt file or runbook]" AND (b) an aside flagging GitHub issues, PRs, commits, or
   state-of-the-world that should be "aware of" / "factor in" / "watch out for" /
   "FYI." Phrasings include:

   - "execute X, but be aware of #N"
   - "run the prompt — watch out for PR #M"
   - "implement this, factoring in #issue"
   - "but FYI #N was filed since"
   - "remember #X is open now"

2. Before any code changes, a quick check (`gh issue view`, `gh pr view`, `git log`)
   shows at least one hinted artifact was filed/merged AFTER the prompt's authoring
   timestamp (`Date:` line, frontmatter, git mtime, or first commit on the prompt's
   feature branch).

3. The artifact's content is non-trivial — a P1+ issue, a merged PR, a probe verdict,
   a panel review request_changes. (If the hint is just "remember the deploy schedule
   is Friday" — that's calendar context, not a scope change. Don't fire this skill.)

## Solution

**Step 1: Pause before the first scope-affecting action.**

Don't run `git checkout` to the prompt's working branch; don't start the rebase; don't
spawn implementation subagents. The cost of pausing for 1 AskUserQuestion turn is far
lower than the cost of a partial-execution rollback.

**Step 2: Fetch the current state of each hinted artifact.**

For each `#N` the user named:

```sh
# For each #N — issue or PR doesn't matter; gh detects the type:
gh issue view N --repo <org>/<repo> --json number,title,state,labels,body
gh pr view N    --repo <org>/<repo> --json number,title,state,mergeable,merged
```

Pull the body. Look for:
- Severity labels (`p0`, `p1`, `bug`, `ml-correctness`, `security`)
- "Closes / Refs / Supersedes" cross-refs to the prompt's target issue
- Verdicts that contradict the prompt's plan (e.g., "Probe X verified — leakage-adjacent")
- Path-forward menus or amendments

**Step 3: Map each artifact to its implication for the prompt.**

For each artifact, write down in ≤1 sentence:
- "If this is true, the prompt's [step N / design choice / hero number] should change to …"
- "If false / no longer applicable, the prompt is still correct."

**Step 4: Issue a single AskUserQuestion gating execution scope.**

Present the user with concrete options. Bias toward giving them a default that respects
the artifact's implications:

```
question: "The planned PR uses inputs that a newer issue flags as invalid.
           How should I proceed with the merge?"
options:
  - "Merge as-is + caveat"        (execute verbatim, surface divergence post-merge)
  - "Edit basis before merge"     (re-scope per the newer issue; merge after)
  - "Hold PR, design pivot"       (don't merge today; resolve newer issue first)
  - "Narrative-only edit + merge" (smallest delta to address the newer state)
```

Each option's `description` field should explicitly cite what changes and what stays
the same.

**Step 5: Execute the user's choice.**

If "execute verbatim": run the original prompt; flag the divergence in PR description
and follow-up comments.

If "edit / pivot / hold": adjust scope. Update your task list with the new plan before
touching code. The prompt becomes a partial input, not a script.

**Step 6: Record the gate in the post-merge artifacts.**

PR description: include a "Updated after #X amendment" subsection. Commit message:
"...post-#N narrowing." Memory file: capture the user-hint-triggered-rescope as a
session-level annotation so future similar prompts get the gate routine in advance.

## Verification

You did this right if:

1. The first AskUserQuestion fires BEFORE any `git checkout` to the impl branch or
   any code-modifying tool call.
2. The PR description (or commit body) cites the newer issue(s) by number in the
   "what changed" section.
3. The post-merge issue closure comments link back to the prompt's authoring track
   AND the newer-state artifacts that drove the amendment.
4. The user's aside ("be aware of #X") shows up as a load-bearing decision point in
   the session log, not a footnote.

## Synthetic example: a handoff predates an input-quality correction

A handoff asks the next session to merge a dashboard update. The user adds that
an input-quality issue and a correction PR have appeared since the handoff.

The current issue identifies invalid inputs in the original metric definition.
The correction establishes a replacement input set: it includes a valid input
from the old set plus a newly admitted input. It is a replacement basis, not
merely a subset of the old one. The dashboard's calculation and explanation must
agree about that distinction.

The agent reads the current issue and correction, then presents the concrete
scope choices: retain the old definition with an explicit limitation, adopt the
replacement definition, or hold the change pending a product decision. The user
chooses the replacement. The agent updates both calculation and explanation,
validates their agreement, and records which newer evidence changed the plan.

This example uses no real project, issue identifiers, measurements, or deployment
history. Its lesson is the scope decision triggered by newer evidence.

## Notes

- **Adjacent to but distinct from**
  `feedback_brief_says_probe_dont_close_on_permission_block` (project-feedback): the
  same don't-barrel-forward principle, but the trigger here is a user's verbal hint
  about newer state, not a sandbox block on a required probe.
- **Adjacent to but distinct from** `subagent-pre-existing-misattribution` (global):
  catches when a subagent claims a task is its own work when it was actually done in
  a prior session. That skill protects against attribution drift; this skill protects
  against scope drift.
- **Adjacent to but distinct from** `procedure-doc-reads-pending-but-already-shipped`
  (global): the NO-HINT variant — same "a procedure doc's tense lies about its execution
  state" family, but there the user gives no `#N` hint and you must self-discover during a
  "confirm/verify/execute" request that a parallel session already ran the doc. This skill
  fires on an explicit user hint + gates on AskUserQuestion; that one fires on a live-state
  probe you initiate yourself.
- **Adjacent to but distinct from** `auto-mode-handoff-deploy-permission-still-denied`
  (global): also about handoff execution, but the failure mode is "Bash permission
  classifier denies despite AskUserQuestion answer" rather than "prompt's premise has
  changed."
- **AskUserQuestion is non-negotiable here.** Without the gate, the model's default
  is to execute the prompt verbatim — exactly what the user's hint was trying to
  prevent. Don't rationalize that you "understand the implications" without surfacing
  them; the user surfaced them deliberately so the decision is theirs.
- **When the hint is ambiguous** ("be aware of the model retrain schedule"), ask the
  user what they mean before assuming it's a scope change. Some hints are operational
  context (deploy windows, on-call) not scope-amending.
- **When the hint cites artifacts NOT yet in your conversation context** (e.g., an
  internal Slack thread): ask the user to summarize or paste the load-bearing content.
  Don't infer from the issue number alone.

## References

- `feedback_brief_says_probe_dont_close_on_permission_block` — related principle
  for a required probe blocked by the execution environment.
- Project incident links and private memory paths are intentionally omitted.
