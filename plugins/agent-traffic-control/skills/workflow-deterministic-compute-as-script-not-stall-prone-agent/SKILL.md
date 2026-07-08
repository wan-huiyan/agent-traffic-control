---
name: workflow-deterministic-compute-as-script-not-stall-prone-agent
description: |
  Use when a Workflow-tool (or background Agent) subagent doing heavy multi-step compute STALLS
  mid-stream and loses work. Trigger conditions: (1) a workflow agent fails with "API Error: Response
  stalled mid-stream. The response above may be incomplete" and returns null; (2) a subagent runs many
  bq/python/tool calls in one long turn and dies before writing/committing; (3) the agent must emit a
  LARGE structured return (big arrays/objects) and stalls while producing it; (4) recurring stalls on
  long single-agent turns. Root insight: agent turns stall on long compute + large returns; DETERMINISTIC
  computation should run as a direct script the orchestrator executes, with agents reserved for judgment.
  Covers file-first idempotent durability, design-injection to avoid rediscovery, and compact returns.
disable-model-invocation: true
author: Claude Code
version: 1.0.0
date: 2026-06-29
---

# Move deterministic compute to a direct script; don't lose it to a stalling agent turn

## Problem
A Workflow `agent()` (or `Agent(run_in_background:true)`) doing a big job — schema probes + build N
tables + prove + enumerate + a large structured return — dies with **"API Error: Response stalled
mid-stream. The response above may be incomplete"** and returns `null`. The longer the turn and the
larger the structured output, the higher the stall rate. Naively re-running the same monolithic agent
just burns the budget rediscovering the same things and stalls again.

Observed on one heavy job: **3 agent turns stalled; 0 direct-Python runs stalled.** The heavy work that
*needed* an agent (judgment: a binarization/thresholding design decision) was done once; everything deterministic
(counting, closed-form stats) was far more reliable as a plain script.

## Context / Trigger Conditions
- Workflow/subagent stalls mid-stream, returns null, after meaningful tool use (work may be partially
  durable).
- A single agent prompt asks for build + prove + enumerate + model + write + a big structured return.
- The return schema is large (full per-cell tables, hundreds of rows) embedded in the agent's output.

## Solution
1. **Triage what's durable first.** A stall kills the *structured return*, not necessarily the side
   effects. Check the DB (were `CREATE OR REPLACE` tables written?), disk (files?), git (commits?), and
   the agent's transcript (`subagents/.../agent-*.jsonl`) for what it figured out before dying. Often
   the hardest *design* work completed and only materialization was lost.
2. **Make every agent file-first + idempotent.** `CREATE OR REPLACE` tables (durable in the warehouse),
   write SQL/CSV to disk (durable even uncommitted). Then a stall leaves resumable artifacts, and
   `Workflow({scriptPath, resumeFromRunId})` re-runs only the failed call (completed calls are cached;
   idempotent rebuilds are safe).
3. **Inject resolved design to kill rediscovery.** If a stalled run already derived facts (schema,
   value distributions, a tricky cohort definition), paste them into the re-run prompt as "RESOLVED —
   do not rediscover." Rediscovery is usually where the token budget (and the turn length) went.
4. **Split long turns into short ones.** Two short sequential agents (build → enumerate) stall far less
   than one long agent doing both.
5. **Move DETERMINISTIC compute OUT of agents.** Counting, pre-screens, closed-form statistics, BH-FDR,
   labeling — none needs agent judgment. Write a plain Python script and run it via Bash yourself. It
   cannot stall on a model stream, it's exactly reproducible, and it keeps the orchestrator's hand on
   the consistent "hero" artifact. **Reserve agents only for judgment** (design, narration, review).
6. **Return COMPACT.** Write heavy data to CSV/JSON files; have the agent return only a small summary
   (counts + a short worklist). Large embedded returns are a primary stall trigger.

### Specific instance worth remembering
A within-stratum 2×2 interaction (the saturated-logit `a:b` term) is **exact in closed form (Woolf)**
from the 8 cell counts when every cell has ≥ N in both outcome classes:
`logOR = [ln(ev11/ne11)−ln(ev10/ne10)] − [ln(ev01/ne01)−ln(ev00/ne00)]`, `SE=√Σ(1/ev+1/ne)`,
`p = erfc(|logOR/SE|/√2)`. No `statsmodels`, no re-pulling the panel, no agent — just pandas + `math`
over the counts you already have. (A fixed min-class floor guarantees the finiteness this relies on.)

## Verification
- The deterministic script runs once to completion, no stall, reproducible output.
- After a stall, the warehouse tables + on-disk files from completed steps are present; resume re-runs
  only the failed step.

## Notes
- Workflow agents *can* run live BQ/Bash in the background (unlike `Agent(run_in_background:true)`,
  which is denied write/exec) — so the choice isn't "agent or nothing," it's "agent for judgment,
  script for determinism."
- This refines the file-first / successor-handoff patterns in `overnight-insight-discovery`: those
  manage *context*; this manages *stall-resistance + reliability of deterministic work*.
- Don't over-fan-out to honour a "use agents" request when the real shape is build-once + deterministic
  compute. Honour the *intent* (get it done correctly) over the literal word; fan out where judgment is
  genuinely parallel, script the arithmetic.
