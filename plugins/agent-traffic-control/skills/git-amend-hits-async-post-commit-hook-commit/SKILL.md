---
name: git-amend-hits-async-post-commit-hook-commit
description: |
  Use when a `git commit --amend` silently rewrites the WRONG commit in a repo
  that has an async/background post-commit hook. Trigger: after a normal commit,
  `git log` shows an unexpected extra commit on top that a background hook
  created (`[auto-docs] ...`, a docs/site regen, a changelog/checkbox tick) —
  and a later `--amend` folds your change into THAT hook commit instead of your
  feature commit. The amend reports success; no error. Also use proactively
  before instructing subagents to `--amend` in any repo with a background
  post-commit hook. Sibling of git-add-u-after-async-post-commit-hook,
  git-rebase-stalls-async-post-commit-hook,
  worktree-index-corrupt-async-post-commit-hook.
author: Claude Code
version: 1.0.0
date: 2026-05-22
disable-model-invocation: true
---

# `git commit --amend` hits the async post-commit hook's commit

## Problem

A repo has an **async post-commit hook** — it fires in the background after a
commit and creates its OWN follow-up commit (auto-generated docs, a site
regen, a changelog or plan-checkbox tick). If you (or a subagent) run
`git commit --amend` after that hook has fired, `--amend` rewrites **the
hook's commit**, not your work commit. Your change's content is folded into a
commit titled e.g. `[auto-docs] ...`; your real `feat(...)` commit is left
untouched. The amend "succeeds" — no error — so it is easy to miss.

## Context / Trigger Conditions

- The repo has a background/async post-commit hook (look for a `post-commit`
  hook that backgrounds work, or commits with prefixes like `[auto-docs]`,
  `chore: regenerate site`, etc. appearing without a human authoring them).
- You ran `git commit`, then later `git commit --amend` (often a code-review
  fix, a typo fix, or "tidy the last commit").
- `git log` shows HEAD's message is the hook's, not yours — and your change is
  inside that hook commit.
- Especially common in **subagent-driven development**: a fix subagent is told
  to `--amend` its fix, but the async hook committed between the implementer
  subagent's commit and the fix subagent running.

## Solution

1. **Never `git commit --amend` in a repo with an async post-commit hook** —
   and never instruct a subagent to. Use a fresh `git commit`. A clean extra
   commit is harmless (it squash-merges away); a misplaced `--amend` is silent
   structural corruption.
2. **Re-read `git log` yourself after every commit.** Do not trust an
   agent-reported SHA — the async hook shifts HEAD after the agent reports.
   Determine BASE/HEAD for the next step by reading `git log --oneline`.
3. If you genuinely must amend: first confirm HEAD is YOUR commit
   (`git log -1 --format='%s'`), and ideally disable the hook for the
   operation.

## Verification

`git log --oneline -3` immediately after committing — confirm your commit
message sits on the commit you intend, and note any `[auto-docs]` / regen
commit the hook added on top.

## Example

A code-quality-fix subagent was told `git commit --amend --no-edit` to fold a
fix into the implementer's `feat(library): ...` commit. By the time it ran,
the repo's async `[auto-docs]` hook (which ticks plan checkboxes) had already
committed on top. `--amend` rewrote the `[auto-docs]` commit — the fix's
content was committed and correct, but attributed to the wrong commit; the
`feat(...)` commit was untouched. Caught only by reading `git log` and
noticing HEAD's message did not match the work.

## Notes

- The fix's *content* is not lost — only the commit *structure* is wrong. This
  makes it easy to miss and harmless under squash-merge, but it corrupts a
  rebase-merge workflow and confuses `git log` archaeology.
- Detection heuristic: right after your commit, `git log` shows a commit you
  did not author.
- See also the sibling skills for other failure modes of the same async-hook
  pattern (`git add -u` racing the hook, worktree index corruption, rebase
  stalls).
