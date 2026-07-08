---
name: workflow-schema-agents-empty-loop-under-ratelimit
description: |
  A dynamic Workflow (the Workflow tool / multi-agent orchestration) returns FEWER results than it
  dispatched, and one or more parallel() agents "failed" — because during a transient server-side
  rate-limit storm the affected agents called StructuredOutput 50-90× each with EMPTY args (0 fields),
  failed schema validation every time, then died on a terminal API error. Use when: (1) a workflow
  fan-out comes back with N-of-M results and logs show "API Error: Server is temporarily limiting
  requests (not your usage limit) · Rate limited"; (2) agent-*.jsonl shows many StructuredOutput
  tool_use calls whose input has zero keys; (3) heavy code-tracing agents fail to emit a big required
  schema while a light agent on the same run succeeded. Covers recovering the COMPLETED agents from
  journal.jsonl (don't re-run them), re-dispatching the failed ones as FREE-TEXT (no schema), and
  prevention (concise field values, anti-empty-call directive, free-text for heavy-context agents,
  a watchdog that greps the empty-SO signature).
author: Claude Code
version: 1.0.0
date: 2026-06-08
disable-model-invocation: true
---

# Workflow: schema agents empty-loop StructuredOutput under a rate-limit storm

## Problem
A Workflow `parallel()`/`pipeline()` fan-out where each agent is forced to emit a large
`StructuredOutput` schema can come back **degraded** (N-of-M results, not a clean crash) when a
**transient server-side rate-limit** hits mid-run. The affected agents repeatedly call
`StructuredOutput` with **empty arguments** (0 fields → schema-validation fail → retry → empty
again), burn 50-90 attempts, then die on a terminal API error and resolve to `null` inside
`parallel()`. The run "completes" but silently drops those agents' work — easy to mistake for "the
analysis found nothing" rather than "the emission failed."

This is **distinct** from `workflow-standalone-schema-agent-crash-and-args-string` (a *standalone*
non-parallel schema agent that cleanly never calls StructuredOutput and crashes the *whole* run).
Here the agents are inside `parallel()` (so the run survives), the failure is **rate-limit-induced
empty payloads**, and it correlates with **large accumulated context** (deep code-tracing agents
fail; a light agent that finished just before the storm succeeded).

## Context / Trigger Conditions
- A Workflow returns fewer results than agents dispatched; `<failures>` / `logs` show
  `API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited`.
- Inspecting the run dir confirms the signature: an agent jsonl with **many** `StructuredOutput`
  tool_use calls, **all with empty input**, and a final `isApiErrorMessage` assistant turn.
- The heavy agents (lots of greps/reads → large context) fail; lighter agents succeed.

## Solution

### 1. Diagnose — confirm the empty-SO signature (don't assume "found nothing")
Run dir: `<session>/subagents/workflows/<wf_runid>/`. Count empty StructuredOutput calls per agent:
```bash
WF=~/.claude/projects/<encoded-dir>/<session-uuid>/subagents/workflows/<wf_runid>
for f in "$WF"/agent-*.jsonl; do
  python3 -c "
import json,os
recs=[json.loads(l) for l in open('$f') if l.strip()]
so=sum(1 for o in recs for c in (o.get('message',{}).get('content') or []) if isinstance(c,dict) and c.get('type')=='tool_use' and c.get('name')=='StructuredOutput')
ne=sum(1 for o in recs for c in (o.get('message',{}).get('content') or []) if isinstance(c,dict) and c.get('type')=='tool_use' and c.get('name')=='StructuredOutput' and len((c.get('input') or {}).keys())>0)
print(os.path.basename('$f')[:20],'SO=',so,'nonempty=',ne)"
done
# SO>=15 & nonempty==0  ==>  this agent empty-looped (stuck), not 'found nothing'.
```

### 2. Recover the COMPLETED agents from the journal — do NOT re-run them
`journal.jsonl` in the run dir has one `{"type":"result", "result": {...}}` line per agent that
finished. Extract those objects directly (axiom: session history IS retrievable). You only need to
re-run the agents that have NO result line.
```bash
python3 -c "
import json
for l in open('$WF/journal.jsonl'):
    o=json.loads(l)
    if o.get('type')=='result':
        json.dump(o['result'], open('/tmp/recovered_<id>.json','w'), indent=2)"
```

### 3. Re-dispatch the failed agents as FREE-TEXT (no schema)
The empty-SO loop is an *emission* failure, worst for big-schema + large-context agents. Re-run the
failed ones as plain `Agent` calls (or workflow agents) that return **labelled markdown** instead of
a forced `StructuredOutput`, then parse the text yourself. Free-text final messages do **not** have
the empty-tool-input failure mode. (Verified 2026-06-08: two heavy triage agents that empty-looped
90×/14× under the storm both succeeded immediately as free-text once re-dispatched.)
Feed the recovered results + the fresh free-text results into the next stage (e.g. a synthesis/judge)
via `args` or inline.

### 4. Prevent / mitigate (so a transient API condition doesn't degrade the run)
- **Keep schema field VALUES concise** — terse file:line + 1-4 sentence verdicts, not essays. Smaller
  tool-call payloads are far less prone to the empty-emit loop.
- **Add an explicit directive**: "Do ALL investigation first, then make exactly ONE StructuredOutput
  call with ALL required fields populated; NEVER call it with empty/partial args."
- **For agents that accumulate large context (deep code tracing): prefer free-text return over a big
  forced schema** from the start.
- **Run a background watchdog** that greps the run dir for `SO>=15 & nonempty==0` and exits early so
  you can intervene in minutes instead of waiting for terminal failure.

## Verification
After recovery + free-text re-dispatch, you have M-of-M results (recovered + fresh) and the synthesis
stage runs on the full set — not the degraded N-of-M. Confirm no agent jsonl still shows the
empty-SO signature.

## Notes
- The storm is **transient** ("not your usage limit"): a plain re-dispatch after it passes usually
  succeeds even with the schema — but free-text is the robust fix for the heavy agents regardless.
- This complements `resumeFromRunId` (cached-completed-agent re-launch): use resume when you want to
  re-run with the SAME script after editing; use journal-recovery + free-text when you want to change
  the *emission strategy* for the failed agents specifically.
- See also: `workflow-standalone-schema-agent-crash-and-args-string` (standalone-agent crash + args-string),
  `workflow-parallel-fanout-omits-sequential-phases`, `claude-code-workflow-subagent-tokens-nested-undercount`.
- **Sibling failure mode — full args, not empty:** if the retry-cap message fires but the agent's
  StructuredOutput inputs are POPULATED (a large/nested findings array, not `{}`) and there's no
  rate-limit, the cause is an **oversized/malformed payload**, not this empty-loop — recover from the
  agent's own transcript and shrink the schema. See `workflow-schema-agent-retry-cap-oversized-payload`.
