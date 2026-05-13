---
name: stacked-pr-base-branch-deletion-auto-closes-dependent
description: |
  Recover from the trap where deleting a base PR's branch (via `gh api -X DELETE
  refs/heads/<branch>`) auto-closes any open dependent stacked PR, and the closed
  PR cannot be reopened or retargeted. Use when: (1) you set up a stacked PR
  pair (PR2's `base` field = PR1's branch instead of `main`), (2) you merged PR1
  via squash, (3) you then deleted PR1's remote branch via the API (because
  `gh pr merge --delete-branch` failed locally with the worktree-checkout-trap
  and you used the API as a workaround), (4) the dependent PR2 is now reported
  as `state: CLOSED` even though you never closed it, (5) `gh pr reopen N` fails
  with `Could not open the pull request`, (6) `gh pr edit N --base main` fails
  with `Cannot change the base branch of a closed pull request`. The only
  recovery is to open a fresh PR from the same head branch with base=main.
  Sister skill to `gh-pr-merge-worktree-checkout-trap` (the upstream cause).
author: Claude Code
version: 1.0.0
date: 2026-05-08
---

# Stacked PR: Base-Branch Deletion Auto-Closes the Dependent PR

## Problem

You have a stacked PR pair:

- **PR1** — `base: main`, `head: feature-pr1`
- **PR2** — `base: feature-pr1`, `head: feature-pr2` (stacked on PR1)

You squash-merge PR1. The merge succeeds. You then run:

```bash
gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/feature-pr1
```

…to clean up the orphaned remote branch (because `gh pr merge --delete-branch`
failed locally with the worktree-checkout-trap and you used the API as a
workaround). Within seconds, PR2 silently transitions to `state: CLOSED`:

```bash
$ gh pr view <PR2> --json state,closed,mergedAt,baseRefName
{"baseRefName":"feature-pr1","closed":true,"mergedAt":null,"state":"CLOSED"}
```

You never closed PR2. The PR's `head` branch still exists with all the work.
But:

```bash
$ gh pr reopen <PR2>
API call failed: GraphQL: Could not open the pull request. (reopenPullRequest)

$ gh pr edit <PR2> --base main
GraphQL: Cannot change the base branch of a closed pull request. (updatePullRequest)
```

GitHub refuses to reopen the PR (its base branch no longer exists), and
refuses to retarget a closed PR. The PR is effectively a dead reference —
all comments, reviews, and history land on a record that nothing can resurrect.

## Why this happens

When a PR's base branch is deleted, GitHub's behavior is asymmetric:

- **If the base branch is deleted via the GitHub UI's "delete branch" button
  on a merged PR**, GitHub usually auto-retargets dependent open PRs to the
  default branch (typically `main`).
- **If the base branch is deleted via the Git Refs API directly**
  (`DELETE /repos/.../git/refs/heads/<branch>`), GitHub does NOT auto-retarget.
  Instead, it auto-closes any open PR whose `base` field referenced the now-
  missing branch.

The closed PR cannot be reopened because GitHub validates that the base ref
exists at reopen time. It cannot be retargeted because the reopen happens
before the retarget — both are blocked by the missing-base validation.

## Context / Trigger Conditions

You are in this trap if **all** of these are true:

1. You used a stacked PR setup (PR2 explicitly opened with `--base <PR1-branch>`,
   not `main`).
2. PR1 squash-merged (PR1 is in `state: MERGED`).
3. You deleted PR1's remote branch via `gh api -X DELETE` (the API), not
   via `gh pr merge --delete-branch` (which would have done it through
   GitHub's UI flow that handles stacked retarget).
4. PR2 is now `state: CLOSED` with `mergedAt: null` and `closed: true`.
5. `gh pr reopen <PR2>` fails with `Could not open the pull request`.

## Solution

The dead PR cannot be recovered. Open a fresh PR from the same head branch
against `main`:

```bash
# 1. Verify the head branch still exists with your work
git fetch origin
git ls-remote origin refs/heads/feature-pr2
# should print a SHA — your work survives on the remote branch

# 2. (Optional) Verify HEAD diff against main is what you expect
git log origin/main..origin/feature-pr2 --oneline | head

# 3. Open a fresh PR with base=main; reuse the original PR's body
#    (you can copy-paste from the closed PR; comments don't migrate).
gh pr create \
  --base main \
  --head feature-pr2 \
  --title "feat(...): same title as the dead PR" \
  --body "$(cat <<'EOF'
Replaces #<DEAD_PR_NUMBER> (auto-closed when PR1's base branch was deleted
post-merge — GitHub couldn't auto-retarget). Same diff, now based on main
directly.

[... rest of original body ...]

Code-review findings preserved as comments on the closed PR:
https://github.com/<owner>/<repo>/pull/<DEAD_PR_NUMBER>#issuecomment-<ID>
EOF
)"

# 4. Squash-merge the new PR as usual
gh pr merge <NEW_PR> --squash
```

Reviews and comments on the dead PR are NOT auto-migrated. Leave a comment
on the new PR that links to the dead PR's review thread so the audit trail
stays connected.

## Prevention (recommended workflow)

Pick ONE of these patterns when working with stacked PRs + worktrees:

### Pattern A — Merge both PRs before any branch cleanup

Don't delete PR1's branch until PR2 is also merged. After PR1 squash-merges,
GitHub automatically marks PR1's branch as "ready to delete" but doesn't
delete it. Leave it alone. Merge PR2 (which still has `base: PR1-branch`).
Once both are merged, clean up:

```bash
gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/feature-pr1
gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/feature-pr2
```

This is the cheapest and safest pattern. PR2 doesn't need to be retargeted —
it merges with `base: feature-pr1`, and GitHub computes the diff correctly
(PR2's head minus PR1's head, which is just PR2's specific commits).

### Pattern B — Retarget PR2 to main BEFORE deleting PR1's branch

If you need to delete PR1's branch immediately after merge (e.g., automation
constraints):

```bash
# 1. Squash-merge PR1
gh pr merge <PR1> --squash

# 2. Retarget PR2 to main (works because PR2 is still OPEN at this point)
gh pr edit <PR2> --base main

# 3. NOW it's safe to delete PR1's branch
gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/feature-pr1
```

The retarget rebases PR2's diff against `main` (which now contains PR1's
squash). PR2 may then need a manual rebase or merge of `main` to resolve
conflicts, but the PR stays open and reviewable throughout.

## Verification

After recovery, verify:

```bash
# Old PR is closed-unmerged (intentional dead state)
gh pr view <DEAD_PR> --json state,mergedAt
# {"state":"CLOSED","mergedAt":null}

# New PR is open against main with the expected diff
gh pr view <NEW_PR> --json state,baseRefName,headRefName
# {"state":"OPEN","baseRefName":"main","headRefName":"feature-pr2"}

# New PR's diff matches what you intended (no PR1 commits leaked back in)
gh pr diff <NEW_PR> | head -50
```

## Notes

- **The harness/CLI does not warn before this happens.** `gh api -X DELETE`
  on a refs/heads/X executes immediately and the auto-close cascade is a
  GitHub-server-side reaction that lands within ~1 second. There is no
  "this will close N dependent PRs, continue?" prompt.
- **The auto-close on dependent PRs is asymmetric with the UI delete-branch
  button.** If you use the GitHub UI's "Delete branch" button on a merged
  PR's page, GitHub generally auto-retargets dependent open PRs to the
  default branch instead of closing them. Only the API-direct ref delete
  triggers the close cascade.
- **GitHub does NOT silently reopen** dependent PRs even if you re-create
  the deleted ref afterwards (`gh api -X PUT refs/heads/feature-pr1`). The
  closed state is sticky.
- **Sister skill — upstream cause:** `gh-pr-merge-worktree-checkout-trap`
  documents why operators reach for `gh api -X DELETE` in the first place
  (because `gh pr merge --delete-branch` fails locally when another worktree
  has `main` checked out). That skill says "the merge succeeded; verify
  state=MERGED and move on" — this skill extends that advice with: if you
  also need to clean up the branch AND a stacked PR depends on it, follow
  Pattern A or B above instead of using the API delete directly.
- **Sister skill — different problem:** `pr-followup-commit-stranded-after-squash`
  covers commits pushed after PR squash-merge — different failure mode
  (stranded commits vs auto-closed PR).

## Example — 2026-05-08 chatbox session

Two-PR stack:
- PR #456 (chatbox hardening), `base: main`, `head: worktree-chatbox-with-data`
- PR #461 (chatbox knowledge gap), `base: worktree-chatbox-with-data`,
  `head: worktree-chatbox-with-data-pr2`

Sequence that hit the trap:

1. PR #456 squash-merged (commit `36111e42` on main). ✓
2. `gh pr merge 456 --squash --delete-branch` — local-side failed with
   "fatal: 'main' is already used by worktree at '...wow-action'"
   (the worktree-checkout-trap; merge succeeded on GitHub, only local
   cleanup failed).
3. To clean up the orphaned remote PR1 branch, ran:
   `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/worktree-chatbox-with-data`
4. **Within seconds, PR #461 transitioned to `state: CLOSED`.** No notification.
5. `gh pr reopen 461` → `Could not open the pull request`.
6. `gh pr edit 461 --base main` → `Cannot change the base branch of a closed PR`.
7. **Recovery:** opened PR #465 with `--base main --head worktree-chatbox-with-data-pr2`,
   reused the body, linked the review-comment thread on the dead #461.
   PR #465 squash-merged successfully.

Total recovery time: ~5 minutes. Could have been zero with Pattern A
(don't delete PR1's branch until PR2 is also merged).

## References

- GitHub Git Refs API delete behavior:
  https://docs.github.com/en/rest/git/refs#delete-a-reference
- GitHub stacked-PR documentation (auto-retarget on UI delete):
  https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-base-branch-of-a-pull-request
- Sister skill: `~/.claude/skills/gh-pr-merge-worktree-checkout-trap/SKILL.md`
