---
name: synthetic-id-collision-rebase
description: |
  Fix the "I claimed id-bg, they claimed id-bg, theirs merged first" failure
  mode when rebasing a PR after parallel sessions land mid-flight. Use when:
  (1) rebasing a stale PR onto current main produces a conflict in an append-only
  register file (tracker entries, ADR `NNNN-` prefixes, migration filenames, OpenAPI
  operationIds, error codes, lessons.md `## N.` numbering), (2) BOTH your branch
  and a freshly-merged branch added an entry under THE SAME synthetic ID — the
  collision is namespace, not just text, (3) plain "accept both sides" yields two
  rows with identical IDs that violate the file's invariant, (4) multiple Claude
  Code sessions share a working tree and each picked "next free letter" from their
  local view of the file. Prescribes a reroll workflow: scan ALL taken IDs in
  current main, pick truly-next-free, replay only your entry under the new ID,
  regenerate any derived artifacts (site, indexes), force-push.
author: Claude Code
version: 1.0.0
date: 2026-04-27
---

# Synthetic ID Collision During Multi-Session PR Rebase

## Problem

You opened a PR that adds an entry to an append-only register — `Item("id-bg", ...)` in a roadmap tracker, `0017-foo.md` ADR, `V025__add_index.sql` migration, `## 144. ...` in `lessons.md`, `errcode: "E_QUOTA"` in an error catalog. You picked the ID by reading the file and grabbing the next free slot.

Meanwhile, a parallel session — or a co-author, or your own work in another worktree — also picked the same ID. **Their PR merged first.** Now your PR is `mergeable: CONFLICTING / DIRTY`, and even after reading their version, the conflict isn't really about content alignment — it's that **the synthetic ID itself is taken**. A 3-way merge that "accepts both sides" produces two rows with identical IDs, which violates the file's primary key.

This is a particularly nasty failure because:
1. The conflict resolution `--theirs` keeps their entry under the ID you wanted; your work is silently dropped.
2. The conflict resolution `--ours` overwrites their already-merged entry; your work shows up under their ID, blowing away their data.
3. The naive "merge both" appends two `id-bg` rows; tooling that keys on the ID picks the first, hides the second.

## Context / Trigger Conditions

All four hold:
1. Your PR is conflicting after a mid-flight merge from another branch (often: another Claude Code session sharing the same working tree).
2. The conflicting file is an **append-only register** keyed by a synthetic ID, where the ID is supposed to be unique. Common patterns:
   - Roadmap/backlog trackers: `Item("id-bg", ...)`, `Item("id-bh", ...)`
   - ADRs: filename prefix `NNNN-` (`0016-foo.md`, `0017-bar.md`)
   - DB migration files: `V025__create_users.sql`, `V026__add_index.sql`
   - Sequential lessons: `## 142. ...`, `## 143. ...` in `lessons.md`
   - OpenAPI operationIds, GraphQL error codes, feature flags with sequential names
3. `git diff origin/main..HEAD -- <file>` shows your block adding the same ID their already-merged block adds.
4. The file has a derived/regenerated artifact (HTML site, sphinx index, README badge, openapi.json) that was also touched on both sides — meaning the regenerator runs on whichever wins the merge.

## Solution

**Reroll your ID. Don't try to resolve in-place.**

### Step 1 — Confirm the namespace collision

After `git fetch origin main && git rebase origin/main`, when conflict surfaces:

```bash
# Show your ID + theirs in the conflict block
git diff --name-only --diff-filter=U   # which files conflict
grep -n "<<<<<<<\|=======\|>>>>>>>" <register-file> | head -20
```

If you see your `Item("id-bg", ...)` and their `Item("id-bg", ...)` in the same conflict hunk under the same key, you have a namespace collision, not a content collision.

### Step 2 — Find the truly-next-free ID on current main

```bash
# For tracker/Item-style files
grep -oE "id-b[a-z]" docs/generate_tracker.py | sort -u
# Pick the next letter alphabetically: if ..bj is taken, you take bk

# For ADR files
ls docs/decisions/ | grep -oE "^[0-9]{4}" | sort -u | tail -3
# Pick max+1

# For migrations
ls db/migrations/ | grep -oE "^V[0-9]+" | sort -V | tail -3

# For lessons.md
grep -E "^## [0-9]+" .claude-memory/lessons.md | tail -3
# Pick max+1
```

**Critical:** scan the file as it exists on current `main`, NOT your local pre-rebase view. Your local thinks `bg` is free; main says `bg` through `bj` are all taken now.

### Step 3 — Abort the rebase, reset clean, replay your entry under the new ID

The cleanest path is to reset to current main and cherry-pick only the substantive part of your change, then re-apply the register entry under the new ID as a separate commit.

```bash
git rebase --abort                                      # back out of the conflict
git reset --hard origin/main                            # clean slate
git cherry-pick <your-substantive-commit-sha>           # the actual feature/doc work
# Now manually add the register entry under the NEW ID, regenerate derived artifacts
# (site/index/openapi.json/etc.), commit as a fresh "tracker reroll" commit.
```

If your branch had multiple commits, cherry-pick each substantive commit, then add ONE final "tracker reroll" commit that puts the register entry under the new ID + regenerates derived artifacts.

### Step 4 — Regenerate derived artifacts against the new state

The site/HTML/openapi/index file regenerator must run against the post-rebase state, not the pre-rebase state. The file SHA pre-regen will mismatch what's on main even if your register entry's content is identical:

```bash
python3 docs/generate_site.py             # tracker → site
# or whatever the project's regen command is
git add docs/generate_tracker.py docs/site/
git commit -m "chore(tracker): add <new-id> for <feature> (PR #N reroll)"
```

### Step 5 — Force-push and refresh the PR description

```bash
git push --force-with-lease origin <branch>
gh pr edit <N> --body "$(cat <<'EOF'
... existing summary ...

## Status — rebased <date>
This branch was rebased onto origin/main after PR #<X> shipped <feature> and
took the original <id>. Re-rolled to <new-id>. New 2-commit history:
1. <SHA> — the substantive change (untouched)
2. <SHA> — fresh register entry (<new-id>) + derived-artifact regen
EOF
)"
```

`--force-with-lease` (not `--force`) prevents stomping any push that another session may have made to your branch in the meantime.

### Step 6 — Verify and merge

```bash
gh pr view <N> --json mergeable,mergeStateStatus
# Expect: MERGEABLE / CLEAN
gh pr merge <N> --squash --delete-branch
```

## Verification

- `gh pr view <N>` returns `mergeable: "MERGEABLE"`, `mergeStateStatus: "CLEAN"`
- The merged main contains BOTH your entry (under the new ID) AND the parallel session's entry (under the original ID); neither overwrote the other
- The regenerated artifact (site/index/etc.) reflects both entries; tooling that keys on the synthetic ID returns 1:1 mapping with no duplicates
- `grep -c "<new-id>" <file>` returns 1 (or however many references you intended)

## Example

This session, 2026-04-27:

- Opened PR #118 with `id-bg` for "an earlier session docs+tests carry-over" at 15:11 UTC
- Parallel session opened a different PR with `id-bg` for "an earlier session Run 2 + privacy-regulation fix" — merged first at 14:29 UTC
- Subsequent PRs took `id-bh` (Streamlit decommission), `id-bi` (deposit-optional), `id-bj` (an earlier session handoff) on main
- Rebased PR #118 → conflict on `Item("id-bg", ...)` block + 3 site files
- Reset to origin/main, cherry-picked substantive commit (4 docs/test files), added new commit with `id-bk` + regenerated `docs/site/{index,roadmap}.html`
- Force-pushed → CLEAN → merged

End state: main has `id-bg` (parallel session's work), `id-bh`/`bi`/`bj` (subsequent sessions), `id-bk` (mine). All entries preserved, all distinct IDs, regenerated site reflects all of them.

## Notes

- **Root cause is shared working tree.** Multi-session work without `claude --worktree <name>` (Claude Code) or equivalent worktree isolation creates this exact failure mode. The recovery here is the symptomatic fix; the structural fix is per-session worktrees.
- **The collision is invisible until merge time.** Both sessions' local view of the file shows their ID as "next free." Only when one merges first does the other's ID become unavailable. There's no useful pre-merge linter for this — the truth lives on origin/main.
- **Append-only registers are vulnerable; replace-style files are not.** A YAML config edit doesn't have this issue because the same key on both sides naturally 3-way-merges. Sequential ID assignment is what creates the namespace.
- **For ADR-style files (one ADR per filename), the collision is at the filesystem level**: `0017-feature-A.md` from your branch + `0017-feature-B.md` from theirs both want to exist as the 17th ADR. Resolution is the same: rename yours to `0018-feature-A.md`.
- **For lessons.md sequential numbering**: if you're at `## 144` and they shipped `## 144` first, you become `## 145`. The reroll edit is in one place but you may need to update cross-references (`L-an earlier session-144` → `L-an earlier session-145`) elsewhere.
- **See also:** `pr-conflict-from-mid-flight-merges` skill covers the broader recipe for any mid-flight-merge conflict; this skill specializes the namespace-collision case where the file conflict isn't really about content.

## References

- Companion skill: `~/.claude/skills/pr-conflict-from-mid-flight-merges/SKILL.md`
- Parallel-session-isolation root-cause fix: Claude Code's built-in `claude --worktree <name>` flag (avoids shared-working-tree race conditions entirely)
