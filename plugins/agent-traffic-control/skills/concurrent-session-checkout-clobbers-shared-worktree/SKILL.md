---
name: concurrent-session-checkout-clobbers-shared-worktree
description: |
  A second Claude Code session (or agent/person) sharing the same working
  directory runs `git checkout`/`git switch`, flipping the branch for the whole
  working tree underneath your session and clobbering your uncommitted work.
  Use when: (1) a file you just edited has silently reverted — often with a
  "file was modified, either by the user or by a linter" system reminder,
  (2) `git branch --show-current` shows a branch you didn't switch to,
  (3) `git reflog` shows a `checkout: moving from X to Y` you never ran,
  (4) unfamiliar files/changes appear in `git status`. Covers detecting the
  collision and recovering via an isolated git worktree.
author: Claude Code
version: 1.0.0
date: 2026-05-21
---

# Concurrent session's `git checkout` clobbers your shared working directory

## Problem

Two Claude Code sessions (or any two agents/people) operate in the **same**
working directory on the same clone. `git checkout` / `git switch` changes
`HEAD` for the *entire working tree* — it is not per-session. When session B
switches branches, session A's tree changes underneath it:

- Uncommitted edits to tracked files may be carried across, reverted, or left
  in a confusing half-state.
- Untracked files (new files you created) stay on disk but risk being swept
  into session B's next `git add -A`.
- Edits get silently lost — e.g. a config field you added disappears.

It is invisible until something breaks: a function you wrote is "gone", a test
errors on a symbol you defined, or a harness emits *"file was modified, either
by the user or by a linter"* for a file you didn't expect to change.

## Context / Trigger Conditions

- A file you edited reverted to an older version with no action from you.
- `git branch --show-current` is not the branch you were working on.
- `git status` lists changes or untracked files you don't recognize.
- **Decisive:** `git reflog` shows `checkout: moving from <yours> to <other>`
  that you never performed.

## Solution

Do **not** keep fighting inside the shared directory — you will collide again.
Isolate into a git worktree.

1. **Confirm the collision** — `git reflog -5` reveals the foreign checkout.
   `git log <your-branch> --oneline` confirms your committed work is still safe
   on its branch (commits survive a checkout; only uncommitted work is at risk).
2. **Create a worktree for your existing branch** (not a new branch):
   ```bash
   git worktree add /path/outside/repo/my-worktree <your-branch>
   ```
   Place it *outside* the repo (a sibling dir) to avoid `.gitignore` edits that
   would themselves collide.
3. **Migrate uncommitted work into the worktree:**
   - Copy untracked files (`cp` the new files you created).
   - Re-apply tracked-file edits in the worktree (apply them fresh; the
     worktree has the clean branch tip).
   - Re-apply any edit that was *clobbered* — recover it from conversation
     context.
4. **Clean your pollution out of the shared dir** so the other session gets it
   back as expected: `git checkout <files-you-modified>` and `rm` your untracked
   files (you copied them already).
5. **Switch your session into the worktree** and continue there.
6. **Commit early and often** to your feature branch — committed work cannot be
   clobbered by a foreign checkout.

## Verification

- `git worktree list` shows your isolated worktree on your branch.
- Your work (files + edits) is present in the worktree; tests pass there.
- The shared directory's `git status` shows only the *other* session's files.

## Example

Session A is on `team-1-iap-deploy` with an uncommitted `app/config.py` edit.
The parallel session runs `git checkout team-1-web-app` in the shared `repo/`.
Session A's `app/config.py` edit vanishes; `git reflog` shows
`checkout: moving from team-1-iap-deploy to team-1-web-app`. Recovery:
`git worktree add ../iap-worktree team-1-iap-deploy`, copy the untracked new
files in, re-apply the lost `config.py` edit, `git checkout app/main.py` + `rm`
the strays in `repo/`, then `EnterWorktree` and carry on — committing each task.

## Notes

- Prevention: when starting isolated feature work, create a worktree *first*
  (the `using-git-worktrees` skill). Shared-directory work is only safe for a
  single session.
- A native `EnterWorktree` tool can enter an already-created worktree by `path`.
- Nothing is permanently lost even if the other session commits your strays —
  file *content* survives; you can recover it. But it is messy; isolate early.

## References

- `using-git-worktrees` — create an isolated workspace up front.
- `git reflog` is the source of truth for "who switched the branch."
