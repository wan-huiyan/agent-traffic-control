---
name: worktree-write-abs-path-lands-in-parent-checkout
description: |
  In a git worktree session, a Write/Edit whose absolute path points at the
  MAIN-REPO ROOT (the parent checkout) silently creates the file in that parent
  checkout's working tree — on whatever branch it has checked out — NOT in your
  worktree on your feature branch. The file then doesn't appear in `git status`
  on your branch and `ls`/Read inside the worktree can't find it. Use when:
  (1) the environment's "Primary working directory" is a worktree at
  `<repo>/.claude/worktrees/<name>/`, (2) you're about to Write or Edit a file by
  ABSOLUTE path (handoff doc, generated artifact, new source file), (3) you
  habitually type the repo's canonical root path (`/.../<repo>/docs/...`) instead
  of the worktree path (`/.../<repo>/.claude/worktrees/<name>/docs/...`),
  (4) a later step reports "file does not exist" / a commit is missing files you
  "just wrote" / `git status` is unexpectedly clean. Trap: the main repo root is
  a real, writable checkout; writing there succeeds silently and pollutes the
  parent's working tree (often on a stale sibling branch). Mitigation: in a
  worktree, pass RELATIVE paths to Write/Edit (cwd is already the worktree), or
  ensure every absolute path carries the `.claude/worktrees/<name>/` segment;
  after writing, `ls` the file back via a relative path to confirm it's in the
  worktree. See also: worktree-outer-ls-mistaken-for-main-state (the read-side
  sibling), main-bash-cwd-persists-nested-worktree, subagent-bash-cd-wrong-worktree.
author: Claude Code
version: 1.0.0
date: 2026-06-09
disable-model-invocation: true
---

# Worktree: Write to an absolute main-repo path lands in the parent checkout

## Problem

You're working in a git worktree (`<repo>/.claude/worktrees/<name>/`) on a feature
branch. You Write or Edit a file using an absolute path rooted at the repo's
canonical location — `/Users/.../<repo>/docs/foo.md` — out of habit. The Write
**succeeds**: that path is the *parent* checkout's working tree, which is a real,
writable git working directory. So the file lands there, on whatever branch the
parent checkout currently has (often a stale sibling worktree's branch), NOT in
your worktree.

Symptoms: the file you "just wrote" is absent from `git status` / `git add` on your
branch; `ls`/Read inside the worktree reports "does not exist"; a commit silently
omits the files. The write isn't lost — it's in the wrong tree.

## Context / Trigger Conditions

- Environment's "Primary working directory" is `<repo>/.claude/worktrees/<name>/`.
- You're Writing/Editing by ABSOLUTE path and typed the canonical repo root
  (no `.claude/worktrees/<name>/` segment).
- Downstream signal: "file does not exist", unexpectedly clean `git status`, a
  commit missing files, or a script (e.g. a label-audit) that can't find a doc you
  just created.

## Solution

1. **Prefer RELATIVE paths for Write/Edit in a worktree.** The Bash/Write cwd is
   already the worktree root, so `docs/handoffs/foo.md` resolves correctly.
2. **If you must use an absolute path, include the worktree segment:**
   `/Users/.../<repo>/.claude/worktrees/<name>/docs/handoffs/foo.md` — never the
   bare `/Users/.../<repo>/docs/...`.
3. **Confirm placement after writing:** `ls -la docs/handoffs/foo.md` via a
   RELATIVE path from the worktree. If it's missing there, it landed in the parent.
4. **Recover a mis-placed file:** `mv /<repo>/docs/foo.md docs/foo.md` (parent →
   worktree). The parent's working tree returns to clean since the file was
   untracked there.

## Verification

- `ls` the file via a relative path from the worktree root — it exists.
- `git status --short` on your branch shows the file as a new/modified path.
- The parent checkout's `git status` is clean (no stray untracked files left).

## Example

S107c: wrote two handoff docs to `/Users/.../the-causal-impact-repo/docs/handoffs/`
(main repo root) while the active worktree was
`/Users/.../the-causal-impact-repo/.claude/worktrees/channel-split/`. The Writes
succeeded but the files were invisible to `git status` on the docs branch and to
`ls` in the worktree. Caught only because the session-handoff label-audit reported
"file does not exist". `mv`'d both into the worktree; parent tree (on a stale
`docs/s110-...` branch) returned to clean.

## Notes

- The environment's "Do NOT cd to the original repository root" guidance applies to
  **Write/Edit targets too**, not just `cd` — the parent root is off-limits as a
  write destination, not only as a working directory.
- Read-side sibling: `worktree-outer-ls-mistaken-for-main-state` (running `ls`/`find`
  on the outer dir and mistaking its branch's files for main's). Same root
  confusion (parent checkout ≠ your worktree), opposite operation.
- A subagent dispatched into a worktree inherits the same hazard — pass it the
  worktree-rooted path explicitly.
