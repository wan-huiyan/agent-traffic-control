---
name: git-stash-pop-pulls-unrelated-stash
description: |
  Diagnose and avoid `git stash pop` pulling in a stale stash from a different
  branch when the preceding `git stash` was a no-op. Use when: (1) `git stash`
  reports "No local changes to save" but you `git stash pop` anyway as a
  reflex; (2) `git stash pop` surfaces files you don't recognize, often with
  "both modified" merge conflicts in files unrelated to your current work;
  (3) `git status` after a stash pop shows changes in files from other features
  / other branches; (4) `git stash list` reveals stash entries from sibling
  worktrees or older branches. The stash stack is GLOBAL across branches and
  worktrees — it's LIFO and branch-agnostic. Pairing `git stash` / `git stash
  pop` defensively (e.g., before `git checkout -- file`) only works when the
  initial stash actually saved something; otherwise the pop reaches deeper
  into history. Save under user-wide skills.
author: Claude Code
version: 1.0.0
date: 2026-05-15
disable-model-invocation: true
---

# `git stash pop` pulls an unrelated stash when preceding `git stash` was a no-op

## Problem

You defensively wrap a risky operation with `git stash` / ... / `git stash pop`
to preserve in-progress work. The working tree is clean, so `git stash` prints
**"No local changes to save"** and exits 0. Later, `git stash pop` pulls in
modifications from a *different* branch's stash entry — sometimes months old,
sometimes from another worktree, often producing merge conflicts in files you
never touched in this session.

## Context / Trigger Conditions

You'll see one or more of:

- `git stash` immediately echoed **"No local changes to save"**
- `git stash pop` runs without error and announces something like
  `On branch <X>: WIP on <other-branch>: <sha> <commit-msg-from-elsewhere>`
- `git status` afterward shows:
  - Modified or unmerged files you didn't touch
  - `both modified: <path>` for paths from unrelated features
  - Filenames matching files on entirely different branches
- `git stash list` shows entries like `stash@{0}: WIP on feature/sca-polish: ...`
  that reference branches you're not on

## Root Cause

The stash stack is a **global, branch-agnostic, LIFO data structure**, shared
across every worktree of the repo. `git stash pop` always pops `stash@{0}` —
it doesn't care which branch the stash was created on. When `git stash` is a
no-op (clean tree), nothing is pushed onto the stack, so a subsequent
`git stash pop` reaches whatever was on top *before* this session — potentially
unrelated work from another branch, sometimes from months ago.

## Solution

### Prevent

1. **Don't pair `git stash` / `git stash pop` reflexively.** Check the output
   of `git stash` first:
   ```bash
   git stash push -m "session-N defensive snapshot" 2>&1 | tee /tmp/stash-msg
   grep -q "Saved working directory" /tmp/stash-msg && DID_STASH=1 || DID_STASH=0
   # ... do risky thing ...
   [ "$DID_STASH" = "1" ] && git stash pop
   ```
2. **Always use `-m` with `git stash push`** so your stash entries are
   identifiable in `git stash list`.
3. **Audit before popping** when you're unsure:
   ```bash
   git stash list | head -5    # show top of stack
   git stash show -p stash@{0} # full diff
   ```
4. **Use a worktree-scoped stash alternative.** Instead of `git stash`, commit
   to a throwaway branch:
   ```bash
   git checkout -b /tmp/snapshot-$$
   git add -A && git commit -m "snapshot"
   git checkout -
   # later: git cherry-pick /tmp/snapshot-$$ ; git branch -D /tmp/snapshot-$$
   ```

### Recover

If you've already popped an unrelated stash:

1. Identify what changed:
   ```bash
   git status -s
   ```
2. **Unstage everything** (the stash pop may have staged things):
   ```bash
   git reset HEAD
   ```
3. **Discard the popped changes** in files you did NOT intend to touch:
   ```bash
   git checkout -- <file1> <file2> ...
   ```
   For unmerged paths, the same `git checkout -- <file>` works after `git reset`.
4. **Verify clean tree:**
   ```bash
   git status -s         # should be empty
   git stash list        # confirm the stale stash is still there if you need it
   ```
5. **Decide on the stale stash:** if it's from another branch, leave it on the
   stack (someone else may want it). If you're confident it's dead, drop it:
   ```bash
   git stash drop stash@{0}
   ```

## Verification

After preventive measures:
- `git stash` should either successfully save (print
  `Saved working directory and index state ...`) or print "No local changes to
  save" — your conditional pop respects which case occurred.

After recovery:
- `git status -s` returns empty
- Subsequent test runs / builds reflect only your intended changes
- `git log --oneline -5` shows no unexpected new commits

## Example

This session ran into the bug while verifying a base-branch behavior:

```bash
$ git stash                              # working tree was already clean
No local changes to save

$ git checkout origin/release-uk -- tests/test_app_flow.py
$ pytest tests/test_app_flow.py -q

$ git checkout HEAD -- tests/test_app_flow.py
$ git stash pop                          # ← reached into unrelated history
On branch feat/report-bundler
Changes to be committed:
        modified:   deliverables/future_roadmap.html
Unmerged paths:
        both modified:   docs/plans/future_sessions_plan.md
        both modified:   tests/test_ci_core.py
        both modified:   webapp/ci_core.py
        both modified:   webapp/cloud_run_task.py

$ git stash list
stash@{0}: WIP on feature/sca-polish: 498faed feat: P2 Specification Curve ...  # ← old, unrelated branch
```

Recovery:
```bash
$ git reset HEAD
$ git checkout -- deliverables/future_roadmap.html docs/plans/future_sessions_plan.md \
                  tests/test_ci_core.py webapp/ci_core.py webapp/cloud_run_task.py \
                  webapp/cloud_runner.py webapp/research_utils.py webapp/templates/sca_results.html
$ git status -s
# (clean)
```

## Notes

- This applies to **all worktrees of a repo** — the stash stack is shared.
  Don't assume "my worktree" or "my branch" scopes the stash.
- `git stash pop` is **partially destructive on conflicts** — if you can't
  cleanly resolve, prefer `git stash drop stash@{0}` to discard the pop and
  recover from your last commit.
- A safer mental model: **`git stash` and `git stash pop` are not a matched
  pair**. They operate on a stack that exists outside the session.
- If you're inside a long-lived repo with stale stashes, periodically run
  `git stash list` and clean up entries you're done with.
- Related skills: `git-recover-lost-branch` (if a stash drop loses important
  work), `git-worktree` (alternative to stash for inter-worktree state).

## References

- [Git Tools — Stashing and Cleaning (Pro Git)](https://git-scm.com/book/en/v2/Git-Tools-Stashing-and-Cleaning)
- [`git-stash(1)` man page](https://git-scm.com/docs/git-stash) — "The latest stash you created is stored in `refs/stash`; older stashes are found in the reflog of this reference."
