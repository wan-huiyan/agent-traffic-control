---
name: verify-a-squash-merge-by-content-not-lineage
description: |
  After a squash merge, git reports something alarming about work that did land. Use when
  `git merge-base --is-ancestor <sha> main` says MISSING though the content checks pass,
  `gh pr merge --squash` prints far more files or `create mode` lines than your PR touched,
  `git pull` or `git checkout main` fails with "untracked working tree files would be
  overwritten", or `git branch -d` refuses a merged branch. Not for work that truly missed
  the squash.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Verify a Squash Merge by Content, Not Lineage

Merged from: squash-merge-content-preservation-vs-ancestor-check,
gh-pr-merge-squash-stdout-shows-sibling-files-as-created, git-pull-after-squash-merge.

## Problem

A squash merge collapses every commit on the source branch into **one new commit** on the target,
with one parent (the previous target tip). The original SHAs never appear in the target's history.
Every git answer that depends on **lineage** (is this commit an ancestor? which files are new since
my branch point? are these local files the ones main introduced?) is therefore wrong or misleading
after a squash, even when every byte of the work landed. The one record you can trust is the
squash commit's content on `origin/main`.

### Variant 1 — the ancestor check says MISSING

```bash
git merge-base --is-ancestor 0b6303e76 origin/main && echo "OK" || echo "MISSING"
# Prints: MISSING
```

…while `wc -l <signature-file>` gives the expected line counts and `grep -c <signature-string>`
gives at least the expected reference count. The SHA truly is not an ancestor; its content is
preserved verbatim inside the squash commit. This fires whenever a handoff, runbook or skill mixes
ancestor checks with content checks for one preservation claim, was written before the merge mode
was decided, or assumed fast-forward or no-ff (which keep lineage). Any check asking "is this old
commit in our new history?" fails the same way for squash workflows. Example: a propagation PR
(35 source commits, `chore/promote-release-uk-to-main → main`) was squash-merged as PR #146 into
`abe1cad7`. The verification block's ancestor check printed MISSING for a colleague's commit
`0b6303e76`, while the line counts (703 / 271 / 303) and the reference count (9, at least 5
expected) all passed. The colleague's work was intact.

### Variant 2 — the merge command's output lists files you never touched

```
 19 files changed, 744 insertions(+), 7 deletions(-)
 create mode 100644 docs/handoffs/session_24_handoff.md
 create mode 100644 docs/handoffs/session_25_prompt.md
```

It reads as if your feature PR smuggled unrelated docs onto main. Usually it did not: the echoed
diffstat was computed against an older ancestor, so files added to main by sibling PRs after your
branch point show as "created". Whether `gh` diffed against a stale local `main` ref or the PR's
merge base was not isolated; the rule holds regardless. Example: PR #115, a 16-file change branched
from `4c3c391` (which already carried #113/#114's handoff docs); `gh pr merge 115 --squash
--delete-branch` echoed 19 files, 744 insertions and `create mode session_24_handoff.md`; the real
squash commit `cac29f2` had exactly 16 files, 600 insertions and no handoff files.

### Variant 3 — untracked leftovers block pull or checkout

```
error: The following untracked working tree files would be overwritten by merge:
    data/results/experiment_1.json
    data/results/experiment_2.json
    docs/findings/analysis.html
Please move or remove them before you merge.
```

A branch created new files, was squash-merged, and you are on a branch (or worktree, or after
cherry-picks) that still has copies of those files untracked. Git cannot tell they match what the
squash commit introduces, because the squash has no parent link to the branch. The same happens on
`git checkout main` from a long-stale branch whose untracked local files shadow files that became
tracked on main since it diverged. Common with working on branch B while branch A gets
squash-merged, with parallel sessions creating overlapping result files, and in data-science repos
where experiments generate many files. There is no `git pull --overwrite-untracked`, and
`git stash` does not help: it stashes tracked files only.

**The danger is in the fix.** An untracked file that exists on main is not necessarily identical to
your copy: a long-stale branch often holds unique edits (a one-line SHA reference, a draft note).
Blind `rm`, `git clean -fd` or `reset --hard` destroys that silently.

### Variant 4 — smaller lineage surprises

- `git branch -d <merged-branch>` refuses because the branch's commits are not ancestors of main;
  `-D` is needed once you have confirmed the content landed.
- `git diff origin/main --stat` from the old branch shows changes after the squash. That compares
  commits, not what landed; use `git diff origin/main -- .` for real content differences.

## Context / Trigger Conditions

- A PR (often a propagation PR, 20+ commits) was squash-merged, and a check, an echo or a git
  command now reports something missing, extra or in the way.
- You are about to react (revert, force-push, re-open, delete files) to that report.
- Confirm the merge mode first:

  ```bash
  gh pr view <PR-N> -R <owner>/<repo> --json mergeCommit
  git log -1 --format='%P' <merge-sha>
  # one SHA = squash or fast-forward; two SHAs = no-ff / merge commit
  ```

  With two parents, `is-ancestor` should work: suspect a wrong SHA or a stale target ref instead.
- Not this skill: work that genuinely is not in the squash commit (edits never committed, commits
  pushed after the merge). That is `reland-work-that-missed-a-squash-merge`.

## Solution

### 1. Read the squash commit itself

```bash
git fetch origin --quiet
git show --stat origin/main | head -40       # the real squash commit and its file list
git show --stat origin/main | grep -c "session_2"   # 0 = the feared file is not in the commit
```

If it lists only your PR's files with the expected insertion count, the merge is clean and the echo
was a misleading view. React (revert) only if this authoritative output itself shows foreign files.

### 2. Replace ancestor checks with content checks

```bash
# file existence + line count
for f in path/to/sig1.py path/to/sig2.py; do
  echo -n "$f: "; git show origin/main:$f 2>/dev/null | wc -l
done
# reference count
git show origin/main:path/to/consumer.py | grep -c "<upstream-symbol>"
# byte-identical block (strongest proof)
for branch in origin/main <source-branch-pre-merge>; do
  git show $branch:path/to/registry.py | sed -n '<start>,<end>p' | sha256sum
done
# two matching hashes = block-level byte preservation proven
```

Then fix the template that recommended the ancestor check, by merge mode:

```markdown
**Verification depends on merge mode:**
- Fast-forward or no-ff merge → `git merge-base --is-ancestor <sha> <target>`
- **Squash merge** → the ancestor check always fails by design. Use content probes: file
  existence, line counts, grep reference counts, byte-identical hash of signature blocks.
- Rebase merge → fails on the original SHA, but a rebased equivalent may exist; use
  `git log --cherry-mark <target>...<source>` for a definitive answer.
```

Where squash is the team default (GitHub's "Squash and merge" button, or `gh api PUT` with
`merge_method=squash` from worktrees), write preservation audits with content checks only; an
`is-ancestor` line will be wrong every time. Either probe is fine when scoped to its merge-mode
assumption; the mistake is mixing them under one claim.

### 3. Clear leftovers only after diffing each against main

```bash
f=path/to/blocking/file
if git diff --quiet --no-index <(git show origin/main:"$f" 2>/dev/null) "$f" 2>/dev/null; then
  echo "IDENTICAL to origin/main — safe to rm"; rm -f "$f"
else
  echo "DIFFERS — back up the local copy first (it has unique content)"
  mkdir -p /tmp/untracked-backup/"$(dirname "$f")"
  cp "$f" /tmp/untracked-backup/"$f"
  git diff --no-index <(git show origin/main:"$f" 2>/dev/null) "$f"   # see what is unique
  rm -f "$f"
fi
git checkout main && git pull        # or: git merge --ff-only origin/main
```

Many files: loop the same check over the list git printed:

```bash
git checkout main 2>&1 | grep "^\t" | tr -d '\t' | while read f; do
  git diff --quiet --no-index <(git show origin/main:"$f" 2>/dev/null) "$f" 2>/dev/null \
    || { echo "DIFFERS, backing up: $f"; mkdir -p /tmp/untracked-backup/"$(dirname "$f")"; cp "$f" /tmp/untracked-backup/"$f"; }
  rm -f "$f"
done
git checkout main
```

`git checkout main && git fetch origin && git reset --hard origin/main` is the last resort, only
with no uncommitted work you need. (`/tmp` does not survive a reboot; move anything you keep.)

**Prevention:** clean generated files before switching branches (`git clean -fd path/to/results/`
after checking them as above); use a separate worktree per parallel task; after a squash lands, do a
clean `git checkout main && git pull` before creating new branches.

## Verification

- Variant 1: an audit that reports `(a) ancestor check: SKIP (squash merge)`, then each signature
  file's line count on `origin/main` matching the expected value, then the reference count at or
  above the expected minimum, ending `Verdict: content preserved`. If `is-ancestor` stays in the
  script, mark it expected-to-fail with a comment, or delete it.
- Variant 2: `git show --stat origin/main` reports exactly your PR's files (for example 16 files,
  600 insertions), none of the files the echo marked `create mode`; `--delete-branch` succeeded and
  the commit subject is your PR title.
- Variant 3: `git log --oneline -3` shows the squash commit; the previously blocking file exists
  (from main); any differing copy is in your backup folder.

## Notes

- The bug is never `is-ancestor` itself; it reports commit-graph reachability, not content.
- Distinct from `git-add-all-sweeps-untracked-artifacts-into-commit`: a real staging mistake
  visible in `git status` or the PR diff before merge. Here the PR was clean all along.
- `gh-squash-merge-closes-only-one-issue`: another squash surprise (only one `Closes #N` closes).
- `byte-identical-sha-gate-as-refactor-safety-net`: the block-hash proof in more depth.
- `pre-merge-client-variant-regression-audit` uses byte-identical hashes for the same reason.

## References

- `git merge-base --is-ancestor`: https://git-scm.com/docs/git-merge-base (graph reachability, not
  content equivalence).
- GitHub, about merge methods: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-merge-methods-on-github
  ("the commits on the head branch are not preserved in the history").
