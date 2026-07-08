---
name: pr-from-stale-branch-silently-reverts-newer-main-files
description: |
  Trap: opening/merging a PR from a branch that was created a while ago can
  SILENTLY DELETE (revert) files that landed on main AFTER your branch point —
  with NO merge conflict to warn you. Use when: (1) about to `gh pr create` or
  squash-merge from a long-lived / earlier-branched branch; (2) `git diff
  origin/main..HEAD --stat` shows DELETIONS of files you never touched; (3) a PR
  diff is unexpectedly large or removes another session's/teammate's work; (4)
  the repo has many parallel branches + a squash-merge flow (each squash makes
  older branches progressively staler). The fix is to merge origin/main INTO the
  branch first, then re-verify the diff shows only your additions. Distinct from
  merge-CONFLICT skills — this is the no-conflict, clean-merge silent-regression
  case. See also: pr-conflict-from-mid-flight-merges,
  large-redesign-parallel-branch-collision-audit, merge-conflict-generated-files.
author: Claude Code
version: 1.0.0
date: 2026-06-17
disable-model-invocation: true
---

# A PR from a stale branch can silently revert newer main files (no conflict)

## Problem
Your branch was cut from main at commit X. Since then, other PRs added files
B, C, D to main. Your branch never had B/C/D. When you open a PR (or merge),
git computes the diff as `origin/main..HEAD` — and because your branch *lacks*
B/C/D, the diff shows them as **DELETIONS**. Merging the PR removes B/C/D from
main, reverting work you never touched. **There is no merge conflict** (your
branch simply doesn't mention those files), so nothing warns you — the PR looks
"clean" and the deletions hide in the diff stat.

## Context / Trigger Conditions
- About to `gh pr create` / `gh pr merge --squash` from a branch that's been
  around for more than a session or two, or in a repo with many parallel branches.
- `git diff --stat origin/main..HEAD` lists files being **removed** that you have
  no memory of touching (e.g. someone else's analysis/handoff/docs from a sibling
  session that merged while you worked).
- The PR's deletion count is suspiciously high for the work you did.
- Squash-merge workflows make this WORSE over time: each squash rewrites main's
  history, so a branch that "was only a bit behind" reverts more with each sibling merge.

## Solution
1. **Before** creating/merging the PR, always sanity-check the full diff stat:
   ```sh
   git fetch origin main
   git diff --stat origin/main..HEAD
   ```
   Scan for `---` / deletion lines on files outside your scope.
2. If you see spurious deletions, **merge origin/main into your branch first**
   (do NOT just merge the PR):
   ```sh
   git merge origin/main --no-edit      # clean if your changes are file-disjoint
   ```
   This re-adds B/C/D to your branch so they're no longer "deleted" in the diff.
3. **Re-verify**: `git diff --stat origin/main..HEAD` should now show ONLY your
   own additions/edits. Then push + PR.
4. If the merge DOES conflict, you've crossed into merge-conflict territory →
   hand off to `pr-conflict-from-mid-flight-merges` /
   `merge-conflict-generated-files` (generated-file union playbooks).

## Verification
Post-merge-of-main, `git diff --stat origin/main..HEAD` lists only files you
intended to change (no foreign deletions). The PR's "files changed" on GitHub
matches your mental model of the work.

## Example (this repo, S258, 2026-06-17)
Branch `docs/s258-prompt-update` was cut before S257b's anomaly-alignment docs
merged to main. The first `git diff --stat origin/main..HEAD` showed 5 unrelated
files being **deleted** (−384/−93/−65/−40/−19 lines: the anomaly HTML, a content
snapshot, two S257b handoffs, a legend edit) alongside the intended S258 additions
— a clean merge would have reverted all of S257b's work. `git merge origin/main
--no-edit` was conflict-free (docs were disjoint) and the diff then showed only the
7 S258 files. PR opened safely.

## Notes
- The tell is **deletions in the diff stat**, not a conflict marker — conflict-only
  habits (rely on git to yell) miss this entirely.
- Same root cause as `large-redesign-parallel-branch-collision-audit` (branches
  drift from main), but that skill is a *pre-plan* collision audit across many
  branches; this is the *at-PR-time* per-branch check + the merge-main-in fix.
- `gh pr merge --delete-branch` may then fail with "main is already used by
  worktree at ..." when you run from a worktree — the merge still succeeded;
  delete the remote ref with `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`.
