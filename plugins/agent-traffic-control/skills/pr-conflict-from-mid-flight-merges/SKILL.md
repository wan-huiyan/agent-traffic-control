---
name: pr-conflict-from-mid-flight-merges
description: |
  Diagnose and resolve a GitHub PR that flips to CONFLICTING / DIRTY (or "This branch
  has conflicts that must be resolved") because OTHER PRs landed on `main` while this
  PR was open. Use when: (1) a PR was clean when opened but is now CONFLICTING after
  hours/days, (2) `gh pr view N --json mergeStateStatus` returns DIRTY / mergeable
  CONFLICTING, (3) the feature branch has accumulated commits whose content is
  already on main via a different PR (squash-merged with a different SHA), (4) you
  need to figure out WHICH PRs landed and which of YOUR commits are now redundant
  before rebasing. Prescribes a 6-step recipe: gh status → list landed commits →
  detect redundant cherry-picks → reset to origin tip → rebase → reconcile.
author: Claude Code
version: 1.0.0
date: 2026-04-27
---

# PR Conflict from Mid-Flight Merges

## Problem

You opened a PR, it was clean and mergeable. While reviewers/CI/you were elsewhere, **other PRs landed on `main`** that touched some of the same files. Your PR now shows `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING` on GitHub, with a "This branch has conflicts that must be resolved" banner.

A naive `git rebase origin/main` may try to replay 14+ commits that aren't really yours — including commits that were squash-merged into main under different SHAs, or commits that someone else cherry-picked onto your branch. You need to (a) identify the actual delta, (b) drop redundant local commits before rebasing, and (c) reconcile any incidental cross-PR additions in a follow-up commit.

## Context / Trigger Conditions

All four hold:
1. PR was clean when opened or last pushed.
2. `gh pr view N --json mergeable,mergeStateStatus` now returns `mergeable: "CONFLICTING"` and `mergeStateStatus: "DIRTY"`.
3. `git log --oneline $(git merge-base HEAD origin/main)..origin/main` shows ≥ 1 commit on main since your branch point.
4. `git diff --name-only $(git merge-base HEAD origin/main)..origin/main` shows files that overlap with your PR's changes.

Adjacent symptom that strengthens the diagnosis: `git log --oneline HEAD~5..HEAD` shows commits you don't recognize ("docs: changelog entry for v3.1.0..." when you only meant to add a README fix) — this means a sibling branch's work got pulled into your local feature branch via checkout-with-modified-state or someone else's cherry-pick.

## Solution

**Six-step recipe.** Run from the PR's local feature branch.

### Step 1 — Confirm the conflict and capture the merge state

```bash
gh pr view <PR#> --json mergeable,mergeStateStatus,baseRefName,headRefName
```

Expect `mergeable: "CONFLICTING"`, `mergeStateStatus: "DIRTY"`. Note `baseRefName` (usually `main`) and `headRefName` (your feature branch).

### Step 2 — Identify what landed on main since your branch point

```bash
git fetch origin main
git merge-base HEAD origin/main                                      # branch point SHA
git log --oneline $(git merge-base HEAD origin/main)..origin/main    # what they merged
git diff --name-only $(git merge-base HEAD origin/main)..origin/main # which files
```

This tells you which PR(s) caused the conflict. If you see commits like `<sha> docs(README): … (#37)` and your PR also touches README, the file overlap is the conflict source.

### Step 3 — Detect redundant cherry-picks on your local branch

This is the non-obvious step. Compare `origin/<your-branch>` (what GitHub sees) against your **local** HEAD:

```bash
git rev-parse origin/<your-branch>   # what's on the PR
git log --oneline -5                 # what's on local HEAD
```

If local HEAD is ahead of origin AND the extra commits' content is already on main via a sibling PR (e.g., a CHANGELOG entry that was independently added to a release PR), those local commits are redundant — they were probably cherry-picked or generated locally for testing and never pushed. They must be dropped before rebasing, otherwise the rebase will try to apply them and conflict-resolve them against their own merged copy.

Confirm a local commit is redundant by grepping its content on main:

```bash
git show <local-only-sha> --stat
git log origin/main --oneline --grep="<keyword from that commit's message>"
```

If a recent main commit references the same content, the local commit is redundant.

### Step 4 — Reset local to the PR's actual tip

This drops the redundant local commits and aligns local with what GitHub thinks the PR contains:

```bash
git reset --hard origin/<your-branch>
```

This is safe — you're not losing real work, only stray local commits. The actual PR content lives on origin and is preserved.

### Step 5 — Rebase onto origin/main

```bash
git rebase origin/main
```

What you should see:
- `warning: skipped previously applied commit <sha>` — git correctly recognized that the squash-merged commit on main is the same logical change as one of your branch's commits (matched via `git patch-id`) and skipped it. **This warning is expected and good.** Do not use `--reapply-cherry-picks` unless you're sure you want a duplicate.
- `Successfully rebased and updated refs/heads/<your-branch>.` — clean rebase, no manual conflicts.

If git instead drops you into manual conflict resolution, that means the file edits genuinely overlap (same lines edited differently). Resolve normally with your editor, then `git add <file>` and `git rebase --continue`.

### Step 6 — Reconcile cross-PR additions in a follow-up commit

After rebase, your PR's diff against main may now lack content that landed in a sibling PR — e.g., the v3.1 release added a row to a Version History table, but your PR was written against v3.0 and only added v3.0. Add a small follow-up commit:

```bash
# example: README update reconciling against a release PR that landed mid-flight
git add README.md
git commit -m "docs: reconcile <topic> against <sibling-PR-#N> after rebase"
```

Keep this commit small and tightly scoped. The PR description should be updated (next step) to call out that the rebase happened.

### Step 7 — Force-push and refresh PR description

```bash
git push --force-with-lease origin <your-branch>
gh pr view <PR#> --json mergeable,mergeStateStatus
# expect mergeable: MERGEABLE, mergeStateStatus: CLEAN
```

`--force-with-lease` is safer than `--force`: it refuses to push if origin moved since your last fetch, preventing you from clobbering someone else's force-push.

Then refresh the PR body via `gh pr edit <PR#> --body "..."` to note:
- The rebase happened
- Any sibling PRs that landed (link them)
- Any reconciliation commits added on top
- Strike through any "Notes" from the original body that no longer apply (e.g., "this PR builds on unmerged branch X" → strike if X has now landed)

## Verification

```bash
gh pr view <PR#> --json mergeable,mergeStateStatus,commits \
  --jq '{mergeable, mergeStateStatus, commits: [.commits[] | {oid: .oid[0:7], message: .messageHeadline}]}'
```

Expect:
- `mergeable: "MERGEABLE"`
- `mergeStateStatus: "CLEAN"`
- The `commits` array shows only your real changes (no `WIP`, no stray cherry-picks, no commits whose message refers to a sibling PR's topic)

## Example (anonymised)
PR #38 was opened on `docs/readme-panel-p0-fixes` against main, with one commit: README P0 fixes from a panel review. Hours later, gh said:
```
{"baseRefName":"main","headRefName":"docs/readme-panel-p0-fixes","mergeStateStatus":"DIRTY","mergeable":"CONFLICTING"}
```

Step 2 revealed two PRs had landed on main: #37 (the dedup base this branch was built on, now squash-merged) and #39 (independent v3.1.0 release). Both touched README.md.

Step 3 revealed local HEAD was 1 commit ahead of `origin/docs/readme-panel-p0-fixes` — a `51bbaa0 docs: changelog entry for v3.1.0` commit that didn't belong (its content was already on main via PR #39's release commit).

Step 4: `git reset --hard origin/docs/readme-panel-p0-fixes` dropped 51bbaa0.

Step 5: `git rebase origin/main` ran cleanly, with `warning: skipped previously applied commit 6e1d28a` confirming the dedup commit was correctly recognized as already on main.

Step 6: A small follow-up commit added a `v3.1` row to the Version History table (since main now had v3.1.0 as the latest) and bumped a `342 tests` claim to `379` to match the v3.1.0 test count.

Step 7: `git push --force-with-lease` succeeded, `gh pr edit` refreshed the body, `mergeStateStatus` flipped to `CLEAN`, and the PR merged.

## Notes

- **Never use `git rebase --reapply-cherry-picks`** unless you've verified the "previously applied" commit is genuinely different from the one on main. The default skip behavior is correct in 99% of mid-flight-merge scenarios.
- **Don't `git push --force`** — always `--force-with-lease`. The lease check prevents you from accidentally clobbering work that landed after your last fetch.
- **If the rebase replays MANY more commits than you expect** (e.g., you committed 1 thing but rebase says "Rebasing 1/14"), you're probably on the wrong branch or your branch accumulated work from a sibling. Verify with `git branch --show-current` before continuing. Abort with `git rebase --abort` if the count is suspicious.
- **The `warning: skipped previously applied commit` line is your friend** — it's git telling you the rebase identified a squash-merge equivalence via `git patch-id`. If you don't see this warning when you expected to (i.e., your branch was based on an unmerged branch that has now squash-merged), check whether that base branch's content is actually on main via `git log origin/main --grep` or `git diff <merge-base>..origin/main -- <file>`.
- **Refreshing the PR description after rebase is non-optional.** The original body may contain claims that are no longer true (e.g., "builds on unmerged branch X"). Reviewers will be confused unless you strike through outdated notes and add a "rebased onto current main" line.
- **Adjacent skill:** `git-pull-after-squash-merge` covers a related but different symptom ("untracked working tree files would be overwritten by merge"). Use that one when the conflict is about uncommitted local changes vs. an incoming merge, not about a feature branch needing rebase.

## References

- Git rebase docs (cherry-pick detection via patch-id):
  https://git-scm.com/docs/git-rebase#Documentation/git-rebase.txt---no-reapply-cherry-picks
- `--force-with-lease` safer-force-push pattern:
  https://git-scm.com/docs/git-push#Documentation/git-push.txt---force-with-leaseltrefnamegt
- gh CLI mergeStateStatus reference:
  https://docs.github.com/en/graphql/reference/enums#mergestatestatus
