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
  v1.2.0 (2026-05-26) adds the sequential-error variant: if you re-run from
  the main-repo worktree after the first error, you can then hit "cannot
  delete branch <feature-branch> used by worktree at <feature-worktree>" —
  same one-checkout-per-branch invariant, this time applied to the feature
  branch. Cleanup order: `git worktree remove` BEFORE `git branch -D`.
  v1.3.0 (2026-05-27) adds the `--auto --delete-branch` enable-time
  variant: when checks are still pending, `gh pr merge N --auto --squash
  --delete-branch` fails locally (same "main is already used by worktree"
  message) BEFORE the auto-merge intent is registered server-side —
  `gh pr view N --json autoMergeRequest` returns null. Workaround: drop
  `--delete-branch` (`gh pr merge N --auto --squash`), then `git worktree
  remove` + `git branch -D` manually after the merge lands. The post-merge
  variant in v1.0-1.2 succeeds the merge first then chokes on cleanup;
  this v1.3 variant chokes BEFORE the server-side enable, so verifying
  with `--json autoMergeRequest` (not just `state`) is required.
author: Claude Code
version: 1.5.0
date: 2026-07-10
disable-model-invocation: true
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

### Step 1b (proactive alternative): Merge directly via GitHub API

If you already know `gh pr merge` will fail — because you're always in a
worktree where `main` is locked — skip `gh pr merge` entirely and call the
GitHub REST API directly. This avoids the error and the verify-after dance:

```bash
gh api repos/<owner>/<repo>/pulls/<number>/merge \
  --method PUT \
  --field merge_method=squash \
  --field commit_title="your squash commit title" \
  --field commit_message="optional body"
```

Expected response on success:
```json
{"sha":"<merge-commit-sha>","merged":true,"message":"Pull Request successfully merged"}
```

`merge_method` accepts `squash`, `merge`, or `rebase`. The `commit_title` and
`commit_message` fields only apply to the `squash` method.

**Note**: this form does NOT delete the remote branch — add a separate
`gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>` if needed,
or rely on the repo's auto-delete-head-branches setting.

### Step 2 (optional, prevent next time): Use a non-conflicting worktree

If you frequently hit this, you have two options:

**Option A — Don't keep a long-lived worktree on `main`.** When you need to
sync local main, use a transient worktree (`git worktree add /tmp/main main`)
or just `git fetch origin main` from the feature worktree without checking it
out. This is the cleanest pattern.

**Option B — Run `gh` from the worktree that already has `main` checked out.**
That worktree's `git` is the one `gh` will succeed in checking out into.

**Option C — Use `gh api PUT` directly** (Step 1b above) instead of `gh pr
merge` whenever you're in a long-lived worktree session. Two-liner, no
local checkout side-effect, no verify-after needed.

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
- **WARNING — never run the API ref-delete after a merge that ERRORED (S233b
  2026-06-03):** the `gh api -X DELETE …/refs/heads/<branch>` cleanup above is
  ONLY safe once the merge is *confirmed landed*. If the `gh pr merge` returned
  a transient GraphQL error — e.g. **"Base branch was modified. Review and try
  the merge again."** (common right after you push a follow-up commit and
  GitHub is mid-recompute) — the PR is **still OPEN and UNMERGED**. Deleting its
  **head** ref at that point auto-closes the PR **unmerged** (and the branch is
  gone, so a naive `gh pr reopen` fails until you re-push the branch). This is
  the same auto-close mechanism as the stacked-PR warning above, but applied to
  the PR's *own* head, not a dependent's base. **Do not bundle the ref-delete in
  the same command block as the merge** — that's how it runs unconditionally
  after a failed merge. Gate it:
  ```bash
  gh pr merge <n> --squash            # NO --delete-branch (it half-runs on error)
  test "$(gh pr view <n> --json mergedAt --jq .mergedAt)" != "null" \
    && gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>   # only if merged
  ```
  Recovery if you already deleted the head of an unmerged PR: `git push -u
  origin <branch>` (re-creates the ref from your still-intact local commits) →
  `gh pr reopen <n>` → `gh pr merge <n> --squash` (no `--delete-branch`) →
  verify `mergedAt` → THEN delete the ref. Nothing is lost as long as the local
  branch still holds the commits.
- Same trap applies to `gh pr checkout <number>` if the target branch is
  already checked out elsewhere.
- **Sequential-error variant (S8 2026-05-26, int_gtm_auditor):** if you
  recognise the trap and re-run from the main-repo worktree, you can hit a
  SECOND error on the same merge:
  ```
  failed to delete local branch <feature-branch>: failed to run git: error:
  cannot delete branch '<feature-branch>' used by worktree at '<feature-worktree>'
  ```
  The PR is already merged at this point (gh's "already merged" message
  precedes the error). The local cleanup is failing because the FEATURE
  worktree still has the feature branch checked out. Recovery order
  matters — clean up in this sequence from the main-repo worktree:
  ```bash
  git fetch origin
  git pull --ff-only                            # sync main locally
  git worktree remove ../<feature-worktree>     # release the branch
  git branch -D <feature-branch>                # now safe to delete
  ```
  If you swap steps 3 and 4, the branch-delete fails for the same reason
  the second error fired. The first error ("'main' is already used by
  worktree") and this second error ("cannot delete branch ... used by
  worktree") are symmetric instances of the same one-checkout-per-branch
  invariant — first applied to `main`, then applied to the feature branch.
- The misleading part is that gh's exit code is non-zero, which makes
  scripts treat the merge as failed and may trigger retries or rollbacks
  that aren't needed.
- `git worktree list` is the diagnostic — find the worktree on `main` and
  decide whether to keep it.
- **`--auto --delete-branch` enable-time variant (v1.3, S19 2026-05-27):**
  the v1.0-1.2 variants all describe a POST-merge cleanup failure where
  the GitHub merge already succeeded. There is a sibling PRE-merge
  variant when checks are still pending:
  ```
  $ gh pr merge 88 --auto --squash --delete-branch
  failed to run git: fatal: 'main' is already used by worktree at '...'
  ```
  This time the local `--delete-branch` cleanup attempt fires BEFORE the
  auto-merge intent is registered server-side. `gh pr view N --json
  autoMergeRequest` returns `null` (no auto-merge enabled) AND the PR
  isn't merged. Workaround: re-run without `--delete-branch`:
  ```bash
  gh pr merge 88 --auto --squash
  # then verify
  gh pr view 88 --json autoMergeRequest,state
  ```
  Auto-merge enables; when checks pass the PR merges; then delete the
  worktree + branch manually:
  ```bash
  git worktree remove .claude/worktrees/<feature-worktree>
  git branch -D <feature-branch>   # may already be auto-deleted on
                                   # remote depending on repo setting
  ```
  Diagnostic difference from v1.0-1.2: with the post-merge variant,
  `gh pr view N --json state` returns `MERGED`. With this enable-time
  variant, `state` is still `OPEN` AND `autoMergeRequest` is `null`.
  Always check BOTH fields before concluding the PR is done.

## v1.5.0 variant — the REMOTE ref survives too, and stale SHAs keep resolving (2026-07-10)

When the post-merge local checkout fails, `--delete-branch`'s **remote** deletion can also be
skipped — `git ls-remote origin <branch>` still shows the ref even though the PR reports MERGED.
Two downstream consequences observed:

1. **Docs cite SHAs that will die later.** Pre-squash commits on the surviving remote branch
   still resolve, so a handoff/PR-body written right after the merge can cite `<sha>` "on main"
   when it is NOT an ancestor of main — it only resolves via the leftover branch and goes dead
   the moment someone prunes. Annotate such SHAs ("pre-squash branch commit, not on main") or
   cite the PR number instead.
2. **Cleanup:** delete the remote ref explicitly and verify:
   ```bash
   gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>
   git ls-remote origin <branch> | wc -l   # expect 0
   ```

After ANY `gh pr merge --delete-branch` that printed the worktree error, check the remote ref —
don't assume only the local checkout failed.

## References

- `git worktree` docs: [`git-worktree(1)`](https://git-scm.com/docs/git-worktree) — explains the
  one-checkout-per-branch invariant that produces this error.
- `gh pr merge` source: [github.com/cli/cli](https://github.com/cli/cli) — the local checkout
  step is wrapped around the GitHub API merge call; failures in the wrapper
  do not roll back the API call.
