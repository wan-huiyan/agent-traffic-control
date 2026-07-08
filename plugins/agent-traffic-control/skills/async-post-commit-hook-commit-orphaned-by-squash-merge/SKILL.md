---
name: async-post-commit-hook-commit-orphaned-by-squash-merge
description: |
  In a repo with an ASYNC/background post-commit hook (one that fires after a
  commit and creates its OWN follow-up commit — `[auto-docs] …`, a docs/site
  regen, a changelog/checkbox tick), the hook's commit can land LOCAL-ONLY
  *after* your `git push` already captured just your work commit, so it is never
  in the PR and gets ORPHANED + silently lost when the squash-merged branch is
  deleted. Use when: (1) you pushed a fix, PR'd it, and squash-merged, then a
  later `git status -sb` shows your feature branch is `[ahead 1]` (or ahead N)
  of its `origin/<branch>` tracking ref even though "everything merged"; (2) that
  extra commit is authored by a background hook (message prefix `[auto-docs]`,
  `chore: regenerate …`, no human author intent) and contains REAL content (a
  corrected design/doc, a regenerated site asset); (3) you're about to delete the
  merged branch / move on and would lose it. The cause: the hook runs
  asynchronously ("running doc update in background…"), so `git push -u origin`
  completes BEFORE the hook commits — the push and the squash-merge both see only
  your work commit. The fix: BEFORE deleting the branch, inspect the orphan
  (`git show <sha>`), and if it carries content worth keeping, cherry-pick it
  onto a fresh branch off origin/main and fold it into your next (e.g. handoff)
  PR. Sibling of git-amend-hits-async-post-commit-hook-commit (amend folds into
  the hook commit), git-add-u-after-async-post-commit-hook,
  git-rebase-stalls-async-post-commit-hook, git-pull-after-squash-merge.
author: Claude Code
version: 1.0.0
date: 2026-06-22
disable-model-invocation: true
---

# Async post-commit hook's commit is orphaned by a squash-merge

## Problem

A repo has an **async post-commit hook** that fires in the background after each
commit and creates its OWN follow-up commit — typically auto-generated docs, a
site regen, or a "correct the design doc to match the code you just changed"
edit (you'll see `[post-commit] … running doc update in background…` at commit
time and an `[auto-docs] …` commit appear seconds-to-minutes later).

The race that loses content:

1. You commit your fix (`feat/fix …`).
2. `git push -u origin <branch>` runs — and **completes before the async hook
   finishes**, so the remote has only your fix commit.
3. You open the PR and squash-merge it. The squash-merge is built from the
   pushed remote state → it contains only your fix commit.
4. *Then* the background hook's `[auto-docs]` commit lands — **local-only**, on
   top of your branch. It's never pushed, never in the PR, never on main.

Now your local branch is `[ahead 1]` of `origin/<branch>`, holding a commit with
real, useful content (e.g. a design doc corrected to match your change). If you
delete the merged branch or just start the next task, that content is **silently
lost** — and because it was the *hook's* job to keep the doc in sync, nobody
re-generates it.

## Context / Trigger Conditions

- The repo has a background/async post-commit hook (greppable: a `post-commit`
  hook that backgrounds work; commits prefixed `[auto-docs]` / `chore: regenerate`
  with no human author intent).
- You pushed → PR'd → **squash-merged** a branch this session.
- `git status -sb` on that (still-checked-out) branch shows `## <branch>...origin/<branch> [ahead 1]`
  (or ahead N) even though you believe it fully merged.
- `git log --oneline` shows the top local commit is the hook's, authored after
  your work commit, and it touches files (a design doc, a site asset) — not empty.

## Solution

**Before deleting the branch or moving on, rescue the orphan.**

1. **See it.** On the just-merged branch:
   ```sh
   git status -sb            # "[ahead 1]" of origin = unpushed local commit(s)
   git log --oneline -3      # top one is the [auto-docs]/hook commit?
   git show <sha> --stat     # what content did the hook generate?
   ```
2. **Judge it.** If the orphan is genuinely valuable (a doc corrected to match
   your merged change, a needed regen) → rescue. If it's noise (a no-op regen,
   already-correct) → discard, no action.
3. **Confirm the target still exists on main** (main may have moved many commits
   since your fix):
   ```sh
   git cat-file -e origin/main:<path-the-hook-edited> && echo EXISTS
   ```
4. **Rescue by cherry-pick onto a fresh branch off origin/main** (NOT onto the
   stale/merged branch), and fold it into your next PR — the session-handoff PR
   is the natural home:
   ```sh
   git fetch origin
   git checkout -b <handoff-branch> origin/main
   git cherry-pick <sha>           # the [auto-docs] commit applies cleanly
   # … add handoff docs, commit, PR, merge
   ```

## Verification

- `git show <new-sha> --stat` on the cherry-picked commit shows the same file(s)
  as the orphan.
- The next PR's diff includes the rescued content; after merge,
  `git show origin/main:<path>` contains the hook's correction.
- The orphan is no longer unique: `git branch --contains <original-sha>` is now
  moot because the *content* (not the sha) is on main via the cherry-pick.

## Example (the-project-repo, 2026-06-22)

Shipped a /monitor copy fix: committed `7c14b4e0`, `git push -u origin
monitor-sprwin-card-honesty`, PR #1283, squash-merged to `d47349e6`. During the
session-handoff, `git status -sb` showed the branch `[ahead 1]` of origin. The
extra commit `c5de20d3` was `[auto-docs] monitor-redesign design: correct SprWin
empty-card framing to data gap` — the post-commit hook had rewritten the
canonical design doc (`docs/plans/2026-06-19-monitor-redesign/design.md`) so a
future session wouldn't follow the now-falsified "add rich SprWin SQL"
recommendation. Real, load-bearing content — and it was never in PR #1283
(the push captured only `7c14b4e0`; the hook committed after). Rescued: branched
`s262b-followup-handoff` off origin/main (which was 12 commits ahead by then),
`git cherry-pick c5de20d3` (applied clean — the design doc still existed on
main), and shipped it in the handoff PR #1299.

## Notes

- **The tell is `[ahead 1]` after a "complete" squash-merge.** A squash-merge
  normally leaves the local branch behind/diverged, not *ahead* of its own
  origin ref. "Ahead" means a local commit never made it to the remote — and if
  you didn't author it, the async hook did.
- **Why the push misses it:** the hook is async by design (it says "running … in
  background"). `git push` does not wait for it. Whether the hook commit makes
  the push is a pure race; for a fast push it almost never does.
- **Distinct from the sibling skills:** `git-amend-hits-async-post-commit-hook-commit`
  is the hook commit corrupting an `--amend`; `git-pull-after-squash-merge` is an
  untracked-file checkout conflict. This skill is the hook commit being *orphaned*
  (its content lost) because the push/PR/squash-merge all predate it.
- Don't blind-delete a merged branch that's `[ahead]` of origin. Inspect the
  ahead commits first — same discipline as "read before archive/delete".
