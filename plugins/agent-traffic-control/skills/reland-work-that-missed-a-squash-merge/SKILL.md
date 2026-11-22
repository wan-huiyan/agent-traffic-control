---
name: reland-work-that-missed-a-squash-merge
description: |
  A PR was squash-merged but some of your work never reached main. Use when a fixed bug is
  back after the merge, `git status` still shows files you edited during the review pass,
  the squash commit's size matches only your first commit, you pushed follow-up commits and
  found the PR already merged, or you wrote a new commit on the merged branch and need it on
  main.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Re-land Work That Missed a Squash Merge

Merged from: working-tree-edits-stranded-on-squash-merge, pr-followup-commit-stranded-after-squash.

## Problem

**A squash merge captures exactly what was committed and pushed to the branch at the moment of
merge.** Not what is in your working tree, and not what you push afterwards. The mental model
"squash collapses everything that ever lived on the branch" is wrong. Nothing errors, the PR shows
`MERGED`, and main is incomplete. Three ways work gets left behind:

### Variant 1 — edits never committed

You iterate on a PR during an acceptance pass. The user reports a bug; you fix it with the Edit or
Write tool; the live server or preview picks it up; the user confirms; you move on. Later you fix
another bug with `git add <that_file>` + `git commit`, and squash-merge. The user reloads: "the bug
is back". Edit and Write change the working tree but do not stage, so only the file you added went
into the commit. After the merge, `git status` in the worktree shows `M <file_you_edited>` and the
squash on the base branch has the old content.

The Edit/Write tools are deliberately non-staging, so the user can stage the way they would in any
workflow; the gap is in the workflow, not the tool. Scratch edits made only to show a preview and
then consciously discarded are fine; the trap is edits you **think** shipped.

### Variant 2 — commits pushed after the merge

You pushed commit 1, opened the PR, then pushed commits 2, 3, ... in response to feedback. The user
merged while only commit 1 (or the first few) was on the branch, possibly during one of your
iterations. GitHub does not re-apply a closed branch's later commits onto main. Signs:

1. `gh pr view N --json state` returns `MERGED`;
2. `git show <merge-commit> --stat` has insertion counts matching only your first commits;
3. `git log origin/main..<closed-branch> --oneline` lists commits that are not on main;
4. the closed branch still exists locally and/or on GitHub, holding them.

### Variant 3 — a new commit written on the branch after the merge

You finish, the squash lands, then you write a new commit (for example a session-handoff doc
referencing the merged PR) on top of the old local branch and want it on the base branch
(`main`, `release-uk`). Recovery is the same as Variant 2, but one tempting command is dangerous:

**Do not use `git rebase --onto origin/<base> <pre-squash-branch> <followup-branch>`** across a
squash-merged boundary. It has been seen to **silently drop the new commit** with
"Successfully rebased and updated refs", no error, no skip notice, working tree reset to the base
tip. Reproduced: commit `13f1ac7` added two new files that conflicted with nothing on `release-uk`,
yet `git rebase --onto origin/release-uk feat/s63-oom-sentinel docs/s63-handoff` reset the branch to
`origin/release-uk` with no replayed commit. The root cause was not found (the patch was non-empty
and not a duplicate); the defensive rule stands. If it already happened, `git reflog <branch>` then
`git reset --hard <reflog-hash>` recovers it within the reflog retention window.

Even rebase-merge has an edge: a commit pushed after the rebase-merge starts may or may not be
included, depending on GitHub's race resolution.

## Context / Trigger Conditions

- You used Edit/Write during an interactive review pass to make a preview reflect a fix, and later
  committed a different file.
- You pushed several commits asynchronously to one PR, not all before opening it.
- After the merge: the user says the issue is back; `git status` shows `M` lines for files you
  remember fixing; `git diff origin/<base>` against the merged work surfaces edits that should have
  been in the PR; or `[ahead N]` commits sit on the merged branch.
- `gh pr create` or the merge printed `Warning: N uncommitted changes`. That is the canary.
- If the stranded commit was made by a background post-commit hook rather than by you, see
  `recover-from-an-async-post-commit-hook` (Variant 5).

## Solution

### Prevent

1. **Audit before every merge.**

   ```bash
   git status --short              # any `M` or `??` lines?
   git diff                        # any uncommitted hunks?
   git diff origin/<base_branch>   # exactly what the squash will contain
   ```

   For each unstaged change decide: part of this PR (`git add <file>`, commit, push, then merge);
   stays local (stash it or `.gitignore` it so the choice is explicit); a leftover from an earlier
   session (triage it). Never run `gh pr merge` with a non-empty `git status` without a stated
   reason; the harness and GitHub will both let you.
2. **Check PR state before every push to a PR branch.**

   ```bash
   gh pr view <num> --json state
   ```

   If it is `MERGED`, stop: commit on a fresh branch off current main and open a follow-up PR.
3. For high-iteration PRs (three or more async commits expected): prefer rebase-merge if the
   project allows it, or hold iterations locally and push one batch right before merge, or tell the
   user "still iterating, hold the merge" before each push.

### Recover — re-land on a fresh branch off current main

Never build on the stale, merged branch.

**Uncommitted edits (Variant 1).** The edits survive the checkout because they are uncommitted:

```bash
git fetch origin
git checkout -B hotfix/<short-name> origin/<base_branch>
git add <files_that_were_stranded>
git diff --staged                 # sanity-check before commit
git commit -m "hotfix(<area>): <fixes that missed the squash>

<one paragraph per stranded fix explaining the bug and why it missed>"
git push -u origin hotfix/<short-name>
gh pr create --base <base_branch> --title "..." --body "..."
gh pr merge <new_pr> --squash
```

If the stranded edits were since reverted (for example by `git checkout HEAD -- <file>`), the
working tree is no longer the source; recover from the Edit tool's history or re-apply from notes.

**Stranded or new commits (Variants 2 and 3).**

```bash
git fetch origin --prune
git log origin/main..<closed-branch> --oneline   # EVERY branch commit, landed ones included:
                                                 # after a squash none of their SHAs are on main
gh pr view <N> --json commits -q '.commits[].oid'   # the commits the merged PR captured
git show <squash-sha> --stat                     # cross-check: the content that landed
# stranded = branch commits after the last one the PR captured
git checkout -b <topic>-followup origin/main
git cherry-pick <commit-2> <commit-3> ...        # resolve conflicts if main moved
git push -u origin <topic>-followup
gh pr create --title "<topic>: follow-up — <what was missed> (PR #N squash missed M commits)" \
  --body "PR #N was squash-merged when only my first commit was on the branch. The follow-up
commits — <list> — never reached main. This PR cherry-picks them. Stale on main: <file X> still
says <old>; should say <new>."
```

For one new commit after the merge:

```bash
git checkout -b <followup-branch>-v2 origin/<base>
git cherry-pick <followup-commit-sha>
git push --force-with-lease origin <followup-branch>-v2:<followup-branch>
```

The closed branch is not garbage-collected at once (`--delete-branch` removes the remote branch, not
your local one, which is what you cherry-pick from), but the longer you wait, the more main diverges
and the more conflicts the cherry-pick meets. A conflict there is normal; resolve it on top of the
latest content.

## Verification

- `git diff origin/<base_branch> origin/hotfix/<name>` shows only the stranded edits, no extras.
- After the recovery PR merges: `git fetch origin --prune` and `git show origin/main:<file> | head
  -20` shows the intended end state, not the first commit's state.
- `git status` in the worktree is clean once the fix is checked out or pulled.
- The user-facing symptom reproduces before and is gone after.

## Example

During PR #90's acceptance pass the user reported two UI bugs. (1) A Plotly chart looked squashed
because the y-range included masked-period extrapolations (~2.5M) while visible data sat at
200K-300K; fixed by editing `webapp/templates/report.html`. (2) Download buttons were missing
because a save path raised `ModuleNotFoundError` from a wrong relative import; fixed in
`webapp/views/analysis.py` (`.data_storage` → `..data_storage`). The Flask reloader picked both up
and the user verified. Then an unrelated `webapp/templates/runs.html` change was committed without
adding the two earlier files. After the squash, "buttons still not there"; `git status` showed
`M webapp/templates/report.html` and `M webapp/views/analysis.py`. Recovery PR #93 shipped both in
eight minutes. `gh pr create` had printed `Warning: 3 uncommitted changes` during #90 and was
ignored.

## Notes

- `git diff origin/<base>` before merging is the auditable truth of what the squash will contain;
  anything you expect that is not there is stranded.
- GitHub's docs on squash and merge do not call out the "commits pushed after merge are stranded"
  case.

## See also

- `recover-from-an-async-post-commit-hook`: a hook's commit lands after your push and is orphaned.
- `verify-a-squash-merge-by-content-not-lineage`: false alarms after a squash that did land.
- `pr-conflict-from-mid-flight-merges`: other PRs make your open PR conflict.
- `gh-pr-merge-worktree-checkout-trap`: `gh pr merge` local side effects fail from a worktree, but
  the merge succeeded.

## References

- [GitHub docs: About pull request merges — squash and merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges#squash-and-merge-your-commits)
- [Pro Git §2.2 — Recording Changes](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository)
