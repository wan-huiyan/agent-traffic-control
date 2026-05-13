---
name: git-add-u-after-async-post-commit-hook
description: |
  Prevent (and recover from) `git add -u` + `git commit --amend` + `git push --force-with-lease`
  catastrophically rolling thousands of unrelated tracked-file deletions into an amended commit
  when the project has an async post-commit hook that mutates tracked files (e.g. regenerates
  `docs/site/*.html`, `docs/site/index.html`, `MEMORY.md`, or any other tracked artefact in a
  background `&` / `nohup` / "running … in background" process). Use when: (1) you just made
  a small commit, the post-commit log line says `[post-commit] … running … in background`,
  and you're about to amend with corrected message / typo / issue ref; (2) `git commit --amend`
  output reports `1000+ files changed, … insertions, NNN,NNN deletions(-)` when you only
  intended a 6-file change; (3) the force-pushed branch on origin shows a massive deletion
  diff and `git status` after the amend shows previously-tracked files like `MEMORY.md`,
  `.github/`, `.cursor/`, `scripts/` as Untracked; (4) you ran `git add -u` reflexively before
  `--amend` on a project with async hooks. Sister skill to
  `worktree-index-corrupt-async-post-commit-hook` (same root cause family — async post-commit
  hook side effects — different symptom: that one corrupts sibling worktree indexes via blob
  GC race; this one mass-stages tracked-file deletions in the SAME worktree). NOT for: stale
  lock files (.git/index.lock — separate pattern), pre-commit hook failures (different signal),
  or post-commit hooks that only print logs without touching tracked files (those are inert).
author: Claude Code
version: 1.0.0
date: 2026-05-06
---

# `git add -u` after async post-commit hook stages tracked-file deletions

## Problem

You make a clean commit. The project's post-commit hook prints something like:

```
[post-commit] Python files changed — running doc update in background...
```

You then need to amend the commit (typo in message, wrong issue reference, etc.).
You reach for the muscle-memory sequence:

```sh
git add -u && git commit --amend -m "..."   # ← TRAP
```

The amend output reports something terrifying:

```
[your-branch 480e2226] fix(...): your message
 1493 files changed, 4 insertions(+), 368977 deletions(-)
 delete mode 100644 .claude-memory/MEMORY.md
 delete mode 100644 .claude-memory/SESSION_CHECKPOINT_*.md
 delete mode 100644 scripts/...
 ...
```

If you immediately ran `git push --force-with-lease`, that catastrophe is now
on the remote branch. The remote PR diff shows thousands of unrelated deletions
mixed with your intended 6-file fix.

`git status` afterwards reveals the smoking gun — files that WERE tracked before
the amend now show as **Untracked**:

```
On branch your-branch
Your branch is up to date with 'origin/your-branch'.

Untracked files:
        .claude-memory/
        .cursor/
        .github/
        MEMORY.md
        PRODUCT.md
        scripts/
```

## Why it happens

The async post-commit hook fires after your *first* commit and starts a background
process that:

1. Reads tracked files (e.g. `MEMORY.md`, `docs/site/*.html`).
2. Regenerates / renames / moves / deletes them as part of doc rebuild logic.
3. May run `git rm` or otherwise mutate the index.

The hook is async (`&` / `nohup`), so the commit returns immediately and you
get the prompt back. The hook is still running.

When you then run `git add -u`, git stages **every change to tracked files** —
including all the deletions/modifications the hook performed. When you `--amend`,
those deletions become part of the commit. Force-push propagates them to the
remote.

## Trigger conditions

ALL of these together:

- Project has a post-commit hook that prints `running ... in background`,
  `running ... in &`, `nohup`, or similar — visible in `git commit` output.
- You commit, see the hook log line, and don't wait for the background process.
- You run `git add -u` (or `git add .` from repo root) before amending or
  before staging your next intentional change.
- Your `git diff --staged --stat` reports far more files than you touched.

If the post-commit hook is synchronous (no `&`, hook output appears before
prompt returns), you're safe — `git add -u` will only see your intentional
changes plus any sync hook output, which is normally idempotent.

## Recovery

The good news: **`reset --hard` is safe** in this scenario, because the
"deleted" files are still on disk as **untracked** (the post-commit hook
didn't unlink them, it removed them from the index when re-tracking the
regenerated artefacts). The reset restores them as tracked.

```sh
# 1. Identify the original good commit SHA — git reflog or the commit summary
#    line printed by your *first* commit (before the bad amend).
git reflog | head -5
#  → c77e6365 HEAD@{2}: commit: fix(insights): ...your good commit
#  → 480e2226 HEAD@{1}: commit (amend): ...same message, but bad index
#  → 1ae4d375 HEAD@{0}: prior main HEAD

# 2. Reset to the original good commit. ⚠ Destructive — confirm SHA first.
git reset --hard c77e6365

# 3. Force-push to remote. Use --force-with-lease so concurrent pushes are caught.
git push --force-with-lease origin your-branch

# 4. If you needed an amend (typo, wrong issue ref), redo it now — but stage
#    EXPLICIT PATHS, not `-u`:
git add path/to/file1 path/to/file2
git commit --amend -m "corrected message"
git push --force-with-lease origin your-branch
```

If anyone else has pulled the bad commit, prefer `git revert <bad-sha>` over
reset+force-push — same end-state on `main` after squash-merge but no
history rewrite.

## Prevention

### Rule 1: Never `git add -u` immediately after a commit on this project

Use explicit paths:

```sh
git add goal_term_enrollment/cloudrun/cr_client_dashboard/ai_insights.py \
        goal_term_enrollment/cloudrun/cr_client_dashboard/tests/test_ai_insights_v2.py
git commit --amend -m "..."
```

`git add .` from the repo root has the same trap.

### Rule 2: Sanity-check `git diff --staged --stat` before `--amend`

```sh
git add path/specific/files
git diff --staged --stat
# → 6 files changed, 211 insertions(+), 21 deletions(-)
#   ✅ matches expectation, proceed
# vs.
# → 1493 files changed, 4 insertions(+), 368977 deletions(-)
#   ❌ STOP, do not amend
```

If the file count or deletion count is materially larger than your intended
change, reset the index (`git reset HEAD path/...` or `git restore --staged .`)
and stage explicitly.

### Rule 3: Wait for the async hook to finish

Cheap check — give it 5-10 seconds, then:

```sh
git status   # should be clean if the hook idempotently regenerates
ps -ef | grep -i "your-project-name\|generate_website\|generate_roadmap"
```

If files keep changing, the hook isn't done yet. Wait longer.

### Rule 4: Inspect the project's post-commit hook once per worktree

```sh
cat .git/hooks/post-commit
# or, for projects that vendor hooks:
cat .githooks/post-commit
git config core.hooksPath
```

If the hook contains `&` or `nohup` AND touches tracked files (`git add`,
`git rm`, file rewrites in `docs/`, `MEMORY.md`, etc.), this skill applies
to every commit in that repo.

## Verification

After recovery, confirm the branch is clean:

```sh
git log --oneline -2
git diff HEAD~1 --stat   # should match your INTENDED change (e.g. 6 files / 211+ / 21-)
git status               # should be "nothing to commit, working tree clean"
```

On the remote PR, refresh — the diff should show only the intended files.

## Notes / edge cases

- Pre-commit hooks don't trigger this trap directly, but a pre-commit hook that
  prints `running ... in background` carries the same mechanism — the same
  rules apply between successive `git add` calls within a single commit.
- `git commit -a` has the SAME trap as `git add -u && git commit --amend` —
  the `-a` flag stages all tracked-file changes, including hook side-effects.
- Force-pushing to a shared branch propagates the catastrophe. `--force-with-lease`
  protects you against concurrent legitimate pushes overwriting your work,
  but does **not** detect that *your own* push is bad — that's on you.
- A post-commit hook that ONLY prints (no `git add`, no file mutations) is
  inert; the trap requires both async execution AND tracked-file mutation.

## Sister skills (same root cause family)

- [`worktree-index-corrupt-async-post-commit-hook`](../worktree-index-corrupt-async-post-commit-hook/SKILL.md)
  — async post-commit hook in worktree A causes `fatal: unable to read <sha>` /
  cache-tree corruption errors in **sibling** worktree B. Same hook mechanism,
  different surface (cross-worktree blob GC race vs. same-worktree index
  staging trap).
- [`gh-pr-merge-worktree-checkout-trap`](../gh-pr-merge-worktree-checkout-trap/SKILL.md)
  — `gh pr merge` failing because main is checked out in another worktree
  (same project, different sharp edge).
- [`git-rebase-stalls-async-post-commit-hook`](../git-rebase-stalls-async-post-commit-hook/SKILL.md)
  — async post-commit hook causes `git rebase` to stall mid-replay with
  `hint: ... It has been rescheduled` output, leaving stuck `rebase-merge`
  directories that `--abort` won't clear. Same hook mechanism, different
  surface (multi-commit rebase race vs. same-worktree index staging trap).
  Fix: `git -c core.hooksPath=/dev/null rebase origin/main`.

## References

- [git-commit hooks: post-commit (git-scm.com)](https://git-scm.com/docs/githooks#_post_commit)
- [git-push --force-with-lease semantics](https://git-scm.com/docs/git-push#Documentation/git-push.txt---no-force-with-lease)
