---
name: opus-ratelimit-fanout-retry-on-sonnet-throttled-waves
description: |
  When a large Workflow/Agent fan-out (dozens of parallel subagents on Opus) mass-fails
  with "Server is temporarily limiting requests (not your usage limit)" / HTTP 429 — most
  agents dying, a few that finished before the burst surviving — recover by re-running the
  SAME fan-out on Sonnet and throttled into sequential waves (not one wide burst). Use when:
  (1) a Workflow returns far fewer results than dispatched and the failures all read
  "Rate limited" / 429 with "not your usage limit"; (2) you launched 20+ concurrent Opus
  subagents in one shot; (3) the task is well within Sonnet's range (triage, review,
  code-tracing, classification). Sonnet is a SEPARATE capacity pool, so it sidesteps the
  Opus-specific server throttle; the orchestrator/synthesis can stay on Opus.
author: Claude Code
version: 1.0.0
date: 2026-06-08
disable-model-invocation: true
---

# Opus rate-limit on a fan-out → retry on Sonnet, throttled into waves

## Problem
A wide parallel fan-out (Workflow `parallel()`/`pipeline()` or many concurrent `Agent`
calls) launched on **Opus** mass-fails with a server-side capacity throttle, not your
account quota. The whole fan-out collapses to a handful of results — only the agents that
happened to finish *before* the burst survive.

## Context / Trigger Conditions
- Failure string (one per dead agent): **`API Error: Server is temporarily limiting
  requests (not your usage limit) · Rate limited`** → HTTP **429**.
- The "(not your usage limit)" clause is the tell: this is **Anthropic-side Opus capacity
  throttling**, NOT your per-account rate limit. Waiting and retrying on Opus alone often
  re-hits it.
- You launched many subagents at once (one `parallel()` over 20–50 items, or a single
  message with dozens of `Agent` calls). The wider the simultaneous burst, the worse.
- Distinct from the empty-`StructuredOutput` loop (that's a *schema*-payload failure under
  the same storm — see the companion skill `workflow-schema-agents-empty-loop-under-ratelimit`).
  This skill is about the **mass-429 capacity** failure mode and the cheapest recovery.

## Solution
Two independent levers; apply both on the retry:

1. **Move the fan-out agents to Sonnet.** Set `model: 'sonnet'` on the `agent()` calls
   (Workflow) or `model: "sonnet"` on the `Agent` tool. Sonnet draws from a **separate
   capacity pool**, so it does not contend for the throttled Opus capacity. Keep the
   *orchestrator* and the final *synthesis/judge* on Opus — only the fan-out workers move.
   Triage / review / code-tracing / classification fan-outs are well within Sonnet's range.
2. **Throttle the burst into sequential waves.** Instead of one N-wide `parallel()`, loop
   in chunks of ~8 (parallel *within* a wave, barrier *between* waves). This spaces the
   request bursts so you never present 50 simultaneous requests again:

   ```js
   const CHUNK = 8
   const results = []
   for (let i = 0; i < ITEMS.length; i += CHUNK) {
     const slice = ITEMS.slice(i, i + CHUNK)
     log(`wave ${i/CHUNK+1}: ${slice.join(', ')}`)
     const r = await parallel(slice.map((it) => () =>
       agent(prompt(it), { model: 'sonnet', schema: SCHEMA })))
     results.push(...r)
   }
   ```

It trades wall-clock (waves run serially) for reliability. Re-running is cheap because a
Workflow with the same script + args returns cached results for the agents that already
succeeded — but a fresh run on Sonnet+waves is usually simpler than resuming.

## Verification
- The retry completes with **0 missing** (`ITEMS.filter(n => !results.some(r => r.number===n))`
  is empty), where the Opus burst returned only a few.
- Spot-check that the Sonnet outputs meet the bar — for triage/review they typically do; if
  a few items need deeper reasoning, re-run *just those* on Opus after the storm passes.

## Example (~50-issue triage fan-out)
First run: ~50 investigator agents in one `pipeline()` burst, all Opus → **nearly all died
with "Rate limited · 429 · not your usage limit"**; only a handful (that finished before the
storm) returned. Re-ran the identical fan-out with `model: 'sonnet'` in **waves of 8** →
**all ~50 completed, 0 missing**, and the adversarial-verify pass still flipped the couple of
dismissals it should. Final synthesis/cut-line stayed on Opus. Net cost of the
diagnosis+retry: minutes.

## Notes
- Don't just "wait and retry on Opus" — the capacity window can persist and you re-burn the
  burst. The model-swap is what actually dodges it.
- `parallel()` swallows a thrown thunk to `null` (never rejects), so a partial storm shows
  up as `null` holes, not an exception — always `.filter(Boolean)` and compare count to
  dispatched to detect it.
- If the agents are forced to emit a large required `StructuredOutput` schema, the storm
  also triggers the empty-args validation loop — drop to free-text return for the heaviest
  agents (see the companion skill `workflow-schema-agents-empty-loop-under-ratelimit`).
- Pair with the journal-recovery path (extract `{"type":"result"}` lines from
  `subagents/workflows/<run>/journal.jsonl`) when you'd rather salvage the survivors than
  re-run the whole fan-out.

## References
- Workflow tool docs — per-`agent()` model override (quality-patterns).
- Companion skill `workflow-schema-agents-empty-loop-under-ratelimit` (the schema-loop
  variant of the same storm).
