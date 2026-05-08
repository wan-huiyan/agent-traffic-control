---
name: subagent-bash-cd-wrong-worktree
description: |
  Diagnose and prevent subagents committing to the wrong git branch when dispatched in
  multi-worktree setups. Use when (1) you dispatched a subagent (Task tool) with bash
  steps like `cd <target-worktree> && git commit ...`, (2) the subagent reported DONE
  with a real-looking commit SHA, (3) `git log` on the target worktree doesn't show
  that SHA — but `git branch --contains <sha>` finds it on a sibling branch
  (typically the parent repo's checked-out branch). Root cause: each Bash tool call
  starts in a shell whose cwd is reset to the agent's launch directory; `cd` in one
  call does not persist to the next. The subagent silently runs `git commit` from the
  launch directory's checked-out branch, not the worktree it intended.
author: Claude Code
version: 1.0.0
date: 2026-05-05
---

# Subagent + bash `cd` + multi-worktree → commit lands on wrong branch

## Problem

You dispatched a subagent (via the Task tool) to do work in a specific git worktree.
You wrote bash steps like:

```bash
cd /path/to/.claude/worktrees/feature-X
pip install -r requirements.txt
git add foo.py
git commit -m "..."
```

The subagent reports DONE with a commit SHA. The SHA is real (`git rev-parse <sha>`
resolves) but `git log` on `feature-X`'s branch does not show it. `git branch
--contains <sha>` reveals the commit landed on whatever branch was checked out
in the **parent repository directory** (not your target worktree).

**Why subagents miss this:** they trust their own `cd` step to have worked, then
call `git commit` and see a successful commit message echoed by Git. Git commits
the staged change to whatever HEAD is in the cwd Git resolves, which (after the
shell reset) is the launch directory's HEAD — not the worktree's.

## Trigger Conditions

- Multi-worktree git setup (`git worktree list` shows ≥ 2 entries)
- Subagent dispatch (general-purpose Task tool, any model)
- Subagent prompt instructed `cd <abspath> && <commands>` for shell steps
- Subagent reported DONE with a SHA that doesn't appear in `git log` on the
  target worktree's branch
- Subagent's first bash call shows the `cd` worked; subsequent calls silently
  ran in a different cwd

## Root Cause

Each Bash tool call starts a fresh shell. Working directory persists *within* a
single tool call (chained with `&&` or `;`) but resets between calls. The
agent's launch cwd is whatever the harness set when spawning it — typically the
parent repository or whatever directory the controller was in when it called
the Task tool. A `cd` in tool call N does not affect tool call N+1.

`git commit` resolves HEAD via `cwd → .git → HEAD`. From the launch cwd, that's
the parent repo's currently-checked-out branch.

## Solution — Prevention

When dispatching a subagent that needs to operate inside a specific worktree,
write the prompt so **every** bash step is independent of cwd:

### 1. Use `git -C <abspath>` for every git command

```bash
git -C /path/to/.claude/worktrees/feature-X add foo.py
git -C /path/to/.claude/worktrees/feature-X commit -m "..."
git -C /path/to/.claude/worktrees/feature-X log --oneline -3
```

### 2. Use absolute paths for file operations

```bash
pytest /path/to/.claude/worktrees/feature-X/tests/
ls /path/to/.claude/worktrees/feature-X/src/
```

Or chain everything in one tool call with `&&`:

```bash
cd /path/to/.claude/worktrees/feature-X && pytest tests/ && git add . && git commit -m "..."
```

### 3. Tell the subagent explicitly

In the dispatch prompt, include:

> The shell does not persist cwd between Bash tool calls. Use
> `git -C /absolute/path/to/worktree` for every git command, and absolute
> paths for all file operations. Do not rely on `cd` from a previous call.

### 4. Skip the subagent for trivial mechanical tasks

If the task is a 2-line file edit + `git add` + `git commit`, controller-side
execution is more reliable. The subagent overhead doesn't pay off for
deterministic well-specified work; it pays off for tasks that benefit from
fresh context (research, multi-file refactors, ambiguous specs).

## Solution — Detection

After every subagent that committed work in a worktree, verify before
proceeding:

```bash
# 1. Check the worktree's branch tip is what you expect
git -C /path/to/worktree log --oneline -1

# 2. Look up the claimed SHA — if it exists on a different branch, you've
#    been bitten:
git rev-parse <claimed-sha>            # does it resolve?
git branch --contains <claimed-sha>    # which branch holds it?

# 3. If the SHA is not in the worktree's branch:
#    - Identify the branch that wrongly received the commit
#    - Reset that branch back to its prior tip:
git -C /path/to/parent reset --hard <prior-sha>
#    - Cherry-pick onto the correct worktree branch:
git -C /path/to/worktree cherry-pick <stray-sha>
```

## Verification

After applying the fix, the recovery commit SHA shows in `git log` on the
target worktree's branch, and the parent repo's branch is back to its prior
tip. `git branch --contains <recovery-sha>` shows only the target worktree's
branch.

## Example

Real failure mode that produced this skill:

```text
Controller dispatched: "cd /Users/.../worktrees/auth-outside-google && ..."
Subagent reported:    Status: DONE, commit SHA: e5b4b14d
Controller verified:  git -C /Users/.../worktrees/auth-outside-google log
                      → HEAD still 3345ac5e, e5b4b14d not present
Controller searched:  git branch --contains e5b4b14d
                      → docs/s123-followup-issue212-prompt
                        (the parent repo's currently-checked-out branch)
```

Recovery: `git reset --hard 3345ac5e^` on the parent repo (well, on its
specific branch), cherry-pick the auth commit onto the target worktree.

## Notes

- This is a Bash-tool-specific behavior; the subagent itself is not "wrong" —
  it's a shell semantics issue at the harness layer.
- The most insidious aspect is that the commit succeeds (no error), so a
  subagent doing self-review (`git log` in a chained call) will see its own
  commit and report DONE legitimately. The bug only surfaces when controller
  inspects the target worktree's branch, which the subagent didn't.
- Same root cause hits any state set in tool call N expected to persist to N+1:
  environment variables, virtualenv activation, ssh-agent identities. `cd` is
  just the most common manifestation.
- Consider adding the "use `git -C`, not `cd`" instruction to your project's
  CLAUDE.md if you regularly dispatch subagents into worktrees.

## See Also

- `gh-pr-merge-worktree-checkout-trap` — different worktree gotcha (sibling
  worktree blocks `gh pr merge --delete-branch`)
- `using-git-worktrees` — creating worktrees safely
- `worktree-historical-test-replay-missing-dirs` — pytest exit 4 in worktrees
  when historical SHAs reference paths that no longer exist
