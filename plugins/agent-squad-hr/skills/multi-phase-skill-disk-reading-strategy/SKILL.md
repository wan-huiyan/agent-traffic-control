---
name: multi-phase-skill-disk-reading-strategy
description: |
  Fix silent subagent failures in late phases of multi-phase Claude Code skills.
  Use when: (1) a skill has 10+ phases and the last phase's subagent silently
  fails to launch, (2) Phase N produces output that Phase N+1 needs but the
  orchestrator's context is near capacity, (3) the orchestrator injects large
  data payloads (500+ lines) into subagent prompts and the subagent produces
  degraded or empty output, (4) a skill's final output step works in short
  reviews but fails in long ones. The fix: have late-pipeline subagents read
  already-written files from disk instead of receiving data via orchestrator
  context injection.
author: Claude Code
version: 1.0.0
date: 2026-04-15
---

# Multi-Phase Skill: Disk-Reading Strategy for Late-Pipeline Subagents

> **Sister skill:** [`multi-agent-skill-silent-phase-compression`](../multi-agent-skill-silent-phase-compression/SKILL.md) covers the **output-direction** symmetric problem (subagent outputs flooding back into orchestrator → silent compression of mandatory phases). Same fix family (file-based state passing), opposite direction. If a multi-agent skill is failing, read both — the bug is usually one or the other (sometimes both).

## Problem

In Claude Code skills with many phases (10+), late-pipeline subagents silently
fail to execute when the orchestrator's context window is near capacity. The
orchestrator tries to inject large amounts of structured data (earlier phase
outputs) into the subagent's prompt, but context exhaustion causes the launch
to either fail silently or produce a degraded prompt that the subagent can't
follow properly.

Symptoms:
- Earlier phases complete successfully but the final phase's output is missing
- No error reported — the orchestrator skips to the completion message
- When the user manually asks for the missing output, the orchestrator
  produces a generic version from memory rather than following the spec
- The failure is intermittent: works on short inputs, fails on long ones

## Context / Trigger Conditions

- A Claude Code skill runs 10+ sequential phases with subagents
- A late phase (e.g., Phase 15 of 16) needs data from earlier phases
- The orchestrator currently INJECTS that data into the subagent prompt
  (embedding 500+ lines of structured data or process history)
- The earlier phases already WROTE their output to disk (.md, .json, etc.)
- The failure appears as a silent skip — no error, just missing output

## Solution

### 1. Make late phases sequential, not parallel

If Phase N-1 and Phase N currently run in parallel, make them sequential.
Phase N runs AFTER N-1 so that N-1's output file exists on disk.

Latency impact is usually negligible — orchestrator-assembled phases
(no subagent) complete in seconds.

### 2. Have the subagent read from disk

Instead of:
```
# BAD: Orchestrator injects 700+ lines into subagent prompt
Agent({
  prompt: "Generate the report. Here is all the data:\n{massive_data_blob}"
})
```

Do:
```
# GOOD: Orchestrator tells subagent which files to read (~10 lines)
Agent({
  prompt: "Generate the report by reading these files:
  1. {absolute_path}/phase_1_output.md — structured data
  2. {absolute_path}/phase_2_output.md — detailed narratives
  3. {absolute_path}/references/spec.md — rendering spec
  Follow the spec exactly. Write the complete output file."
})
```

### 3. Resolve paths to absolute

The subagent has NO knowledge of:
- The skill's installation directory
- The user's output directory
- Custom filenames the user specified

The orchestrator MUST substitute all paths to absolute paths before
including them in the subagent prompt.

### 4. Add a verification gate

Before reporting completion, verify all expected output files exist:
```bash
ls -la output_file_1.md output_file_2.md output_file_3.html
```

If the late-phase file is missing:
1. Retry ONCE with the same disk-reading prompt (cheap — no re-assembly)
2. If still missing, report partial output + tell user the manual command

### 5. Add a manual recovery path

Document in the skill: if the user asks to regenerate the missing output,
launch the SAME subagent with the SAME disk-reading prompt. Do NOT generate
a generic version from the orchestrator's memory — it won't follow the spec.

## Verification

After applying this pattern:
1. Run the skill on a large input (one that previously caused the failure)
2. Verify ALL output files are present
3. Verify the late-phase output follows the full spec (not a degraded version)
4. Check that the orchestrator's launch prompt is <200 tokens

## Example

**Before (agent-review-panel v2.16.3):**
- Phase 15.3 HTML report ran in parallel with 15.2
- Orchestrator injected ~700 lines of structured data + process history
- Phase 15.3 silently failed in most runs
- Manual request produced a generic HTML page, not the spec-compliant dashboard

**After (agent-review-panel v2.16.4):**
- Phase 15 runs sequentially: 15.1 -> 15.2 -> 15.3
- Phase 15.3 agent reads 3 files from disk (~10 line prompt)
- Verification gate checks all 3 files exist before completion
- Manual recovery launches same agent with same disk-reading prompt
- Meta-test: ran the review panel on its own fix, 56KB spec-compliant HTML generated

## Notes

- This pattern applies to ANY multi-phase skill, not just review panels
- The key insight: subagents get fresh context windows — they can easily
  read 3 files totaling 300KB. The orchestrator can't inject that much.
- Parallel execution between the second-to-last and last phase saves
  almost nothing (usually seconds) but creates the context pressure bug
- The "generic output from memory" failure mode is particularly insidious
  because the output LOOKS correct but doesn't follow the spec
- Always use absolute paths — subagents don't inherit the orchestrator's
  working directory knowledge

## See Also

- **skill-creator** — when building new multi-phase skills, apply this pattern during design
- **skill-sync** — version bump checklist for when you update a skill after applying this fix

## References

- agent-review-panel PR #26: https://github.com/wan-huiyan/agent-review-panel/pull/26
- Failure evidence: a much earlier session run (2 of 3 files), S81 run (generic HTML on manual request)
