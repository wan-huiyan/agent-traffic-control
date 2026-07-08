---
name: parallel-subagent-fanout-rate-limit-recover-from-disk
description: |
  Large parallel subagent fan-outs (dispatching many Agent/Task subagents at once
  to each extract/transform a chunk and WRITE a file) hit a server-side rate
  limit, AND the agent RETURN STATUS lies about what got produced. Use when:
  (1) dispatching more than ~5-6 concurrent subagents and seeing "Server is
  temporarily limiting requests (not your usage limit) · Rate limited";
  (2) deciding which "failed" subagents to re-run after a throttled batch;
  (3) a graphify-style chunked extraction (28 chunks → 28 subagents) where some
  agents error on their final return. Two facts: concurrency >~5 trips
  server-side throttling (distinct from your usage limit), and a throttled/errored
  agent usually ALREADY WROTE its output file before the error hit on its final
  summary — so check disk for the expected files, not the agent return, when
  deciding retries. Fix: batch at ≤4-5 concurrent; re-dispatch only chunks whose
  files are actually missing/empty. v1.1.0 adds the USER-ACCOUNT session-limit
  variant ("You've hit your session limit · resets HH:MM" — not the server-side
  throttle): same recovery rule applies (agents usually wrote their files before
  the final-summary call died), with one addition — a retry launched INSIDE the
  limit window dies instantly at ~0 tokens, so re-dispatch only AFTER the stated
  reset time.
author: Claude Code
version: 1.1.0
date: 2026-06-25
disable-model-invocation: true
---

# Parallel subagent fan-out: rate limit, and recover from disk not return status

## Problem
You dispatch a large fan-out of subagents in one message — each reads a chunk,
does work, and **writes an output file** — to maximize parallelism. Two things go
wrong:
1. Above a low concurrency ceiling the API returns **"Server is temporarily
   limiting requests (not your usage limit) · Rate limited"** for most of the
   batch.
2. When you go to retry the "failed" ones, the agents' **return status is
   misleading**: many agents that returned a rate-limit/terminal error had
   *already completed their work and written their output file* — the error hit
   on the final summary turn, after the side effect.

Re-running based on the agent return status re-does work that's already on disk
(wasted tokens) or, worse, you trust "20 failed" and redo all 20 when 14 actually
succeeded.

## Context / Trigger Conditions
- Dispatching **>~5-6 concurrent** `general-purpose` Agent/Task subagents (or a
  Workflow fan-out) in a single message.
- Result array peppered with `API Error: Server is temporarily limiting requests
  (not your usage limit) · Rate limited`. Some agents show `tool_uses: 14-24,
  subagent_tokens: 0` — they did work but the final return failed.
- Each subagent's contract is to **write a file** (chunk JSON, transformed doc,
  etc.) at a known path.

## Root cause
1. **Concurrency, not quota.** Too many simultaneous subagent inference streams
   trip a *server-side* throttle that is explicitly "not your usage limit." A
   smaller batch (≤4-5) stays under it.
2. **Side effect precedes the failing turn.** A subagent does Read→…→Write (the
   deliverable) and *then* emits a final summary turn. The rate-limit/terminal
   error lands on that last turn, so the file is already on disk even though the
   agent "errored."

## Solution
- **Batch at ≤4-5 concurrent** for large fan-outs. Dispatch batch, wait, dispatch
  next. (One validation batch first to prove the prompt, then scale in small
  batches.)
- **To decide retries, CHECK DISK, not the agent return.** Enumerate the expected
  output paths; re-dispatch only the chunks whose files are **missing or empty**:
  ```bash
  for n in $(seq -w 1 N); do
    f="out/.chunk_${n}.json"
    [ -f "$f" ] && [ -s "$f" ] || echo "MISSING $n"
  done
  ```
- Make each subagent write to a **deterministic absolute path** (so this disk
  check is possible) and validate the file parses before counting it done.
- If the run is paused/resumed across sessions, commit the produced files (or
  rely on a persistent working dir) so the expensive partial work survives.

## Verification
After a "rate limited" batch, `ls`/parse the output dir: a meaningful fraction of
the "failed" agents' files are present and valid. Only the truly-missing set needs
a re-run. The smaller-batch re-runs complete without throttling.

## Example
graphify doc extraction: chunked 552 docs into 28 chunks → dispatched all 22
remaining subagents at once → 20 returned "Rate limited." Disk check showed 20/28
chunk files present (the throttle hit on final returns *after* writes). Re-ran
only the genuinely-missing chunks in **batches of 4-6** — clean, no throttling.
A 6-concurrent batch later partially throttled too, but again the throttled
agents had written their files; the disk check (not the return) drove the precise
re-run set.

## Notes
- This pairs with the deadlock trap: the in-session subagent path
  (`claude-cli-backend-deadlocks-nested-in-active-session`) avoids nested
  `claude -p`, but its concurrency still hits this server-side ceiling.
- "Throttled agents still wrote their file" is the load-bearing, non-obvious bit —
  treat the agent's textual return as advisory and the filesystem as ground truth
  for any subagent whose job is to produce a file.

## Variant: user-account session limit (v1.1.0, verified 2026-07-01)

Trigger text differs: `You've hit your session limit · resets 9:50pm (<tz>)` — this is the
ACCOUNT usage cap, not the server-side "temporarily limiting requests" throttle. Observed on a
6-agent debate round: every agent returned the limit message as its "result", yet **5/6 had
already written their full state files to disk** (10-20KB each) — only the final chat summary was
lost. The 6th had died earlier on a connection error before writing.

Recovery rules (same core + two additions):
1. Check the expected output paths on disk; re-dispatch ONLY missing/stub files (<500 bytes).
2. **Do not retry inside the limit window** — a re-dispatch before the reset dies at launch
   (~0 tokens, sub-second). Wait for the stated reset time, then re-dispatch.
3. For WRITE-scoped agents (fixers editing files), also `git diff --stat` their target file:
   a mid-stream stall usually happens in the READ phase (file untouched → clean re-dispatch),
   but verify rather than assume. Sister skill: parallel-impl-agent-dies-mid-stream-verify-working-tree.
