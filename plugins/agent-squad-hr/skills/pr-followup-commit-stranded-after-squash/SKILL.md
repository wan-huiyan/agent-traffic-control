---
name: pr-followup-commit-stranded-after-squash
description: |
  Diagnose and recover follow-up commits that were pushed to an open PR's branch
  but never reached `main` because the user squash-merged the PR between pushes.
  Use when: (1) you pushed commit 1, opened a PR, then iteratively pushed commits
  2, 3, ... in response to user feedback, (2) you go to merge / verify and find
  the PR is already MERGED, (3) the squash commit on main has insertion counts /
  file content matching ONLY commit 1 — your follow-up commits are stranded on
  the now-closed branch. Root cause: GitHub squash captures the commits that
  were on the branch *at merge time*, not what you push afterward. The mental
  model "squash collapses everything that ever lived on the branch" is wrong.
  Fix: branch off current main, cherry-pick the stranded commits, open a
  follow-up PR.
author: Claude Code
version: 1.0.0
date: 2026-05-06
---

# Follow-up commits stranded after PR squash-merge

## Problem

You've been iterating on a PR: pushed commit 1, opened the PR, then pushed commits 2 / 3 / ... in response to user feedback or new information. At some point the user merges the PR — possibly during one of your iterations, possibly before you finished pushing. The squash on `main` only contains commit 1's content. Your follow-up commits sit on the closed branch, never reaching `main`. If you ask `gh pr view N --json state` you see `MERGED`, but the merged content is missing your iterations.

This is a silent failure. Nothing errors. The PR appears successfully shipped. But main is incomplete.

## Context / Trigger Conditions

All of:
1. You pushed multiple commits asynchronously to a single PR's branch (not all at once before opening the PR).
2. You believed those commits would all land in the squash because they were on the branch at merge time.
3. `gh pr view N --json state` returns `MERGED`.
4. `git show <merge-commit> --stat` shows insertion counts matching only your *first* (or first few) commits — not all of them.
5. `git log --oneline <stranded-branch>..origin/main` returns empty (the branch's later commits never reached main).
6. The closed feature branch still exists locally / on GitHub, holding the stranded commits.

## Why squash captures less than you think

GitHub's squash-merge captures the state of the branch at the moment of merge. If the user clicks "Squash and merge" on the GitHub UI when only commit 1 is on the branch, *that's* what gets captured. Commits you push after that moment land on a closed branch — GitHub does NOT auto-rebase the closed branch's later commits onto main.

The trap is the mental model. "Squash collapses everything that ever lived on the branch" sounds right but it's wrong. The correct mental model: **squash captures the commits that exist on the branch at merge time**. Push timing matters.

## Solution — recovery recipe

Once you've confirmed commits are stranded, recovery is cheap:

```bash
# 1. Identify the stranded commits — those on the closed branch but not on main
git fetch origin --prune
git log <closed-branch>..origin/main --oneline
# (empty = stranded commits are NOT on main; you need to recover them)
git log origin/main..<closed-branch> --oneline
# This lists the stranded commits in chronological order

# 2. Branch off CURRENT main (not from the stale closed branch)
git checkout -b docs/<topic>-followup origin/main

# 3. Cherry-pick the stranded commits in order
git cherry-pick <commit-2> <commit-3> ...
# Resolve conflicts if main has moved meaningfully

# 4. Push and open a follow-up PR
git push -u origin docs/<topic>-followup
gh pr create --label "documentation" \
  --title "docs(<topic>): follow-up — <what was missed> (PR #N squash missed M commits)" \
  --body "$(cat <<'EOF'
## Summary

PR #N was squash-merged when only my first commit was on the branch. The follow-up
commits — <list> — never made it onto main. This PR cherry-picks them.

## What's stale on main (and this PR fixes)

- <File X>: still says <stale content>; should say <correct content>.
- ...

## Why this happened

Squash captured branch state at merge time, not at PR-close time. Recovery is
cheap; the lesson (`feedback_check_pr_state_before_pushing_followup_commits.md`)
is captured.
EOF
)"
```

## Prevention — verify PR state before each push

The cheapest prevention: before any `git push` to an open-PR branch, run:

```bash
gh pr view <num> --json state
```

If `state == "MERGED"`, **stop**. Don't push. Branch is closed. Commit your work on a fresh branch off current main and open a follow-up PR.

For high-iteration PR work where you expect 3+ async commits in response to user feedback:
- Prefer **rebase-merge** over **squash-merge** if the project allows it (each commit lands distinctly).
- Or: hold all iterations locally, push as a single batch right before merge.
- Or: tell the user "still iterating, hold the merge" explicitly before pushing each follow-up.

## Verification

After recovery PR merges:
```bash
git fetch origin --prune
git show origin/main:<file-that-was-stale> | head -20
# Should now show the correct content from your follow-up commits
```

If the file content matches the *intended end state* (not the original-commit state), recovery succeeded.

## Notes

- Even rebase-merge has an edge case: if you push commit 4 *after* the rebase-merge starts, commit 4 may or may not be included depending on GitHub's race resolution. The safest pattern remains "verify state before each push."
- The closed branch is not garbage-collected immediately — you have time to recover. But the longer you wait, the more main may diverge and require non-trivial conflict resolution during cherry-pick.
- If the stranded commits touched a file that was *also* edited on main between the squash and your recovery (e.g., another PR landed on the same file), `git cherry-pick` may conflict. Resolve normally; the cherry-picked commits should still apply on top of the latest content.
- `--delete-branch` on the original `gh pr merge` deletes the remote branch but not local. Your local copy of the closed branch retains the stranded commits, which is what you cherry-pick from.

## Sibling skills

- `pr-conflict-from-mid-flight-merges` — different problem: OTHER PRs cause conflicts on YOUR open PR (you need to rebase + reconcile).
- `git-pull-after-squash-merge` — post-merge local-state cleanup (untracked files blocking pull).
- `gh-pr-merge-worktree-checkout-trap` — `gh pr merge` failing because another worktree has main checked out (merge succeeded; only the local-side effect failed).

## References

- [GitHub docs: About pull request merges — Squash and merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges#squash-and-merge-your-commits) — the docs *don't* explicitly call out the "commits pushed after merge are stranded" case; this skill fills that documentation gap.
