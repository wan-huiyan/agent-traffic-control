---
name: main-bash-cwd-persists-nested-worktree
description: |
  Prevent and diagnose nested git worktrees created at the wrong filesystem path when
  orchestrating parallel work from the main Claude Code agent. Use when (1) you ran
  `git worktree add .claude/worktrees/<name> ...` from the main agent's Bash tool,
  (2) `git worktree list` shows the new worktree at an unexpected nested path like
  `.claude/worktrees/<previous-worktree>/.claude/worktrees/<name>` instead of the
  intended top-level location, (3) a subagent dispatched to the intended path reports
  "worktree path mismatch" or operates from a longer nested path. Root cause: the
  main agent's Bash tool **persists cwd between calls** (per its docstring: "The
  working directory persists between commands"). An earlier `cd /abs/path && cmd`
  changes the main shell's cwd; a later `git worktree add <relative-path> ...`
  resolves against that persisted cwd rather than the project root, silently creating
  nested layouts. This is the **inverse** of the subagent variant
  (subagent-bash-cd-wrong-worktree) — subagent shells reset per call, main shell
  doesn't.
author: Claude Code
version: 1.0.0
date: 2026-05-26
---

# Main-agent Bash cwd persistence → nested worktrees at wrong path

## Problem

You're orchestrating multiple parallel-dispatch subagents, each in its own git worktree. From the main agent's Bash tool you do:

```bash
git worktree add .claude/worktrees/track-A origin/main -b feat/track-A
# ... dispatch Track A subagent ...
# ... investigate codebase ...
cd /path/to/repo/.claude/worktrees/track-A && grep -rn "foo" src/   # persists cwd!
# ... time passes, you dispatch Track B ...
git worktree add .claude/worktrees/track-B origin/main -b feat/track-B
```

You expect `track-B` at `<repo>/.claude/worktrees/track-B`. Instead `git worktree list` reports it at `<repo>/.claude/worktrees/track-A/.claude/worktrees/track-B` — nested inside the Track A worktree.

Branches, commits, and pushes still work (git resolves them via `.git/worktrees/<name>` metadata regardless of disk location), but:
- Dispatched subagents pointed at the intended path will report "worktree path mismatch."
- Cleanup (`git worktree remove .claude/worktrees/track-B`) from the project root won't find it.
- Per-worktree caches, venvs, and uploads end up under the wrong parent directory.

## Context / Trigger conditions

- Main agent runs more than one `git worktree add` in the same session.
- Between worktree-add calls, the main agent ran a Bash command that included a `cd` to a path other than the project root.
- The later `git worktree add` uses a **relative** path (e.g., `.claude/worktrees/<name>`).
- Symptom: `git worktree list` shows nested paths, OR a subagent given the intended path can't find its worktree, OR `pwd` inside a subagent reports a longer-than-expected path.

The Bash tool's own description says it: *"The working directory persists between commands, but shell state does not."* This is the opposite of subagent Bash, which resets cwd per call (see `subagent-bash-cd-wrong-worktree`).

## Solution

Three reliable mitigations, in order of preference:

1. **Always pass an absolute path to `git worktree add`** from the main agent.
   ```bash
   git worktree add /Users/huiyanwan/Documents/AMC-handover/.claude/worktrees/track-B origin/main -b feat/track-B
   ```
   This is the cleanest fix and is robust against any cwd drift.

2. **Reset cwd to project root** in the same chained call before any `git worktree add` with a relative path:
   ```bash
   cd /Users/huiyanwan/Documents/AMC-handover && git worktree add .claude/worktrees/track-B origin/main -b feat/track-B
   ```

3. **Create ALL worktrees up-front in a single batch** at the start of the session, before any other Bash commands that might `cd`.

When dispatching parallel subagent prompts, also bake an absolute-path verification step into each prompt:

```
First action: verify worktree path matches expectation.
cd /Users/huiyanwan/Documents/AMC-handover/.claude/worktrees/<name>
pwd  # MUST end in <name>; STOP and report if it doesn't
git rev-parse --abbrev-ref HEAD  # MUST be feat/<name>
```

## Verification

After creating a worktree, immediately:

```bash
git worktree list | grep <name>
```

The reported path must NOT be nested under another worktree. If it is, before any subagent dispatch:

```bash
# Move it to the correct location (requires admin; or just remove + re-add)
git worktree remove <wrong-nested-path>
git worktree add /abs/path/to/.claude/worktrees/<name> origin/main -b feat/<name>
```

## Example

**What went wrong (Session 15, AMC-handover):**

```bash
# Main agent at /Users/huiyanwan/Documents/AMC-handover (project root)
git worktree add .claude/worktrees/s15-lows-bundle origin/main -b feat/s15-lows-bundle
# → created at .../AMC-handover/.claude/worktrees/s15-lows-bundle ✅

# Later, investigation:
cd /Users/huiyanwan/Documents/AMC-handover/.claude/worktrees/s15-lows-bundle && grep "_JINJA_ENV" src/
# → main shell cwd is now inside s15-lows-bundle worktree

# Even later, second worktree:
git worktree add .claude/worktrees/s15-csv-upload origin/main -b feat/s15-csv-upload
# → created at .../s15-lows-bundle/.claude/worktrees/s15-csv-upload ❌
```

**Fix applied in that session:** none mid-session (PRs all pushed correctly via branch refs). The lesson is to use absolute paths next time.

## Notes

- Branch and push behavior are NOT affected because git tracks worktrees by `.git/worktrees/<name>` metadata, not by filesystem path. So this bug is silent — you only notice when a subagent reports a path mismatch or when you try to `git worktree remove` from the project root.
- This is a property of the Claude Code Bash tool specifically. Other tools (e.g., Edit, Write, Read) don't have a persistent cwd — they take absolute paths or resolve against the project root.
- The subagent variant (`subagent-bash-cd-wrong-worktree`) describes the opposite failure mode: subagent shells reset cwd per call, so a `cd` followed by `git commit` in a *separate* Bash call commits to the parent repo's HEAD. Both are real, and the fix is the same: use absolute paths and verify with `pwd` before any state-changing command.

## References

- Claude Code Bash tool docstring: "The working directory persists between commands, but shell state does not."
- Related skill: [subagent-bash-cd-wrong-worktree](../subagent-bash-cd-wrong-worktree/SKILL.md) — the inverse failure mode in subagent shells.
- Related skill: [using-git-worktrees](../using-git-worktrees/) — general worktree workflow.
