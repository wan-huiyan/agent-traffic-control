---
name: barryu-pr-conflict-site-regen
description: |
  Resolve rebase/merge conflicts in the the-project-repo repo when an old PR is
  being merged into a much-newer main. Use when: (1) `git rebase origin/main` or `git merge
  origin/main` reports CONFLICTs limited to `docs/generate_tracker.py`,
  `docs/site/index.html`, `docs/site/roadmap.html`, `docs/site/active-sprint.html`, or
  `docs/site/assets/site.{css,js}`, (2) you are cleaning up stale PRs authored in earlier
  sessions, (3) an add/add conflict appears in `docs/overnight/<date>/state/*.json` or
  `docs/handoffs/session_NNN_*.md` because both branches wrote the same session artefact. Covers
  the "union the generator, regenerate the HTML" playbook discovered while clearing 12 open PRs
  in Session 102. v1.3.0 (2026-05-08) adds Step 2a (ID-collision: your Item() ID claimed on
  main → renumber to next free ID + propagate rename to PR body / commit msgs / handoff)
  and Step 2b (recurring-rebase loop in dense parallel-PR windows, with `gh pr merge --auto`
  footgun warning for solo-contributor repos without required-status-check branch protection).
  v1.4.0 (2026-05-08, an earlier session) adds Step 2c (silent ID collision: two Items with same ID at
  different file positions produce NO rebase conflict but still collide logically; audit
  via `grep -c | sort | uniq -c | sort -rn` post-rebase AND post-merge — the id-fn
  favicon-vs-an earlier session-retro case where collision was only caught in the next session's
  handoff PR via `wc -l` audit, not at rebase time).
author: Claude Code
version: 1.4.0
date: 2026-05-08
---

# Generated-Site-File PR Conflict Playbook

## Problem

Almost every commit to `main` in this repo regenerates `docs/site/*.html` via
`docs/generate_site.py`, which reads tracker data from `docs/generate_tracker.py`. A
PR authored N sessions ago and rebased/merged today will **always** conflict on those generated
files, even if the human-authored content has no real overlap with main.

Resolving these conflicts by hand line-by-line wastes time and produces wrong output (stale
roadmap entries, missing categories). Taking only one side loses data — main has newer
categories, the PR has the session-specific Item() that justifies the PR existing.

## Context / Trigger Conditions

Exactly one (or more) of these files in the conflict set:
- `docs/generate_tracker.py` (content conflict — both sides added `Item(...)` entries)
- `docs/site/roadmap.html`, `docs/site/index.html`, `docs/site/active-sprint.html` (content)
- `docs/site/assets/site.css`, `docs/site/assets/site.js` (content)

Plus often:
- `docs/handoffs/session_NNN_handoff.md` or `session_NNN_prompt.md` (add/add — both branches
  wrote a handoff for the same session number, usually because #77 wrote one perspective and
  #78 wrote a richer one for the same an earlier session)
- `docs/overnight/<date>/state/*.json`, `docs/overnight/<date>/track_*/tap_outs.md`,
  `hypothesis_log.md` (add/add — independent branches wrote parallel run state)

## Solution

### Step 1 — Classify the conflict file

For each conflicted file, pick the bucket:

| File type                                              | Resolution                                                                 |
|--------------------------------------------------------|----------------------------------------------------------------------------|
| `docs/site/**/*.html`, `site/assets/*`                 | Take main's version, then regenerate at the end                            |
| `docs/generate_tracker.py`                     | **Hand-union Item() entries** (see Step 2)                                 |
| `docs/handoffs/session_NNN_handoff.md` (add/add)       | Take the richer/canonical narrative (usually the one from the later PR)    |
| `docs/overnight/<date>/**` state files (add/add)       | Take the version from the branch that completed the run                    |
| Human-authored plan/doc files (content)                | Hand-merge normally; these are real conflicts                              |

### Step 2 — Hand-union the generator Item() entries

`docs/generate_tracker.py` contains Python `Item(...)` tuples inside `CATEGORIES` lists.
When two branches add related items (e.g. `id-ax` and `id-ay` for the same session), the
3-way merge produces a conflict marker around the whole block.

**Don't pick one side.** Edit the file so BOTH Item() entries are present and ordered
chronologically. For updated-in-both entries (same `item_id`, different status/notes), adopt
the richer/later narrative — **regardless of which side it's on**. Often it is on main, not
the PR branch, because a later PR updated the same entry after your branch diverged. The rule
is: "most complete story wins," not "PR branch wins." Keep any unique cross-links from the
other side too.

#### Step 2a — (v1.3.0) ID-collision: when YOUR Item() ID has been claimed on main

In a high-throughput PR window, two parallel sessions can independently pick the same
`cat7-7XX` ID for **different** Items. The `<<<<<<< HEAD` block holds main's Item with
*your* ID describing somebody else's work; the `>>>>>>>` block holds your Item with the
same ID. This is NOT the "hand-union both entries" case — it's a name collision.

**Procedure:**

1. List all `cat7-7*` IDs currently in use to find the next free one:

   ```bash
   grep -oE 'Item\("cat7-7[a-z0-9]+"' docs/generate_tracker.py | sort -u | tail -20
   ```

2. **Take main's version of the conflicted file** (NOT a manual hand-union of the conflict
   block — main already has the canonical Item for the ID that collided):

   ```bash
   git checkout --ours -- docs/generate_tracker.py \
                          docs/site/index.html \
                          docs/site/roadmap.html
   ```

   Reminder: in rebase, `--ours = upstream (main)`. Verify with `grep -n "cat7-7XX" docs/generate_tracker.py | head -5` — main's Items should be present.

3. **Insert your Item** at the chronological top of the list with the next free ID. Update
   `name=`, all internal `cat7-7XX → cat7-7YY` self-references, and add a `Renumbered
   cat7-7XX → cat7-7YY during rebase` note in the entry's notes/source_ref.

4. Update **the same renumber** in any committed text that referenced the old ID — your PR
   body, your fixup commit messages, your handoff doc, MEMORY.md draft. The git tree carries
   stale references otherwise.

5. **Re-run `python3.11 docs/generate_site.py`** so the new ID is in `docs/site/*.html`,
   then `git add` the regen output.

#### Step 2b — (v1.3.0) Recurring rebase loop in dense parallel-PR windows

If main is gaining 1+ commits per few minutes (release-day, mass-merge sweep, or several
sessions all squashing within minutes of each other), expect to rebase **multiple times in
a row** before the PR can land. Each rebase may surface NEW collisions that didn't exist on
the previous one.

After every rebase:

```bash
git fetch origin --quiet && git rev-list --left-right --count <branch>...origin/main
```

If `behind` is non-zero again, rebase again immediately. Don't `gh pr edit --body` between
rebases unless the story actually changed — `--body` updates create push churn that loses
to the next merge.

**Force-push hygiene:** always use `--force-with-lease`, never plain `--force`. The lease
catches the rare case of an external commit landing on your remote branch.

```bash
git push --force-with-lease origin <branch>
```

**`gh pr merge --auto` footgun on solo-contributor repos.** With no required-status-check
branch protection configured, `gh pr merge --squash --auto` merges the PR **immediately**
even if CI checks are still IN_PROGRESS — `--auto` means "wait for required checks", and
zero required checks means zero wait. If you want CI to actually gate, either (a) set up
required-status-check branch protection on `main`, or (b) wait for CI to go green first
(`gh pr checks <N> --watch`) and then call `gh pr merge --squash` without `--auto`.
Observed a recent multi-track session 2026-05-08: PR #565 squash-merged 16 seconds after pytest+gitleaks+pip-audit
+trivy entered IN_PROGRESS, all unfinished.

#### Step 2c — (v1.4.0) Silent ID collision: same ID at two file positions, no rebase conflict

Step 2a covers the case where two Items collide in the same diff hunk — the rebase
surfaces a `<<<<<<< HEAD` block and you renumber. **This step covers the case where the
collision is invisible at rebase time:**

- PR A reserves `id-fn` and inserts at line 2960
- PR B reserves `id-fn` (independently — different sub-session, different worktree) and
  inserts at line 2952 (a chronologically earlier "newer" slot in the file's reverse-chrono
  ordering)
- PR A merges first
- PR B rebases onto post-A main: textually, the two Item lines are 8 lines apart with
  unrelated context between them. **Git produces NO conflict.** Your branch lands cleanly
  with two `Item("id-fn", ...)` calls at different line numbers.

The collision is logical, not textual. Rebase conflict detection misses it because git
diffs lines, not parsed AST nodes. Renderer (`generate_site.py`) tolerates duplicate
IDs — both rows just appear in `roadmap.html` with the same ID prefix. The collision
survives until someone runs an explicit ID-uniqueness audit, often N sessions later.

**Audit recipe** — run after EVERY rebase AND after EVERY merge of a tracker-touching PR:

```bash
# Quick uniqueness check — should print no lines if all IDs are unique
grep -oE 'Item\("cat7-7[a-z0-9]+"' docs/generate_tracker.py \
  | sort | uniq -c | sort -rn | awk '$1 > 1'
```

If the recipe prints anything, you have a silent collision. Renumber the second-occurrence
in source-order to the next free ID per Step 2a's procedure (skip the `git checkout --ours`
step — there's no rebase in progress; this is a free-standing fixup PR).

**Where to put the renumber:**

- If discovered DURING a rebase you're already running: roll the rename into the rebased
  commit. No separate PR needed.
- If discovered POST-merge in a clean tree: bundle the rename with the next docs/handoff
  PR you're already opening (cheaper than a dedicated tracker-hygiene PR), AND grep the
  worktree for any external references (`docs/handoffs/*.md`, `MEMORY.md`, prior PR
  bodies via `gh pr view`) that need the same rename to stay consistent.
- If you're in a quiet window with no PR queued: file a dedicated `fix(tracker): resolve
  cat7-7XX collision` PR like an earlier session's PR #578 (5-collision sweep) or its sibling PR #588
  (1 collision absorbed into the next handoff).

**Observed in an earlier session 2026-05-08**: PR #581 (favicon) reserved `id-fn`. PR #585 (an earlier session
retrospective handoff) ALSO reserved `id-fn`. PR #585 merged ~17:55Z, PR #581 rebased
~18:00Z and saw NO conflict on the tracker file (only `docs/site/*.html` had textual
overlap from the regen output). Both Items landed on main. Collision discovered ~25min
later in PR #588 (an earlier session handoff) via `grep | sort | uniq -c` audit; resolved by
renumbering favicon → `id-fs` in the same handoff PR.

### Step 3 — Stage the non-site conflicts

```bash
# For files where you take PR branch's version (--ours during merge main-into-branch)
git checkout --ours -- docs/handoffs/session_100_handoff.md \
                       docs/overnight/2026-04-21/state/status.json \
                       # ...etc
# WARNING: during `git rebase onto=main`, --ours/--theirs are REVERSED from merge.
# In rebase --ours = upstream (main), --theirs = the branch being replayed.
# Always verify with: `git diff --cached <file>` shows expected content before proceeding.

git add <all the files you resolved>
```

### Step 4 — Regenerate site files FROM the merged generator

```bash
python3 docs/generate_site.py
# Output confirms: "✓ site/index.html / ✓ site/roadmap.html / ✓ site/active-sprint.html"
# Plus summary line: "Active sprint: N/M done (XX.X%). Roadmap: N/M done (YY.Y%)."

git add docs/site/roadmap.html docs/site/index.html docs/site/active-sprint.html \
        docs/site/assets/site.css docs/site/assets/site.js
```

This is the key insight: the generator is the source of truth. Once you've hand-unioned the
generator, the HTML output files are fully derived — don't waste effort hand-merging them.

### Step 5 — Commit and verify

```bash
git status  # confirm "All conflicts fixed but you are still merging"
git commit -m "merge: resolve conflicts with main (<list landed PRs>)"
# Pre-commit hook will run syntax check on the generator Python — make sure it passes
```

## Verification

1. `grep -rn "<<<<<<<\|>>>>>>>\|=======" docs/generate_tracker.py docs/site/` returns
   no matches.
2. `python3 -c "import ast; ast.parse(open('docs/generate_tracker.py').read())"` parses
   without error.
3. `python3 docs/generate_site.py` runs and produces the expected summary line.
4. The PR's original Item() entry still appears in `docs/site/roadmap.html` after regen.
5. Any Item() entries that were on main before the merge still appear too.

## Example — Session 102 clearing PR #78

PR #78 had 8 merge conflicts:
- `docs/generate_tracker.py` (content) → hand-union `id-ay` (from main, PR #77's
  CCR env entry) + adopt PR #78's richer `id-ax` completion narrative
- `docs/handoffs/session_100_handoff.md` (add/add, 84 vs 141 lines) → take PR #78 (richer)
- `docs/handoffs/session_101_prompt.md` (add/add) → take PR #78
- `docs/overnight/2026-04-21/state/status.json` (content) → take PR #78 (complete run state)
- `docs/overnight/2026-04-21/state/track_c_status.json` (add/add) → take PR #78
- `docs/overnight/2026-04-21/track_c/state/hypothesis_log.md` (add/add) → take PR #78
- `docs/overnight/2026-04-21/track_c/tap_outs.md` (add/add) → take PR #78
- `docs/site/roadmap.html` (content) → regenerate at end

Result after `python3 docs/generate_site.py`: `Active sprint: 54/55 (98.2%). Roadmap: 170/219
(77.6%).` — both main's categories AND PR #78's items present.

## Notes

- **Rebase `--theirs`/`--ours` is reversed from merge.** In a rebase onto main, `--ours` = main,
  `--theirs` = the branch being replayed. Easy to get backwards — always inspect the staged
  diff with `git diff --cached <file> | head -20` before continuing the rebase.
- **Superseded-PR detection:** before rebasing, run `git diff --stat
  origin/main...origin/<branch>` and `git log origin/main..origin/<branch> --oneline`. If the
  only unique commits are site-regen and the claimed-new files are already on main
  (`git ls-tree -r origin/main --name-only | grep <key-file>`), close the PR as superseded
  rather than rebasing.
- **Pre-commit hook on this repo** runs Python syntax checks on staged `.py` files and blocks
  commit on failure. A malformed `generate_tracker.py` (missing `)` after Item(), trailing
  `=======` markers) will fail the hook — fix and re-stage.
- **Infra-commit hook** fires post-commit whenever cloudrun/dataform/docker paths are touched —
  false positive if your merge only modified docs. Ignore.
- For **add/add handoff conflicts** on the same session number, the pattern is typically: one
  branch (the earlier-merged one) wrote a narrow postmortem, the other (the full-run branch)
  wrote the complete arc. Almost always take the full-run version; the narrow one's unique
  content is already captured in its standalone plan docs (`docs/plans/...`).
- **Session prompt filename collision** — two parallel session tracks can independently write
  `session_N+1_prompt.md` for *different* purposes (e.g., one track writes an earlier session for a
  dashboard-bug ship cluster; another writes an earlier session for a v6-findings implementation). These are
  NOT the same file — keep both, renaming the later-discovered one to `session_N+2_prompt.md`.

  **(v1.2.0) Don't stop at N+1 — check the entire forward range.** A single auth/IA/etc. track
  can write multiple future-session prompts in one commit (an earlier session prompt + an earlier session prompt + an earlier session
  prompt all from one auth-design session). If you only audit `session_<N+1>_prompt.md` and
  rename to N+2, you'll silently overwrite their N+2 prompt during your rebase. The discovery
  symptom is brutal: `git rebase origin/main` reports `Successfully rebased` with NO conflict
  flagged, your branch's create wins, and the other track's content is only recoverable from
  the pre-merge blob. Audit recipe before writing any next-session prompt:

  ```bash
  # List ALL session prompts on origin/main; pick a number > max
  git ls-tree origin/main docs/handoffs/ | grep -oE 'session_[0-9]+_prompt\.md' \
    | sort -V | tail -10
  # Then verify your chosen number is unclaimed
  git ls-tree origin/main -- docs/handoffs/session_<YOUR_PICK>_prompt.md
  # (empty output = available)
  ```

  **Recovery recipe if you discover the regression POST-MERGE:** the silently-overwritten
  content is still in the pre-merge blob. Find the commit that originally added the file:

  ```bash
  git log --all --oneline --follow -- docs/handoffs/session_<N>_prompt.md
  # Identifies <orig-commit> = the one BEFORE your overwrite landed
  git show <orig-commit>:docs/handoffs/session_<N>_prompt.md \
    > docs/handoffs/session_<N>_prompt.md             # restore byte-identical
  cp docs/handoffs/session_<N>_prompt.md \
     docs/handoffs/session_<N+1>_prompt.md            # save for diff if needed
  # ... move your prompt to a new free number, update its title + filename note,
  # update all cross-references in handoff docs, MEMORY.md, sessions_archive.md,
  # future_sessions_plan.md. Open a recovery PR.
  ```

  Verify recovery with `diff <(git show <orig-commit>:docs/handoffs/session_<N>_prompt.md) \
  docs/handoffs/session_<N>_prompt.md` — empty output means byte-identical restore.

  **Why git's rebase didn't flag it as a conflict:** when both sides ADD a file at the same
  path with different content, the 3-way merge SHOULD detect add/add. Empirically (an earlier session,
  2026-05-06): a `git rebase origin/main` with a fresh commit that creates a same-named file
  succeeded silently with no conflict markers. The exact cause isn't fully understood (likely
  a strategy-option default or merge.renames heuristic that treated it as a fast-forward
  pickup of the upstream version, then re-applied my add on top). Doesn't matter — **the
  audit MUST happen before the rebase, not as a conflict-handling step during it.** Trusting
  rebase output is not safe for this class.

## References

- `docs/generate_site.py` — the regenerator (reads `generate_tracker.py`, writes
  site/*.html)
- `docs/generate_tracker.py` — source of truth for Items, `CATEGORIES`
- Session 102 PR-cleanup session (2026-04-23) where this playbook was validated across 5
  consecutive conflict resolutions (PRs #75, #65, #55, #78)
- **Parent skill:** `merge-conflict-generated-files` — the project-agnostic version of this
  playbook (applies to any project with a source-of-truth generator + committed outputs)
