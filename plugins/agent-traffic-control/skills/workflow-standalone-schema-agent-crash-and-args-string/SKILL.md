---
name: workflow-standalone-schema-agent-crash-and-args-string
description: |
  Two failure modes that crash an entire dynamic Workflow (the Workflow tool / multi-agent
  orchestration scripts) and discard all completed agents' work. Use when: (1) a workflow fails
  with "Error: agent({schema}): subagent completed without calling StructuredOutput (after 2
  in-conversation nudges)" — caused by a STANDALONE/terminal `await agent(prompt, {schema})` that
  is NOT inside parallel()/pipeline(), so the throw propagates and fails the whole run even though
  the other agents succeeded; (2) a workflow fails immediately with "TypeError: undefined is not an
  object (evaluating 'P.candidates.map')" or args being a string — caused by the `args` global
  arriving as a JSON STRING in the script, not a parsed object. Covers guarding standalone schema
  agents (try/catch, parallel wrapper, or schema-less), defensive JSON.parse of args, and recovering
  a crashed run cheaply via resumeFromRunId (completed agents return cached).
author: Claude Code
version: 1.2.0
date: 2026-06-06
disable-model-invocation: true
---

# Workflow: a standalone schema agent crashes the whole run; and args arrives as a string

## Problem
A dynamic Workflow (the `Workflow` tool's JS orchestration script) can run dozens of expensive
subagents and then **lose the entire run to a single late failure** — discarding all the completed
agents' work — because of two non-obvious script-level fragilities. Both cost a failed launch each;
the second can throw away a near-complete, six-figure-token run on one agent's hiccup.

## Context / Trigger Conditions
- **Mode A — terminal schema agent.** The run fails at the very end with:
  `Error: agent({schema}): subagent completed without calling StructuredOutput (after 2 in-conversation nudges)`
  Symptom: many agents ran (high `agent_count` / `subagent_tokens`), but `status: failed` and the
  workflow returned nothing. The culprit is almost always a **standalone** `const x = await agent(prompt, {schema})`
  (e.g. a final "critic"/"synthesis" step) that is NOT wrapped in `parallel()` or `pipeline()`.
- **Mode B — args is a string.** The run fails in `~10ms` at the first line touching `args`, with
  `TypeError: undefined is not an object (evaluating 'P.candidates.map')`, **`X.map is not a function`**
  (e.g. `SESSIONS.map is not a function` when `const SESSIONS = args`), or any `args.<field>` access.
  The `args` you passed as a JSON object/array reached the script as a **JSON string**, so `args.map`/`args.foo` is invalid.
  **Best fix when the work-list is fixed/known at author time: skip `args` entirely — embed the list as a literal**
  (`const SESSIONS = [ {...}, ... ]`) in the script body. (Confirmed 2026-06-06: a 22-element array passed inline as
  `args` arrived as a string → `SESSIONS.map is not a function`; embedding the literal fixed it on relaunch — 0 agents
  had run, so a clean re-launch lost nothing.) Otherwise parse defensively: `const a = typeof args === 'string' ? JSON.parse(args) : args`.

## Solution

### Why Mode A happens
`agent(prompt, {schema})` is contractually required to return a schema-valid object, so it **throws**
if the subagent never calls `StructuredOutput`. Inside `parallel(thunks)` / `pipeline(...)` a thrown
thunk is caught and resolves to `null` (the run survives). But a **bare `await agent(...)`** propagates
the throw to the top level and fails the whole workflow — including all the agents that already finished.

Guard every standalone schema-bearing agent. Any of:
```js
// Option 1 — schema-less (most robust for a single synthesis/critic step; you read the prose)
let critic
try { critic = await agent(prompt, { label: 'critic', phase: 'Critic' }) }  // no schema -> returns text, can't fail this way
catch (e) { critic = 'CRITIC_FAILED: ' + String(e) }

// Option 2 — keep the schema but make it non-fatal
const [critic] = await parallel([() => agent(prompt, { schema: CRITIC_SCHEMA })])  // failure -> null, run survives

// Option 3 — explicit guard, keep schema
let critic = null
try { critic = await agent(prompt, { schema: CRITIC_SCHEMA }) } catch (e) { critic = { error: String(e) } }
```
Rule of thumb: **fan-out phases (parallel/pipeline) are already null-tolerant; standalone/terminal
agent() calls are not — guard them.** A late critic should never be able to discard an expensive
upstream fan-out.

### Recover a crashed run WITHOUT re-running everything
You do not have to redo the completed agents. Edit the persisted script file (the launch result prints
its `Script file:` path) to add the guard, then **resume**:
```
Workflow({ scriptPath: "<that path>", resumeFromRunId: "<the failed run's Run ID>", args: <same args> })
```
Completed agents with unchanged `(prompt, opts)` return **cached instantly**; only the edited call
(e.g. the now-guarded critic) re-runs. Pass byte-identical `args` so the cached agents' prompts hash-match.

### Recover WITHOUT even resuming — read the completed results from journal.jsonl
If the ONLY thing that failed was a late synthesis/critic agent and you just want the upstream
fan-out's results (e.g. to synthesize them yourself in the orchestrator), you don't need resume at
all — the completed agents' **schema-validated results are already persisted** in the run's
`journal.jsonl`. The launch result prints a `Transcript dir:` (…/subagents/workflows/<runId>/);
`journal.jsonl` there has one line per agent lifecycle event: `{type:"started",…}` then
`{type:"result", agentId, result:<the validated object>}`. Extract the `result` payloads directly:
```sh
# each successful schema agent emits a {"type":"result", "result": <object>} line
cat "<transcript-dir>/journal.jsonl" | python3 -c '
import json,sys
for line in sys.stdin:
    o=json.loads(line)
    if o.get("type")=="result": print(json.dumps(o["result"]))
'
```
A failed terminal agent shows only a `started` event (no `result`) — that is exactly the one that
threw. So `N parallel agents succeeded, 1 synthesis failed` ⇒ `journal.jsonl` has N `result` lines you
can use immediately. This is cheaper than `resumeFromRunId` when you don't actually need the synthesis
re-run — just pull the N findings and synthesize inline. (Verified 2026-06-05: a 4-reviewer plan-review
whose 5th synthesis agent hit the StructuredOutput error — all 4 reviewers' findings were intact in
`journal.jsonl`, recovered + synthesized by hand, zero re-run.)

### Mode B — parse args defensively
Make the script tolerate `args` arriving as a string:
```js
const P = (typeof args === 'string') ? JSON.parse(args) : args
```
Put this as the FIRST line that consumes `args`. (Passing a large object via the `args` parameter can
reach the sandboxed script JSON-encoded rather than as a live object; the defensive parse is cheap and
removes the dependency on how the harness marshals it.)

## Verification
- Mode A: after guarding, the run reaches its `return {...}` and `status: completed`; the guarded
  agent's value is either its result or your fallback sentinel — not a crash.
- Mode B: the script gets past the first `args.<field>` access; `P` is an object with the expected keys.
- Resume: the relaunch's `agent_count` shows the cached agents (fast/instant) and only the changed
  agent does real work.

## Example
A 17-agent verification workflow (13 parallel classifiers + 3 adversarial + 1 critic) ran ~18 min and
~1M tokens, then failed with the StructuredOutput error — the final `const critic = await agent(prompt,
{schema: CRITIC_SCHEMA})` threw because that one agent never emitted structured output. The 16 parallel
agents had succeeded but their work was discarded. Fix: made the critic schema-less + try/catch, then
`Workflow({scriptPath, resumeFromRunId, args})` — the 16 returned cached, only the critic re-ran (~1 min),
and the full `{classified, adversarial, critic}` returned. (A separate first launch had already failed
Mode-B with `P.candidates.map` undefined → fixed with the `typeof args === 'string' ? JSON.parse` guard.)

## Notes
- These are robustness gotchas of the dynamic-Workflow scripting model, not of any one project.
- Prefer designing so the EXPENSIVE work is in null-tolerant `parallel()`/`pipeline()` phases and any
  single standalone aggregator/critic is guarded — that ordering means a terminal failure costs one
  agent, never the whole fan-out.
- **For review/critic/synthesis patterns, the most robust design is to skip the terminal schema agent
  entirely:** have the fan-out `return` the raw per-agent results (the orchestrator script `return`s the
  `parallel()` array) and do the dedup/merge/verdict yourself in the main loop. You almost always have
  the context to synthesize N structured findings, and it removes the single most common crash surface.
  (Verified 2026-06-05: the retry of a failed plan-review used exactly this shape — `return reviews` from
  the parallel phase, synthesize in the orchestrator — and completed cleanly.)
- See also: `claude-code-workflow-subagent-tokens-nested-undercount` (a different Workflow gotcha —
  token accounting in nested workflows).

## References
- Workflow tool contract: `agent(prompt, {schema})` returns the validated object and retries on
  mismatch; `parallel()`/`pipeline()` catch per-thunk throws and resolve to `null`; resume via
  `resumeFromRunId` returns cached results for unchanged `(prompt, opts)`.
