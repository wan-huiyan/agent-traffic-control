---
name: parallel-session-superseded-validated-fix-verify-live-prod-state-first
description: |
  A parallel Claude/work session shipped a DIFFERENT (often better) fix to the SAME live-prod
  artifact for the SAME issue while you were mid-build — so your fully-implemented, validated,
  reviewed fix is now REDUNDANT and must NOT be deployed over theirs. Use when: (1) you picked up a
  "next session ships the scoped fix X" handoff/prompt and invested a full implementation, (2) the
  target is a SHARED prod artifact (Dataform .sqlx, a serving feature table, a deploy config, a model
  pointer) editable by multiple sessions, (3) the related issue is "still OPEN" but a sibling issue
  mysteriously CLOSED, (4) the user/another session says "stand down — already fixed live", (5) you're
  about to deploy and haven't re-checked the live state since you started. Core trap: a handoff/issue
  reflects the world WHEN IT WAS WRITTEN; "issue open" ≠ "unfixed"; a parallel session can ship between
  your build and your deploy. Verify the LIVE DEPLOYED state of the target artifact at task START and
  again IMMEDIATELY before any deploy — a 1-query live-state check can save a whole redundant build,
  and prevents clobbering a live fix.
author: Claude Code
version: 1.0.0
date: 2026-06-22
disable-model-invocation: true
---

# A parallel session superseded your validated fix — verify LIVE prod state before building/deploying

## Problem
You took a "next session ships the scoped fix" handoff, did everything right — diagnosed, designed,
panel-reviewed, implemented, validated end-to-end — and then discovered a **parallel session already
shipped a DIFFERENT fix for the SAME issue to the SAME live-prod artifact**, mid-flight. Your work is
redundant, and worse: deploying it would **clobber the live fix** (two mechanisms on one file). The
handoff was accurate when written but the world moved.

## Context / Trigger Conditions
- A multi-session / multi-worktree repo where >1 session can edit the same prod artifact.
- A handoff or prompt that says "NEXT SESSION ships fix X" (X already scoped) — you executed it faithfully.
- Target is a **shared prod artifact**: a Dataform `.sqlx` on the deployed branch, a serving feature
  table, a Cloud Run/deploy config, a `latest_good_model` pointer.
- The driving issue is **still OPEN**, but a **sibling issue CLOSED** unexpectedly (the early signal).
- You're about to deploy and your last look at the live artifact was at task start (stale).
- The user interjects "stand down — it's already fixed live / a parallel session shipped it."

## Solution
1. **At task START, verify the LIVE DEPLOYED state of the target artifact — not just the issue/handoff text.**
   The handoff reflects when it was written. Read the deployed file / compile the live branch / read the
   live config BEFORE investing in a full build. One cheap probe (e.g. compile the live Dataform release
   config and grep the compiled target for the markers your fix would add/remove) tells you if someone
   already changed it.
2. **Treat "issue still OPEN" as NOT proof it's unfixed**, and chase WHY any sibling issue CLOSED. A
   closed sibling (here #1242) is often "fixed by a PR that also resolves your issue, pending close."
   `gh pr list --search "<file or issue>"` / `gh issue view <sibling>` for the closing PR.
3. **Re-verify the live state IMMEDIATELY before any deploy** to a shared prod artifact. A parallel
   session can ship between your build and your deploy. NEVER blind-deploy over a shared prod file.
4. **If superseded:** STAND DOWN. Do not deploy over the live fix (an atomic revert+swap is the ONLY
   safe path, and only if your approach is *strictly* better on a dimension theirs lacks). Then:
   - Preserve your analysis/diagnosis (it usually still informs follow-ups) — push the branch as a record.
   - Reconcile threads: comment the supersession on the open issue; file any residual systemic findings
     your diagnosis surfaced that the live fix did NOT cover.
   - Clean up isolated infra you created for validation (dev workspaces, scratch tables you don't need).

## Verification
- The live artifact's content/SHA reflects the OTHER fix, not yours (grep the compiled/deployed source
  for your fix's unique markers → absent).
- Confirm your work never reached prod (isolated dev-workspace compile / local branch only) so "stand
  down" is genuinely a no-op on prod, not a rollback.

## Example (the client term-enrollment, #1212, 2026-06-22)
Prompt: "ship the REAL #1212 citizenship-flicker fix (carry-forward, scoped in #1270)." Built it fully:
serving-only carry-forward, panel-reviewed (5-lens plan + 3-lens diff, all-opus), validated 131/131
correct, Dataform workspace compile 0 errors. **A parallel session had shipped a DIFFERENT fix ~30 min
in** — the full identity key-set reconstruction (#1271, `alien_status_resolved` + `IN UNNEST`) — merged
+ live on Dataform main (`346da39f`), verified. Carry-forward was redundant. The **early signal missed**:
sibling #1242 was already CLOSED at task start (I noted it but didn't chase the closing PR). Recovery:
verified live main had the other fix (grep compiled target: 0 carry-forward markers), confirmed my work
was workspace-only (never touched main), deleted the dev workspace, stood down, filed the residual
systemic finding (#1291), commented the supersession on #1212. One marginal edge of the abandoned fix was
noted in the follow-up (defense-in-depth), but NOT atomic-swapped in.

## Notes
- Distinct from siblings: `deploy-from-stale-worktree-silent-rollback` (deploying YOUR OWN stale local
  build context), `pr-conflict-from-mid-flight-merges` (git PR text conflict from other merges),
  `concurrent-session-curating-shared-global-dir` (shared `~/.claude/*` dirs). This one is **live-prod +
  issue-level supersession of a complete build**, where the cost is a wasted full implementation, not a
  merge conflict.
- The asymmetric cost makes the START-OF-TASK live-state check worth it even when it "probably" hasn't
  changed: minutes of probing vs hours of redundant build + the deploy-clobber risk.
- Both sessions independently de-scoping the same way (e.g. both reached "serving-only, no retrain") is
  reassuring on the DIAGNOSIS but does not make your IMPLEMENTATION non-redundant — only one ships.
- See also: `flicker-fix-verify-oscillation-and-prefix-baseline` (the verification discipline that was
  still correct), `feature-rebuild-arms-unattended-scheduled-retrain-promote`.
