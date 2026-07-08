---
name: git-auto-maintenance-recurring-worktree-index-lock
description: |
  Fix a RECURRING `fatal: Unable to create '.../worktrees/<name>/index.lock':
  File exists` that comes back after you `rm` it — in a busy/multi-worktree repo
  where your OWN git commands keep spawning `git maintenance run --auto` (→ `git
  gc --auto` / `git repack` / `git pack-objects`). Use when: (1) a `git
  checkout`/`add`/`commit` fails with "Another git process seems to be running …
  index.lock: File exists", (2) deleting the lock works ONCE then it returns on
  the next git command, (3) `pgrep -fl 'git (gc|maintenance|repack|pack-objects)'`
  shows background maintenance running, (4) the repo has many loose objects from
  heavy fetch/checkout/commit churn (many worktrees, frequent rebases), OR (5) a PARALLEL
  session's commit was killed mid-flight and left a stale 0-byte lock blocking all sessions in
  the shared worktree. Includes the cause-agnostic forensic test for whether a lock is SAFE to
  remove (lsof-unheld + 0-byte + old mtime). NOT for: stale lock from a crashed async POST-COMMIT
  hook (see `worktree-index-corrupt-async-post-commit-hook` /
  `git-rebase-stalls-async-post-commit-hook`), nor "branch checked out elsewhere" merge errors.
disable-model-invocation: true
author: Claude Code
version: 1.1.0
date: 2026-06-23
---

# Recurring worktree `index.lock` from git auto-maintenance

## Problem
In a repo with many worktrees and heavy object churn, git's **automatic
maintenance** (`maintenance.auto` / `gc.auto`, enabled by default) fires at the
*start* of routine commands once loose-object thresholds are hit. The spawned
`git gc --auto` / `git repack` / `git pack-objects` run concurrently with your
`add`/`commit`/`checkout`, and the contention leaves a **stale
`.git/worktrees/<name>/index.lock`**. You `rm` it, the command works, then the
NEXT git command spawns maintenance again and the lock returns — an infuriating
loop that looks like "another git process is running" when the other process is
git maintaining itself on your behalf.

## Context / Trigger Conditions
- `fatal: Unable to create '.../worktrees/<name>/index.lock': File exists` /
  "Another git process seems to be running … remove the file manually to continue"
- Removing the lock fixes it for exactly one command, then it recurs
- `pgrep -fl "git (gc|maintenance|repack|pack-objects)"` shows live maintenance procs
- Repo has many worktrees / frequent fetches / rebases (lots of loose objects)
- It even blocks a plain `git checkout -b` *before any commit* (rules out a
  post-commit hook as the cause — that's the key discriminator vs the
  async-post-commit-hook skills)

## Solution
1. **Confirm the lock is STALE, then clear it once.** Don't blindly `rm` — a genuinely
   in-progress commit would be corrupted. Three cause-agnostic forensics PROVE staleness
   (any cause: auto-maintenance contention, OR a parallel session's killed/crashed commit):
   ```sh
   LOCK=.git/worktrees/<name>/index.lock          # or .git/index.lock in a plain clone
   lsof "$LOCK"                                    # NO output  => no process holds it open
   [ -s "$LOCK" ] && echo NONEMPTY || echo EMPTY   # 0 bytes    => process died before writing the index snapshot
   ls -la --time-style=full-iso "$LOCK"            # mtime minutes old => not an active commit
   pgrep -fl "git (commit|add|write-tree|gc|maintenance|repack|pack-objects)" | grep -v pgrep
   ```
   **Unheld (lsof empty) + 0-byte + minutes-old = textbook stale → safe `rm -f "$LOCK"`** (git's
   own error literally says "remove the file manually to continue"). Re-check `lsof`/size
   immediately before the `rm`, then stage-by-explicit-path + commit at once to minimise the
   re-lock window. NOTE the background `gc`/`pack-objects` use their OWN locks (`gc.pid`, pack
   lock), NOT `index.lock` — their mere presence is not a reason to wait.
2. **Stop YOUR commands from spawning maintenance** — pass the flags INLINE on
   every git write command for the rest of the session:
   ```sh
   git -c gc.auto=0 -c maintenance.auto=false add <paths>
   git -c gc.auto=0 -c maintenance.auto=false commit -F - <<'EOF'
   ...
   EOF
   git -c gc.auto=0 -c maintenance.auto=false checkout -b <branch> origin/main
   git -c gc.auto=0 -c maintenance.auto=false push -u origin <branch>
   ```
3. The background `gc`/`repack` on the shared object store use their OWN locks
   (`gc.pid`, objects pack lock) — separate from the worktree `index.lock` — so
   they don't block *reads*; only your index *writes* contend. Disabling
   auto-maintenance on your commands removes the collision.

## Verification
The same `add`/`commit`/`checkout` that was failing now succeeds, and it stays
fixed across subsequent commands (no recurrence) — because none of them spawns a
new maintenance run.

## Gotcha — the flags MUST be inline, not a shell variable
`GIT="git -c gc.auto=0 -c maintenance.auto=false"; $GIT add …` FAILS in zsh with
`command not found: git -c gc.auto=0 …` — zsh tries to exec a binary literally
named "git -c …". Write the flags inline on each invocation (or use a shell
function / array), never a string variable.

## Notes
- This is the "stale lock files — separate pattern" that
  `worktree-index-corrupt-async-post-commit-hook` explicitly defers to. That
  skill is for `fatal: unable to read <sha>` / cache-tree corruption from a
  crashed async **post-commit hook**; THIS skill is for a recurring **lock file**
  from auto-**maintenance**. Same family (worktree + background git), different
  cause + different fix. See also: `async-doc-hook-autodocs-worktree-locks-branch-checkout`.
- You can also disable it repo-wide for the session
  (`git config maintenance.auto false; git config gc.auto 0`) but per-command
  inline flags are safer (don't mutate shared config other worktrees read).
- Don't kill the running `gc`/`repack` — let them finish; they're not the
  blocker once your commands stop spawning new ones.
- **Sibling cause — killed parallel-session commit (not auto-maintenance).** In a worktree
  shared by multiple concurrent Claude sessions, a session whose `git commit` is killed
  mid-operation leaves a **0-byte** `index.lock` (it died before writing the index snapshot)
  that NEVER clears on its own and blocks EVERY session. Same `Unable to create index.lock`
  symptom, different root cause: it does NOT recur after `rm` (it's a one-shot orphan, not the
  maintenance loop). The Step-1 forensic test (lsof-unheld + 0-byte + minutes-old mtime)
  identifies BOTH causes as safe-to-remove; removing it unblocks the parallel sessions too.
  Always stage by explicit path / never `git add -A` in a shared worktree, so a parallel
  session's uncommitted work isn't swept into your commit (or yours into theirs).
  (Confirmed 2026-06-23: a 9-min-old 0-byte lock from a parallel session's killed commit
  blocked all commits; forensically confirmed stale + removed; all sessions resumed.)
