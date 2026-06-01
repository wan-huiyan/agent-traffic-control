---
name: git-pull-after-squash-merge
description: |
  Fix "untracked working tree files would be overwritten by merge" errors when
  pulling after a squash merge. Use when: (1) `git pull` fails listing files that
  should already be on main, (2) you just squash-merged a PR and can't pull on
  another branch, (3) files from a merged branch appear as "untracked" blocking
  checkout or pull. The root cause is that squash merge creates new commits — the
  original branch files exist on main but your local copy has them as untracked
  leftovers from the old branch. ALSO triggers on `git checkout main` from a
  long-stale branch when untracked local files shadow files that became tracked
  on main since the branch diverged. **Before removing the blocking files, diff
  each against `git show origin/main:<path>` — content, not just existence —
  because a differing untracked copy holds unique local content that blind
  `rm` / `git clean -fd` / `reset --hard` will silently destroy.**
author: Claude Code
version: 1.1.0
date: 2026-05-29
---

# Fix git pull After Squash Merge

## Problem

After a PR is squash-merged to main, switching branches or pulling fails with:

```
error: The following untracked working tree files would be overwritten by merge:
    data/results/experiment_1.json
    data/results/experiment_2.json
    docs/findings/analysis.html
Please move or remove them before you merge.
```

These files ARE on main (from the squash merge) but git sees them as untracked locally because squash merge creates a new commit hash — the original branch commits never appear in main's history.

## Context / Trigger Conditions

This happens when:
- A branch created new files (not just modified existing ones)
- The branch was **squash-merged** (not regular merge) to main
- You're on a different local branch that also has those files (from cherry-picks, worktree remnants, or the original branch)
- `git pull` or `git checkout main` refuses to proceed

Common scenarios:
- Working on branch B while branch A (which created new files) gets squash-merged
- Checking out main after a parallel session merged files you also have locally
- Multiple Claude Code sessions creating overlapping experiment result files

## Solution

> **⚠️ Safety first — diff CONTENT, not just existence, before removing.** An
> untracked file that *exists* on main is not necessarily *identical* to your
> local copy. A long-stale branch's local copy often has unique edits (a 1-line
> SHA reference, a draft note). Blindly `rm`-ing / `git clean -fd` / `reset
> --hard` destroys that content silently. The default instinct (and Options 2-4
> below) skip this check — don't.

**Option 1: Diff each blocking file against main, back up differers, then remove**

```bash
# For each blocking file: compare LOCAL untracked copy vs origin/main's version
f=path/to/blocking/file
if git diff --quiet --no-index <(git show origin/main:"$f" 2>/dev/null) "$f" 2>/dev/null; then
  echo "IDENTICAL to origin/main — safe to rm"
  rm -f "$f"
else
  echo "DIFFERS — back up the local copy before removing (it has unique content)"
  mkdir -p /tmp/untracked-backup/"$(dirname "$f")"
  cp "$f" /tmp/untracked-backup/"$f"
  git diff --no-index <(git show origin/main:"$f" 2>/dev/null) "$f"  # eyeball what's unique
  rm -f "$f"   # only after backing up
fi
git checkout main && git pull   # or: git merge --ff-only origin/main
```

**Option 2: Bulk remove all blocking files (when there are many)**

⚠️ Only safe once you've confirmed they're all content-identical to main (loop
the Option-1 diff over the list first). Blind bulk `rm` destroys any differing
local copy.

```bash
# Parse the error message and remove all listed files (AFTER the diff check)
git checkout main 2>&1 | grep "^\t" | tr -d '\t' | while read f; do
  git diff --quiet --no-index <(git show origin/main:"$f" 2>/dev/null) "$f" 2>/dev/null \
    || { echo "DIFFERS, backing up: $f"; mkdir -p /tmp/untracked-backup/"$(dirname "$f")"; cp "$f" /tmp/untracked-backup/"$f"; }
  rm -f "$f"
done
git checkout main  # Should succeed now
```

**Option 3: Nuclear option (reset to remote state)**

```bash
git checkout main
git fetch origin
git reset --hard origin/main
```

Only use option 3 if you have no uncommitted work you need to keep.

**Option 4: Stash won't help**

`git stash` only stashes tracked files. These are untracked, so stash won't capture them. You need to either `rm` them or use `git clean`.

## Verification

After removing the files and pulling:
```bash
git log --oneline -3  # Should show the squash-merge commit
ls path/to/previously/blocking/file  # Should exist (from main)
```

## Why This Happens

Regular merge preserves branch commit history — git sees the files as already present via the merge commit's parents. Squash merge creates a single new commit with no parent relationship to the branch. Git's merge machinery can't tell that the untracked local files are the same as the ones being introduced by the squash commit.

This is a known git UX issue. There's no `git pull --overwrite-untracked` flag.

## Prevention

When working across multiple branches that create new files:
1. Clean up untracked files before switching branches: `git clean -fd path/to/results/`
2. Use `git worktree` for parallel work to avoid file collisions entirely
3. After a squash merge lands, do a clean checkout: `git checkout main && git pull` before creating new branches

## Notes

- `git diff origin/main --stat` showing changes after a squash merge is **normal** — it compares commit hashes, not file contents. Use `git diff origin/main -- .` for actual content differences.
- This problem is most common in data science repos where experiments generate many result files across parallel sessions.
