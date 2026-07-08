---
name: subagent-read-stale-worktree-needs-head-pin
description: |
  Read-only subagents (Explore / code-explorer / general-purpose dispatched to AUDIT or
  READ code, not write) silently return line numbers and "what exists" claims from the
  WRONG git worktree in a repo with many worktrees — confidently-wrong stale data, no
  error. Use when: (1) you dispatched 1+ read/audit subagents and their cited
  file:line numbers, function locations, or "X is/isn't present" claims DON'T match what
  you read directly in your pinned worktree; (2) `git worktree list` shows 2+ paths
  (especially a `.claude/worktrees/` fan-out); (3) a subagent reports an issue is
  "not implemented" / "missing" when you can see it on fresh main; (4) two parallel
  audit subagents disagree with each other or with origin/main. Fix: every read-subagent
  prompt must pin the ABSOLUTE worktree path AND require the agent to run
  `git -C <path> rev-parse HEAD` and confirm the expected SHA before reading. Distinct
  from subagent-bash-cd-wrong-worktree (write/commit to wrong branch), 
  worktree-outer-ls-mistaken-for-main-state (`ls` outside any worktree), and
  multi-worktree-file-url-stale-content (browser file:// bookmark).
author: Claude Code
version: 1.0.0
date: 2026-06-01
disable-model-invocation: true
---

# Read-subagent reads a stale worktree — pin the path AND verify HEAD

## Problem
In a repo with many git worktrees (e.g. a `.claude/worktrees/` fan-out of 20+ checkouts,
many on stale feature branches), a **read-only subagent** dispatched to audit/read code can
resolve the target files inside the *wrong* worktree and return **confidently-wrong** results:
line numbers from an old checkout, "function X is at line 1029" when on fresh main it's 1473,
or "cov_intel is NOT passed to the template" when it demonstrably IS. There is **no error** —
the agent reads real files and reports real (but stale) facts. This is worse than the bash-`cd`
worktree trap, which at least commits to a visibly-wrong branch; here the only signal is that
the cited lines don't match reality.

## Context / Trigger Conditions
- You fanned out 1+ `Explore` / `code-explorer` / general read subagents to audit issues,
  map a feature, or check "what already exists vs what's missing."
- A subagent's cited `file:line`, function location, or presence/absence claim **contradicts
  your own direct Read-tool read** of the same file in the worktree you're operating in.
- `git worktree list` shows 2+ working trees; the repo has a `.claude/worktrees/<name>/` style
  fan-out, or sibling clones of the same project exist on disk.
- Two parallel audit subagents disagree with each other, or with `git show origin/main:<path>`.
- A subagent claims an already-shipped feature is "not implemented" (it read a pre-feature branch).

## Solution
**Prevention (do this in every read-subagent dispatch):**
1. Put the **absolute worktree path** in the prompt and say "operate ONLY in this dir; use
   absolute paths under it."
2. Add a hard gate: *"Before reading anything, run `git -C <abs-path> rev-parse HEAD` and
   confirm it equals `<expected-sha>`. If it doesn't, stop and report the mismatch."*
3. For "what's on main" audits, tell the agent to read via `git -C <path> show origin/main:<file>`
   rather than the working tree, so a stale checked-out branch can't mislead it.

**Recovery (when you suspect a stale-read already happened):**
1. **Trust your own direct read over the subagent's.** If the subagent's line numbers don't
   match what you just Read, the subagent is stale — not you.
2. Re-verify the specific claim directly: `git -C <your-worktree> rev-parse HEAD`,
   `git show origin/main:<path>`, `gh pr view <N> --json state,mergedAt`, targeted grep.
3. Discard the stale audit's specifics (line numbers, "missing" claims); keep only conclusions
   you independently re-confirmed.

## Verification
- The subagent echoes the expected HEAD SHA at the top of its report (proves it read the right tree).
- Re-running the same audit with the pin produces line numbers that match your direct reads.
- The "missing feature" claim flips to "present at <correct line>" once read from the right tree.

## Example
S84 (the-causal-impact-repo, ~25 worktrees): 3 parallel `Explore` agents audited issues #178/#181/#191
against `origin/main`. Two returned stale line numbers (`features()` "at 1029", cov_intel "not
passed") from an old worktree — I'd directly Read it at line 1473 with cov_intel passed. Caught it
because the cited lines didn't match my read; re-verified directly (`gh pr view 231/232` both merged;
`prep.py` keys) and ignored the stale audits. The 3 **review** subagents dispatched afterward all
carried `git -C <path> rev-parse HEAD == <sha>` gates and were reliable. Net: pin + HEAD-verify every
read-subagent in a multi-worktree repo; distrust subagent line numbers that don't match your own.

## Notes
- The same pin protects *review* subagents (reviewing a diff/commit): pass the worktree path +
  the commit SHA, and have them confirm `git rev-parse HEAD` before `git show <sha>`.
- Background subagents can't write, but they CAN read the wrong tree — pinning matters even for
  read-only fan-outs.
- See also: `subagent-bash-cd-wrong-worktree` (write/commit to wrong branch),
  `worktree-outer-ls-mistaken-for-main-state` (`ls` from outside any worktree),
  `multi-worktree-file-url-stale-content` (browser `file://` bookmark),
  `flask-debug-cross-worktree-edit-stale` (server reload reads wrong worktree),
  `stale-backlog-triage-adversarial-verify` (verify "what's already shipped" against live main).
