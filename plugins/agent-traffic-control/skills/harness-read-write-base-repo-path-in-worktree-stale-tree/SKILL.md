---
name: harness-read-write-base-repo-path-in-worktree-stale-tree
description: |
  In a git-worktree session, your OWN Read/Write/Edit tool calls that use a BASE-repo
  absolute path (one MISSING the `.claude/worktrees/<name>/` segment) silently operate on
  the base repo's working tree — a DIFFERENT, often month-stale branch sharing the same
  `.git`. Use when: (1) a `Read`'s line numbers / function locations don't match a `grep`
  you ran in the worktree cwd (Bash sees the worktree; Read with a base path sees the base
  repo); (2) a `Write`/`Edit` "succeeds" but the file never appears in the worktree's
  `git status -sb` (it landed in the base repo, untracked there); (3) a review/subagent (or
  a fresh checkout) reports a file you just wrote "doesn't exist"; (4) a file looks
  surprisingly smaller/older than expected (e.g. bq_queries.py 7228 lines via base path vs
  8434 in the worktree). Root cause: harness file tools take absolute paths verbatim and do
  NOT pin to the worktree; the base repo is a separate checkout, usually parked on another
  branch. Fix: build EVERY file path under the worktree root (the env's "Primary working
  directory"), and cross-check Read line numbers against a cwd-relative grep.
author: Claude Code
version: 1.0.0
date: 2026-06-23
disable-model-invocation: true
---

# Read/Write/Edit with a base-repo path silently hits the stale base tree in a worktree session

## Problem
You're working in a worktree (`<repo>/.claude/worktrees/<name>/`). Your `Bash` tool runs with
cwd = the worktree, so `grep`/`git`/`wc` see the worktree's branch. But `Read`/`Write`/`Edit`
take **absolute paths verbatim** — if you write `/…/<repo>/path` (the BASE repo path, missing the
`.claude/worktrees/<name>/` segment) you operate on the **base repo's working tree**, a *different*
checkout that shares the same `.git` and is usually parked on an unrelated, often **month-stale**
branch. The two trees diverge silently and you don't get an error.

## Context / Trigger Conditions
- A `Read`'s line numbers or the functions it shows **disagree with a `grep`/`wc`** you ran in the
  worktree cwd (e.g. `def get_top_drivers` at L2926 via Read vs L3795 via grep).
- A `Write` reports success but the new file is **absent from `git status -sb`** in the worktree
  (it was created in the base repo, untracked there).
- A `Write` to an existing file's path "works" but later edits to "the same file" via worktree-relative
  paths don't see your change.
- A review panel / dispatched subagent / fresh `git` checkout reports a file you KNOW you wrote as
  "absent from the working tree" / "doesn't exist on any ref" (it's sitting untracked in the base repo).
- A file looks much smaller/older than the current branch should have.

## Solution
1. **Always prefix file paths with the worktree root** — the value the environment prints as
   "Primary working directory" (`/…/<repo>/.claude/worktrees/<name>/…`), never the bare `/…/<repo>/…`.
   `Bash` is fine with worktree-relative paths (cwd is already the worktree); `Read`/`Write`/`Edit`
   need the full worktree-prefixed absolute path.
2. **Cross-check on first Read of any file:** if its line numbers don't match a `grep -n` you ran in
   the worktree cwd, you read the wrong tree — re-read via the worktree path.
3. **After any Write/new file:** confirm it shows in the worktree's `git status -sb` before relying on it
   (and before dispatching a review that needs it).
4. **Confirm the divergence when suspicious:**
   `git -C <base-repo> rev-parse --abbrev-ref HEAD` vs the worktree's branch — if they differ, base-path
   reads/writes are operating on that other branch's content.

## Verification
- A worktree-path `Read`'s line numbers match `grep -n <symbol> <worktree-path>`.
- A just-written file appears in `git status -sb` of the worktree.
- `wc -l` (worktree cwd) and the `Read` agree on file size.

## Example
Session worktree on `feat/X` (current `origin/main`); base repo parked on a month-old branch.
`Read('/Users/me/repo/…/bq_queries.py')` returned a function at L2926 and 7228 total lines, while
`grep -n 'def get_top_drivers'` (Bash, worktree cwd) said L3795 and `wc -l` said 8434. A spec
`Write('/Users/me/repo/docs/plans/…md')` "succeeded" but never showed in `git status`, and the review
panel reported it "absent from every ref." Cause: all three used the **base** path. Fix: re-Read/Write
via `/Users/me/repo/.claude/worktrees/<name>/…` — line numbers matched and the file appeared in status.

## Notes
- Distinct from the bash-cwd worktree traps (`main-bash-cwd-persists-nested-worktree`,
  `subagent-bash-cd-wrong-worktree`) — those are about `cd` and shell cwd; THIS is about the harness
  Read/Write/Edit tools taking an absolute path that points at the base repo.
- Distinct from `preview-mcp-reads-base-repo-launch-json` (an MCP reading the base repo) and from the
  file:// URL staleness lesson (browser bookmarks reflecting a stale branch).
- See also: `dispatched-bash-agent-git-checkout-clobbers-uncommitted-edit` (a subagent reverting your
  uncommitted edit), `concurrent-session-checkout-clobbers-shared-worktree`.
- Also captured as a rule in `~/.claude/lessons.md` ("Worktree sessions: tool-call paths must be
  worktree-prefixed").
