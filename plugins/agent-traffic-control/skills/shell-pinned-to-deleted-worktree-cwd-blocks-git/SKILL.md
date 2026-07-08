---
name: shell-pinned-to-deleted-worktree-cwd-blocks-git
description: |
  Diagnoses + recovers the "every shell command now fails `fatal: Unable to read current working
  directory: Operation not permitted`" trap, which appears AFTER a git worktree you were running
  commands in gets removed/pruned mid-session (you merged + deleted its branch, ran `git worktree
  remove`, or the Claude Code harness auto-cleaned a merged/unchanged worktree). Use when: (1) git
  AND python both error `Operation not permitted` / `PermissionError: [Errno 1] Operation not
  permitted` on startup; (2) `cd /valid/abs/path && pwd` PRINTS the valid path but the very next
  `git`/`python` in the SAME command still fails (pwd lies); (3) the harness prints "Shell cwd was
  reset to <some-.claude/worktrees/...>" after each Bash call; (4) `git -C /repo`, recreating the
  dir with `mkdir`, `python3 -c "import os; os.chdir(...)"`, and even `dangerouslyDisableSandbox`
  all still fail. Core fact: the shell's kernel cwd is a DELETED directory the OS won't resolve, and
  zsh `cd` updates `$PWD` without a real `chdir()`, so no subprocess can escape it. The Write/Edit
  tools still work (absolute paths, no cwd) — so you can finish authoring files; only git/subprocess
  work is blocked, and must move to a fresh shell. Prevention: don't delete/auto-clean the worktree
  you're shell-active in until its git work is done.
disable-model-invocation: true
author: Claude Code
version: 1.0.0
date: 2026-06-22
last_verified: 2026-06-22
---

# Shell pinned to a deleted worktree cwd blocks all git/subprocess work

## Problem

Mid-session, a git worktree that your Bash shell is running inside gets removed — you squash-merged
+ deleted its branch, ran `git worktree remove`, or (most insidiously) the Claude Code harness
auto-cleaned the worktree after the branch merged. From that point, **every** `Bash` command's git
or python invocation fails:

```
fatal: Unable to read current working directory: Operation not permitted
```

or, from Python:

```
PermissionError: [Errno 1] Operation not permitted
```

The shell's kernel working directory is now a **deleted directory** the OS (macOS especially)
refuses to resolve via `getcwd()`. Every subprocess inherits that broken cwd at startup and dies
before doing any work.

## Context / Trigger Conditions

- The error is `Unable to read current working directory: Operation not permitted` on git, and
  `PermissionError: [Errno 1] Operation not permitted` on python — at *startup*, before any real work.
- **`pwd` lies.** `cd /valid/absolute/path && pwd` prints the valid path, but a `git`/`python` in the
  **same** `&&` chain still fails. This is the diagnostic fingerprint: zsh's `cd` updated its internal
  `$PWD` variable (so the builtin `pwd` reports the new path) but did **not** perform a successful
  `chdir()` syscall — it getcwd()'d the dead dir first (for `$OLDPWD` tracking) and aborted the real
  chdir. So child processes still inherit the dead kernel cwd.
- The harness prints **"Shell cwd was reset to /…/.claude/worktrees/<name>"** after each Bash call —
  it re-pins every fresh shell to the dead path.
- Common origin in Claude Code: you were working in `.claude/worktrees/<x>`, the PR merged, the branch
  was deleted, and the worktree got pruned — pulling the rug out from under your own shell.

## Solution

**You cannot recover git/subprocess use from this shell. Stop trying** — these all FAIL (verified):

- `cd /valid && git …` — `cd` updates `$PWD` only, no real chdir.
- `git -C /repo …` — git still getcwd()'s its own process cwd at startup, fails.
- `mkdir -p <the-deleted-path>` then cd — recreates the path with a NEW inode; the shell holds a
  handle to the OLD deleted inode, so `getcwd()` still fails (`pwd` then prints `.`).
- `python3 -c "import os; os.chdir('/valid'); import subprocess; …"` — Python's import machinery
  getcwd()'s the dead cwd (path-importer cache) and raises `PermissionError` before/around your chdir.
- `dangerouslyDisableSandbox: true` — it's a kernel cwd problem, not a sandbox-policy problem.

**What still works:** the **Write / Edit tools** use absolute paths and do NOT touch the shell cwd.
So:

1. **Finish authoring any files** (handoff docs, code, notes) with Write/Edit to absolute paths —
   those persist on disk fine.
2. **Move the git work to a fresh shell.** Either:
   - Tell the user the exact `cd /abs/repo && git …` recipe to run in a **new terminal** (a fresh
     shell spawns with a valid cwd), or to type it with the `!` prefix in Claude Code (that runs in
     their interactive session, often at a valid cwd), or
   - Continue in a **new Claude Code session** (fresh shell, valid cwd).
3. **Don't lose the work that already committed.** Anything committed/merged BEFORE the prune is safe
   on the remote/main — only post-prune git steps are blocked. Verify the merge landed by reading the
   remote via the GitHub API (`gh` also needs cwd, so use the user's terminal or a prior `gh pr view`
   result) rather than local git.

## Verification

- Confirm the fingerprint: `cd /valid/abs/path && pwd && git status` — `pwd` prints the valid path,
  `git status` errors `Operation not permitted`. That combination = this trap (not a real repo/perm
  problem).
- After moving to a fresh shell: `pwd` returns a real absolute path AND `git status` runs — recovered.

## Example

S264d (2026-06-20): built the Explorer redesign in `.claude/worktrees/explorer-redesign`, squash-
merged PR #1265, the branch was deleted, and the harness pruned the worktree. Every subsequent Bash
command failed `Unable to read current working directory`. Tried (all failed): `cd primary && git`,
`git -C primary`, `mkdir -p` the dead path + cd, `python3 -c "import os; os.chdir(...)"`,
`dangerouslyDisableSandbox`. The merged code was safe on main (`0dd47e77`, verified via an earlier
`gh pr view`). Wrote the two handoff docs with the **Write tool** (absolute paths — worked), and
handed the `git checkout -b … && git add … && git commit && git push && gh pr create` step to the
user for a fresh terminal.

## Notes

- **Prevention is cheaper than recovery:** do a worktree's remaining git/handoff work BEFORE deleting
  its branch or letting it be pruned; or run git from the **primary** repo path, not from inside a
  throwaway worktree you're about to merge away. The Claude Code harness auto-removes merged/unchanged
  worktrees, so "merge my PR" can silently delete the ground under your shell.
- The misleading part is the `pwd`-lies symptom — without it you'd assume a permissions/sandbox bug
  and waste attempts on `chmod`/sandbox flags. The real cause is a *deleted* cwd, full stop.
- See also: `safe-bulk-worktree-branch-cleanup`, `recover-killed-session-from-transcript-and-worktree`
  (sibling worktree-lifecycle skills; this one is specifically the deleted-cwd-blocks-subprocess trap).
