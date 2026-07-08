---
name: working-tree-edits-stranded-on-squash-merge
description: |
  Diagnose and prevent "I made the fix but it's not on main" cases where the
  fix was applied in the working tree via Edit / Write but never `git add`ed
  before the squash-merge. Use when: (1) you squash-merged a PR and the user
  reports the issue is back, (2) `git status` after the merge shows
  uncommitted changes for files you remember editing during the PR's
  acceptance pass, (3) a follow-up `git diff origin/<base>` against the
  merged branch surfaces edits that should have been in the PR. Root cause:
  the harness's Edit / Write tool modifies the working tree but does NOT
  stage changes; a subsequent `git add <other_file>` + `git commit` leaves
  the Edit'd file in the working tree. When the PR merges, the squash
  captures only what was committed. Sister-skill to
  `pr-followup-commit-stranded-after-squash` (that one covers commits
  pushed after the merge; this one covers edits never committed at all).
author: Claude Code
version: 1.0.0
date: 2026-05-18
disable-model-invocation: true
---

# Working-tree edits stranded by a squash-merge

## Problem

You're iterating on a PR through an acceptance pass. The user surfaces a
bug; you make an Edit() call; the bug is fixed locally; the user confirms;
you move on to the next bug. A few iterations later you squash-merge the
PR. The user reloads the page and says "the bug is back."

The fix is sitting in your working tree, never staged, never committed.
The squash captured everything *committed* on the branch — but Edit() and
Write() don't auto-stage. When you did `git add <other_file>` for the
follow-up bug, only that file went into the commit; the earlier Edit'd
file stayed in the working tree as a modified-but-uncommitted change.

After merge: `git status` shows `M <file_you_edited>`, the merged squash on
`<base_branch>` has the old content, and the user sees the bug return.

## Context / Trigger Conditions

All of these together strongly indicate this pattern:

1. You used Edit() or Write() on a file during an interactive PR-review pass
   (i.e. you applied the fix to "make the live server / preview reflect it"
   for the user to verify, but didn't think of it as a commit-worthy unit).
2. The user later flagged a different bug; you fixed THAT one with
   `git add <different_file>` + `git commit`.
3. Now the PR is merged but the working tree (when you re-enter the
   worktree) shows `M <file_from_step_1>`.
4. The squash commit on `<base_branch>` does NOT include the changes
   from step 1.
5. User-facing symptom: the original bug reappears as if the fix never
   landed.

## Solution

### Prevent — pre-merge audit

Before any `gh pr merge`, run:

```bash
git status --short    # any `M` or `??` lines?
git diff              # any uncommitted hunks?
git diff origin/<base_branch>  # confirm the diff matches your mental model
```

If `git status` shows un-staged modifications, decide for each one:

- Should it be part of THIS PR? → `git add <file>` + commit + push (then merge).
- Should it stay local? → stash or .gitignore it explicitly so you know
  it's intentionally not in the PR.
- Is it a leftover from a prior session? → triage (rarely common but
  happens in long-running worktrees).

Never run `gh pr merge` while `git status` is non-empty without an
explicit reason. The harness will let you, GitHub will let you, and the
user will report the bug as back within hours.

### Recover — hotfix PR

If you've already merged and discovered the strand:

```bash
git fetch origin
git checkout -B hotfix/<short-name> origin/<base_branch>

# The working-tree edits survived the checkout because they're still
# uncommitted. Stage them now:
git add <files_that_were_stranded>
git diff --staged    # sanity-check before commit

git commit -m "hotfix(<area>): <fixes that missed the squash>

<one paragraph per stranded fix explaining the bug + why it missed>"

git push -u origin hotfix/<short-name>
gh pr create --base <base_branch> --title "..." --body "..."
gh pr merge <new_pr> --squash
```

If the stranded edits accidentally got reverted (e.g. you ran
`git checkout HEAD -- <file>`), the working tree is no longer authoritative
— recover from the Edit tool's history or re-apply from notes.

## Verification

After the hotfix lands, the symptom should resolve. Specifically:

- `git diff origin/<base_branch> origin/hotfix/<name>` shows ONLY the
  stranded edits (no surprise extras).
- `git status` on the worktree is clean after the hotfix is checked
  out / pulled.
- The user-facing symptom is reproducible BEFORE and gone AFTER.

## Example

a causal-impact engagement, S60 acceptance pass (2026-05-18):

During PR #90 acceptance the user reported two distinct UI bugs in
sequence:

1. The /runs Plotly chart looked squashed at the bottom because the y-axis
   range was computed from masked-period BSTS extrapolations (~2.5M)
   while visible data sat ~200K-300K. **Fix**: Edit'd `webapp/templates/report.html`
   to apply `isMasked()` in the y-range loop.
2. The /results/<slug> page didn't show the download buttons because the
   opportunistic DB save in `results_page` threw `ModuleNotFoundError`
   from `from .data_storage import ...` (wrong relative-import depth).
   **Fix**: Edit'd `webapp/views/analysis.py` to change `.data_storage`
   → `..data_storage`.

Both fixes worked in the live server (Flask debug reloader picked the
files up). User verified the runs page. THEN I committed an unrelated
file (`webapp/templates/runs.html` for the two-button toolbar) — but
forgot to `git add` the earlier two files. The squash-merge captured
the toolbar change but neither fix.

After merge: user said "buttons still not there", `git status` in the
worktree confirmed the strand:

```
 M webapp/templates/report.html
 M webapp/views/analysis.py
```

Recovery PR [#93](https://github.com/<org>/the-causal-impact-repo/pull/93)
shipped both fixes in 8 minutes via the recipe above. The harness
warning `Warning: 3 uncommitted changes` on `gh pr create` could have
caught this if I'd been paying attention to it during PR #90 too — it
fires on merge with the same wording.

## Notes

- **The Edit / Write tools are deliberately non-staging.** The user can
  reset or selectively stage their working tree the way they would for
  any other dev workflow. This is correct behavior; the workflow gap is
  yours, not the tool's.
- **The `Warning: N uncommitted changes` from `gh pr create` is the canary.**
  If you see it before a merge command, stop and `git status`.
- **`git diff origin/<base>` is the auditable truth.** It shows
  exactly what the squash will contain. Anything you expect that isn't
  there is stranded.
- **Doesn't apply to scratch / preview-only edits.** Sometimes you Edit
  a file just to show the user a rendered preview, then discard. If you
  consciously decide an edit shouldn't ship, that's fine; the trap is
  edits you THINK shipped but didn't.

## References

- Sister skill: `pr-followup-commit-stranded-after-squash` —
  same outcome (changes missing from main), different cause (commits
  pushed *after* merge instead of edits never committed).
- `git status` semantics: [Pro Git §2.2 — Recording Changes](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository)
