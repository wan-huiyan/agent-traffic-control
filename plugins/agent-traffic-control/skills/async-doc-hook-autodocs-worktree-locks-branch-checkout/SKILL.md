---
name: async-doc-hook-autodocs-worktree-locks-branch-checkout
description: |
  Fix for `git checkout <branch>` failing with `fatal: '<branch>' is already used by
  worktree at '.../autodocs-<name>'` (or a subagent reviewing a PR reports a path like
  `.../worktrees/autodocs-<topic>/...`). Use when: (1) right after a commit whose hook
  printed `[post-commit] Python files changed — running doc update in background...`, a
  later branch switch is blocked; (2) you can't check out the branch you just committed to
  because "another worktree" holds it; (3) a review/subagent cites a file path under an
  `autodocs-*` worktree you never created. Root cause: the async post-commit doc-update hook
  spawns its OWN git worktree on the active branch (git forbids a branch being checked out in
  two worktrees). Fix: `git worktree remove --force` the autodocs worktree (after confirming
  it committed nothing), then checkout proceeds. Distinct from the index.lock variant — see
  worktree-index-corrupt-async-post-commit-hook.
author: Claude Code
version: 1.0.0
date: 2026-06-01
disable-model-invocation: true
---

# Async doc-update hook spawns an autodocs worktree that locks your branch

## Problem
This repo's async post-commit hook ("running doc update in background") materializes its own
git worktree (e.g. `.claude/worktrees/autodocs-<topic>`) and checks out the branch you just
committed to. Git only allows a branch to be checked out in ONE worktree, so a subsequent
`git checkout <that-branch>` in your main worktree fails:

```
fatal: '<branch>' is already used by worktree at
'/…/.claude/worktrees/autodocs-<topic>'
```

It also surfaces indirectly: a code-review subagent you pointed at the PR may report file
paths under `.../worktrees/autodocs-<topic>/...` — that's the hook's worktree, not yours.

## Context / Trigger conditions
- You committed on a feature branch; the commit output included
  `[post-commit] Python files changed — running doc update in background...`.
- You then try to switch back to that branch (e.g. to apply a review fix) and git refuses.
- A subagent's review cites an `autodocs-*` path.
- Sibling symptom (different fix): the same hook also leaves `index.lock` behind →
  `Unable to create '.git/worktrees/<name>/index.lock'` → that's `rm -f` (see See also).

## Solution
1. **Confirm the hook committed nothing to your branch** (it usually only reads/regenerates
   docs and leaves them uncommitted):
   ```bash
   git rev-parse <branch>            # local tip
   git rev-parse origin/<branch>     # remote tip (if pushed)
   git log --oneline <your-sha>..<branch>   # empty = no extra commits
   ```
   If local == remote == your commit and the range is empty, the autodocs worktree added
   nothing — safe to remove.
2. **Force-remove the autodocs worktree** to free the branch:
   ```bash
   git worktree remove --force .claude/worktrees/autodocs-<topic>
   git worktree list | grep autodocs   # should be gone
   ```
3. **Now checkout works.** Clear any leftover lock first if present:
   ```bash
   rm -f .git/worktrees/<your-worktree>/index.lock
   git checkout <branch>
   ```

## Verification
- `git worktree list` no longer shows the `autodocs-*` entry.
- `git checkout <branch>` succeeds; `git rev-parse --short HEAD` == your commit.

## Example (S227)
Committed P1 (`23f36f6d`) on `s227-auc-floor-recalibration`, switched to a sibling branch to
build P2, then needed to return to apply a reviewer's DRY fix. `git checkout
s227-auc-floor-recalibration` →
`fatal: '…' is already used by worktree at '…/autodocs-s227-recalib'`. The P1 review subagent
had also been reporting `…/worktrees/autodocs-s227-recalib/…` paths. Confirmed local ==
origin == `23f36f6d` (hook committed nothing), `git worktree remove --force
.claude/worktrees/autodocs-s227-recalib`, then checkout succeeded.

## Notes
- The autodocs worktree is hook scratch — force-removing it is safe once you've confirmed it
  holds no unique commits. If it DID commit (rare), cherry-pick first.
- Don't `git branch -D` the branch to "unstick" it — that destroys your work; remove the
  worktree instead.
- Same underlying async hook as the `index.lock` failure, but a different symptom and fix.

## References
- See also: `worktree-index-corrupt-async-post-commit-hook` (index.lock variant of the same
  hook), `git-rebase-stalls-async-post-commit-hook`, `git-amend-hits-async-post-commit-hook-commit`,
  `concurrent-session-checkout-clobbers-shared-worktree`, `gh-pr-merge-worktree-checkout-trap`.
