---
name: gh-pr-merge-worktree-checkout-trap
description: |
  Diagnose and bypass `gh pr merge --squash --delete-branch` failing with
  "failed to run git: fatal: 'main' is already used by worktree at ..." when
  another git worktree has main checked out. Use when: (1) you run gh pr merge
  and see this exact error, (2) you have multiple worktrees in the repo (e.g.
  `.claude/worktrees/*`), (3) the error appears even though the GitHub merge
  itself looks fine. The merge SUCCEEDED on GitHub — only gh's local-side
  effect (post-merge `git checkout main`) failed. Verify via
  `gh pr view N --json state,mergedAt`; if state=MERGED, you're done. This
  also applies to `gh pr checkout` and any other `gh` subcommand that tries
  to touch the local main branch while another worktree has it claimed.
author: Claude Code
version: 1.0.0
date: 2026-04-27
---

# `gh pr merge` Worktree-on-Main Checkout Trap

## Problem

`gh pr merge --squash --delete-branch` (and similar commands) fail with:

```
failed to run git: fatal: 'main' is already used by worktree at '/path/to/another/worktree'
```

even when the user has every right to merge the PR. The error makes it look
like the merge failed, prompting the user to retry or panic.

**The merge actually succeeded on GitHub.** Only `gh`'s post-merge local
side-effect — switching the local working tree to `main` so it's "ready"
after the merge — failed because git refuses to check out a branch that's
already checked out in another worktree.

## Context / Trigger Conditions

You are in the right place if **all** of these are true:

- You ran `gh pr merge <number>` (any merge mode: `--squash` / `--merge` / `--rebase`).
- The exact error includes `fatal: 'main' is already used by worktree at`.
- The repo has multiple `git worktree` entries (run `git worktree list` to confirm).
- One of those worktrees is on `main` (or whichever branch the PR merged into).

The command's first action is the GitHub merge API call; the local checkout
is downstream of that. Failures in the local step do NOT roll back the merge.

## Solution

### Step 1: Verify the merge actually happened

```bash
gh pr view <number> --json state,mergedAt
# {"state":"MERGED","mergedAt":"YYYY-MM-DDTHH:MM:SSZ"}
```

If `state` is `MERGED`: the PR is merged. The error was a local cleanup
side-effect, not a merge failure. **You can stop here.** Optionally clean up
local artifacts:

```bash
# delete the remote branch (gh's --delete-branch flag also failed silently)
git push origin --delete <feature-branch-name>

# delete the local feature branch (it's already orphaned by the merge)
git branch -D <feature-branch-name>

# remove the worktree you used to develop the feature
git worktree remove .claude/worktrees/<your-feature-worktree>

# prune stale worktree refs
git worktree prune
```

If `state` is `OPEN` or `CLOSED` (without merge): something else went wrong.
The worktree error is masking a real failure. Re-run the merge with `--admin`
or check branch protection / required checks.

### Step 2 (optional, prevent next time): Use a non-conflicting worktree

If you frequently hit this, you have two options:

**Option A — Don't keep a long-lived worktree on `main`.** When you need to
sync local main, use a transient worktree (`git worktree add /tmp/main main`)
or just `git fetch origin main` from the feature worktree without checking it
out. This is the cleanest pattern.

**Option B — Run `gh` from the worktree that already has `main` checked out.**
That worktree's `git` is the one `gh` will succeed in checking out into.

Most users won't bother with prevention — the post-failure `gh pr view`
verification is two seconds and the merge already worked.

## Verification

```bash
gh pr view <number> --json state,mergedAt,mergeCommit
```

Expected after a "failed" merge that actually succeeded:

```json
{
  "state": "MERGED",
  "mergedAt": "2026-04-27T15:04:53Z",
  "mergeCommit": {"oid": "a4bd3004..."}
}
```

The presence of `mergedAt` and `mergeCommit.oid` confirms the merge landed.

## Example

**Symptom (real-world, S109a 2026-04-27):**

```
$ gh pr merge 122 --squash --delete-branch
failed to run git: fatal: 'main' is already used by worktree at '/Users/<user>/Documents/the-project-repo/.claude/worktrees/compassionate-ishizaka-b7e3b7'
```

I had ~40 worktrees in `.claude/worktrees/` from previous parallel sessions,
one of which was on `main`. `gh` tried `git checkout main` after the merge,
git refused.

```
$ gh pr view 122 --json state,mergedAt
{"mergedAt":"2026-04-27T15:04:53Z","state":"MERGED"}
```

**Resolution:** the merge had succeeded; the error was just gh's local
cleanup choking. Same trap fired again 10 minutes later on PR #123 — same
root cause (the same long-lived worktree was still on main).

## Notes

- This is **NOT specific to `--delete-branch`.** Any post-merge action that
  switches branches will hit it. The `--delete-branch` portion does seem to
  also fail silently when the local checkout fails, so manually delete the
  remote branch with `git push origin --delete <branch>` or
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>` after.
- **WARNING — stacked-PR consequence of the API delete workaround:** if the
  branch you are deleting is the `base` of an open dependent stacked PR
  (PR2 was opened with `--base <PR1-branch>` instead of `--base main`),
  using `gh api -X DELETE` on the ref will silently auto-close the dependent
  PR and the close is **not reversible** — `gh pr reopen` and `gh pr edit
  --base main` both fail because the base no longer exists. See
  [`stacked-pr-base-branch-deletion-auto-closes-dependent`](../stacked-pr-base-branch-deletion-auto-closes-dependent/SKILL.md)
  for the recovery (open a fresh PR) and the prevention pattern (retarget
  the dependent PR to `main` BEFORE deleting the base branch, OR merge both
  PRs before any cleanup).
- Same trap applies to `gh pr checkout <number>` if the target branch is
  already checked out elsewhere.
- The misleading part is that gh's exit code is non-zero, which makes
  scripts treat the merge as failed and may trigger retries or rollbacks
  that aren't needed.
- `git worktree list` is the diagnostic — find the worktree on `main` and
  decide whether to keep it.

## References

- `git worktree` docs: [`git-worktree(1)`](https://git-scm.com/docs/git-worktree) — explains the
  one-checkout-per-branch invariant that produces this error.
- `gh pr merge` source: [github.com/cli/cli](https://github.com/cli/cli) — the local checkout
  step is wrapped around the GitHub API merge call; failures in the wrapper
  do not roll back the API call.
