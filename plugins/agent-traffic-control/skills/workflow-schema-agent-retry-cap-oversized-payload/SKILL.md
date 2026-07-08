---
name: workflow-schema-agent-retry-cap-oversized-payload
description: |
  A dynamic Workflow (the Workflow tool / multi-agent orchestration) parallel()/pipeline() agent that
  DID all its work returns null and the run reports "StructuredOutput retry cap (5) exceeded — 5 failed
  calls with no valid output" — NOT because the agent found nothing or was rate-limited, but because its
  result OBJECT was too large / malformed to serialize in one StructuredOutput call (a big nested array
  of findings, long SQL/quotes per row), often compounded by a stray closing-tag / truncation that
  corrupts the JSON. Use when: (1) a workflow fan-out comes back N-of-M and a failure line names the
  StructuredOutput retry cap (distinct from the rate-limit "empty-args 50-90×" mode); (2) an agent's
  transcript shows FULL (non-empty) StructuredOutput tool_use inputs that keep failing validation; (3)
  the agent's own last text says "payload too large / getting truncated" or "stray </parameter> corrupted
  the JSON". Covers RECOVERING the near-complete work from the agent-*.jsonl transcript's failed
  StructuredOutput attempts (the data is there — do NOT re-run), and PREVENTING it with compact schemas,
  capped array sizes, and terse field values. See also: workflow-schema-agents-empty-loop-under-ratelimit
  (empty-args/rate-limit sibling), workflow-standalone-schema-agent-crash-and-args-string,
  cjk-structured-llm-output-truncates-json-needs-2x-tokens.
author: Claude Code
version: 1.0.0
date: 2026-07-07
disable-model-invocation: true
---

# Workflow schema agent hits the retry cap on an oversized output — recover its work from the transcript

## Problem
A `Workflow` `parallel()`/`pipeline()` agent forced to emit a `StructuredOutput` schema **completes its
actual work** (e.g. runs all its BQ probes, gathers every finding) but then **cannot emit the result**
because the object is **too large or malformed to serialize in one call**. It burns the retry cap
(default 5), the run logs `StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid
output`, and that agent resolves to `null` inside `parallel()`. The run "completes" N-of-M and the null
looks like "this agent found nothing" — but the work is real and **recoverable**.

This is a *distinct* failure from its siblings: the args are **full, not empty** (rules out the
rate-limit empty-loop), the agent is **inside** `parallel()` so it doesn't crash the whole run (rules
out the terminal-agent throw), and it's an oversized *payload*, not CJK token density.

## Context / Trigger Conditions
- Workflow `<failures>` / result reports: `parallel[i] failed: agent({schema}): StructuredOutput retry
  cap (5) exceeded — 5 failed calls with no valid output`.
- The offending agent has a **large/nested return schema** — an array of findings where each row carries
  long strings (SQL, verbatim quotes, per-row notes). The more the agent found, the bigger the payload.
- The agent's transcript (`.../subagents/**/agent-<id>.jsonl`) shows repeated `StructuredOutput`
  tool_use calls whose `input` is **populated** (not `{}`), and the agent's own late text says things
  like "payload is too large and getting truncated" or "stray `</parameter>`/`]` corrupted the JSON".
- `journal.jsonl` has **no** `{"type":"result"}` line for this agent (it never emitted) — so the
  journal-recovery path that works for *completed* agents does not apply here; you must read the agent's
  own transcript.

## Solution
**1. Recover the work from the failed StructuredOutput attempts (don't re-run — the BQ/analysis already
happened and re-running costs tokens and may drift).**
- Find the agent by fingerprint (grep its transcript for a distinctive keyword) among
  `<transcriptDir>/subagents/**/agent-*.jsonl`. `.meta.json` often lacks the label — identify by content.
- Read the **last** `StructuredOutput` (or `*output*`) tool_use `input` in that JSONL — the final retry
  usually carries the most complete data. Also scan the agent's last assistant `text` blocks for a
  plain-language summary it wrote before/after the failed emits.

```python
import json
f = ".../subagents/workflows/wf_<runid>/agent-<id>.jsonl"
last_struct, texts = None, []
for line in open(f):
    try: d = json.loads(line)
    except: continue
    msg = d.get("message") or d
    for b in (msg.get("content") or []) if isinstance(msg, dict) else []:
        if not isinstance(b, dict): continue
        if b.get("type") == "tool_use" and ("output" in b.get("name","").lower()
                                             or "structured" in b.get("name","").lower()):
            last_struct = b.get("input")          # the data it tried to submit
        if b.get("type") == "text":
            texts.append(b["text"])               # its own summary/reasoning
print(json.dumps(last_struct, indent=1)[:4000])
print("\n".join(texts[-2:]))
```
- The recovered `input` is usually near-complete (a truncated tail array is common) — enough to use
  directly. Only re-run if the *specific* missing tail matters.

**2. Prevent it on the next dispatch — shrink the payload, don't raise the cap.**
- **Compact the schema:** short field names, `additionalProperties:false`, and prune optional fields.
  Cut long free-text per row (a one-line `note` instead of paragraphs; a `sql` field only if truly needed).
- **Cap array sizes** the agent can return (top-N findings, not all), and say so in the prompt.
- **Split** a heavy agent into per-item pipeline stages so each emits a small object, instead of one
  agent returning a giant array.
- For genuinely large qualitative output, consider a **schema-less (free-text) agent** and parse its
  text, or have it **write the big artifact to a file** and return only the path + a summary.

## Verification
- The recovered `input`/text contains the real findings (numbers, SQL, verdicts) — confirm against what
  the agent was asked to produce.
- On the re-dispatched/compact version, the run comes back full (M-of-M) with no retry-cap failure line,
  and the returned objects are small.

## Example
In one run: a 4-agent verification workflow returned 3-of-4; the failure line was `parallel[1]
failed: agent({schema}): StructuredOutput retry cap (5) exceeded`. The failed agent (a per-item
spot-check) had actually run every BQ probe; its transcript's last `StructuredOutput` input held the
full summary + most of a large `findings` array, and its own text said "payload is too large… stray
`</parameter> after the ] corrupted the JSON." Recovered the findings from disk (no re-run). The **next
two** workflows used **compact schemas + capped arrays** and both returned clean full sets.

## Notes
- Distinguish from `workflow-schema-agents-empty-loop-under-ratelimit`: there the args are **empty** and
  the cause is a server-side rate-limit storm; recovery is `journal.jsonl` for *completed* agents +
  re-dispatch as free-text. Here the args are **full/oversized**; recovery is the agent's own transcript.
- Distinguish from `workflow-standalone-schema-agent-crash-and-args-string`: a standalone (non-parallel)
  schema agent that fails **throws and kills the whole run**; inside `parallel()` it degrades to `null`.
- `resumeFromRunId` replays *completed* agents from cache but re-runs the failed one — only useful if you
  first shrank its schema (otherwise it fails the same way).

## References
- Workflow tool docs — the journal.jsonl / agent-*.jsonl transcript layout and `parallel()` null-on-error semantics.
- See also: `workflow-schema-agents-empty-loop-under-ratelimit`, `workflow-standalone-schema-agent-crash-and-args-string`, `cjk-structured-llm-output-truncates-json-needs-2x-tokens`, `claude-code-workflow-subagent-tokens-nested-undercount` (same nested transcript layout).
