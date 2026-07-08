---
name: gh-pr-merge-squash-stdout-shows-sibling-files-as-created
description: |
  Use when `gh pr merge --squash` prints an alarming diffstat — far more files
  than your PR touched, with `create mode 100644 <file>` lines for files you
  never added (e.g. handoff docs, sibling-PR artifacts) and an inflated
  insertion count. This looks like your PR smuggled unrelated content onto the
  base branch, but it usually has NOT: the echoed diffstat reflects your branch
  measured against an OLDER ancestor (files from sibling PRs merged to main
  *after* your branch point show as "created" in that view). The authoritative
  truth is the squash commit itself. Apply when: (1) `gh pr merge --squash`
  output shows a file-count / `create mode` lines that don't match your PR,
  (2) you fear a feature PR pulled in docs/zips/sibling changes, (3) before
  reacting (revert/force-push) to a scary merge echo. Verify with
  `git show --stat origin/main` instead of trusting the merge command's stdout.
author: Huiyan / Claude Opus 4.8
version: 1.0.0
date: 2026-05-29
disable-model-invocation: true
---

# `gh pr merge --squash` stdout shows sibling-PR files as "created" — don't panic, check the commit

## Problem

You squash-merge a clean, well-scoped PR and `gh pr merge --squash` echoes a
diffstat that's far bigger than your change, including `create mode` lines for
files you never touched:

```
 19 files changed, 744 insertions(+), 7 deletions(-)
 create mode 100644 docs/handoffs/session_24_handoff.md
 create mode 100644 docs/handoffs/session_25_prompt.md
 ...
```

This reads exactly like the `git-add-all-sweeps-untracked-artifacts-into-commit`
trap — as if your feature PR smuggled unrelated docs onto `main`. It is alarming
mid-deploy. But the files shown as "created" were already on `main` (added by
sibling PRs merged *after* your branch's start point), and your actual squash
commit does **not** contain them.

## Context / Trigger Conditions

- `gh pr merge --squash` (or `--squash --delete-branch`) prints a diffstat with
  more files / higher insertions than your PR's real diff.
- `create mode 100644 <file>` appears for files added by other PRs merged since
  you branched (common when each session branches off `main` and several
  sibling PRs have merged in between).
- You're about to revert / force-push / re-open in response to the scary echo.

## Solution

Do **not** trust the merge command's stdout as the record of what landed. The
echoed diffstat can be computed against an older ancestor than the current
`main` tip, so files already present on `main` appear as new. Verify the actual
squash commit:

```bash
git fetch origin --quiet
git show --stat origin/main | head -40   # the real squash commit + its file list
```

If the squash commit lists only your PR's files (and the insertion count
matches), the merge is clean — the stdout was just a misleading view. Optionally
confirm a specific file you feared was smuggled is NOT in the commit:

```bash
git show --stat origin/main | grep -c "session_2"   # 0 = not in the commit ✓
```

Only react (revert) if `git show --stat origin/main` *itself* shows the foreign
files — that's the authoritative source, not the merge echo.

## Verification

`git show --stat origin/main` reports exactly your PR's files (e.g. "16 files
changed, 600 insertions") with none of the sibling-PR files the merge stdout
listed as `create mode`. The branch deletion (`--delete-branch`) succeeded and
the commit subject is your squashed PR title.

## Example

S25 PR #115 (16-file plumbing change, branched off `main` = `4c3c391`, which
already carried #113/#114's handoff docs). `gh pr merge 115 --squash
--delete-branch` echoed "19 files changed, 744 insertions, create mode
session_24_handoff.md ...". Panic averted by `git show --stat origin/main`,
which showed the real squash commit `cac29f2`: exactly 16 files, 600 insertions,
zero handoff files. Proceeded with the deploy.

## Notes

- Distinct from `git-add-all-sweeps-untracked-artifacts-into-commit` (that's a
  real staging mistake caught in `git status`/the PR diff *before* merge). Here
  the PR diff was clean all along; only the post-merge echo was misleading.
- Distinct from `squash-merge-content-preservation-vs-ancestor-check` (that's
  about `git merge-base --is-ancestor` returning non-zero after squash). Same
  family (squash collapses lineage), different surface.
- See also: `git-pull-after-squash-merge` (local branch can't fast-forward
  after the remote squash; needs `-D` not `-d`).
- Root mechanism not fully isolated in-session (whether gh diffed against a
  stale local `main` ref or the PR's merge-base); the actionable rule stands
  regardless — the squash commit is the source of truth, the merge stdout is not.
