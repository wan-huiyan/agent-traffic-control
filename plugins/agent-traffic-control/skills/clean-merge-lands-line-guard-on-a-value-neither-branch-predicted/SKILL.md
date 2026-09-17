---
name: clean-merge-lands-line-guard-on-a-value-neither-branch-predicted
description: |
  Two branches each contain a guard, test or document that pins a line NUMBER in
  a third file, each side correctly re-aims that number for its own tree, and
  git merges both edits with NO conflict — leaving a merged tree whose real line
  can be neither number. Use when: (1) two parallel PRs both insert or delete lines
  in a file that other files cite by line, (2) a merge you just completed
  touched a test or page that resolves `path:NNN` and the merge was clean, (3) a
  guard file in your merge result looks "freshly fixed" — touched minutes ago by
  a competent session for this exact reason — and leaving it alone feels like
  respecting their work, (4) you are tempted to compute the new line by adding
  your insertion's size to the old one. A clean auto-merge is evidence of
  nothing here: conflict is the loud case and this is the quiet one. Re-grep the
  anchor TEXT on the merged bytes, run the guards before the long test legs, and
  never carry an offset. NOT for a merge conflict in a generated file (regenerate
  it instead) and NOT for a stale citation in a dated document, which is correct
  as of its own commit.
author: Claude Code
version: 1.0.0
date: 2026-09-17
disable-model-invocation: true
---

# A Clean Merge Lands a Line Guard on a Value Neither Branch Predicted

## Problem

A repo has guards that pin line numbers: a test asserting that `handler.py:992`
still reads `if name not in REGISTRY:`, a published page citing
`handler.py:1559`, a docstring citing `handler.py:1582` for the line its own
example came from. They exist because the statement is stable and its address
is not.

Two branches are open. Branch A inserts 22 lines into `handler.py` and, being
careful, re-aims the three citations that moved — for **its** tree. Branch B
adds 64 lines to a different file and re-aims the same two guard files — for
**its** tree. Each side is right. The edits are in different lines of the same
files, so git merges them **cleanly**.

The merged tree is the first tree either set of numbers has ever been read
against, and it can agree with neither. Nothing conflicts, no gate is red at
merge time, and the guard fails later — on the base branch, and then on every
branch queued behind it.

**The trap is psychological rather than technical.** After the merge, those
guard files look freshly fixed: modified minutes ago, by a competent session,
for precisely this reason. Leaving them alone reads as respecting somebody's
work rather than as skipping a check.

## Context / Trigger Conditions

- A merge or rebase you just completed was **clean**, and it touched a file that
  another file cites as `path:NNN`
- Two parallel branches both changed the *size* of a commonly-cited file
  (inserted a block, moved a function, deleted a guard)
- `git log --oneline <base>..origin/main -- <cited file>` shows the other side
  touched it too
- A test name or a comment in the diff mentions a line number
- You are about to compute a new line number as `old + lines_I_added`
- A guard file in the merge result has a very recent mtime and a commit message
  saying it fixed citations

## Root cause

Line-number citations are **measurements about one commit**, not pointers. Git
merges *text*, so two edits to different lines of the same file combine without
complaint; it has no idea that both numbers describe the same moving target in a
third file, or that the target moved twice.

This is the same family as a rebase resolving text while leaving values wrong,
and it fails in the quiet direction: the merge is clean, both parents' tests
passed, and the first red appears after landing.

## Solution

### Step 1 — After any merge, re-grep the anchor text on the merged bytes

```bash
# the statement is stable; the address is not. Read the address off the result.
grep -n "if name not in REGISTRY:" handler.py
grep -n "label=field.label"        handler.py
```

Never add your insertion's size to the old number. An offset agrees with one
parent and is wrong about the merge — and it is wrong invisibly, because the
result is a plausible number.

### Step 2 — Run the guards, do not read them

They answer in about a second, and unlike the numbers written in them they are
evaluated against the merged tree:

```bash
# the guard files themselves, before the long legs
python -m pytest <guard test files> -q -p no:cacheprovider
```

If they are red, the rest of the local run is wasted — find out first, not
twenty minutes later.

### Step 3 — Fix the numbers, not the code they point at

Each guard usually says so in its own failure message ("fix the page's citation,
not this test"). Where a *page the owner has already answered on* carries the
citation and may not be edited, the remedy is the opposite: move your inserted
block **below** the cited code so the address resolves again, then re-run the
whole documentation leg, because moving a block shifts every line between its
old and new position.

### Step 4 — Sweep for the numbers you just retired

Those are the three citations above as they read before the 22-line insertion
moved them — 970 -> 992, 1537 -> 1559, 1560 -> 1582:

```bash
# every file type, not just tests: pages, docstrings, comments, data files
git grep -n "handler\.py:970\|handler\.py:1537\|handler\.py:1560"
# expect zero hits before you commit
```

## Verification

1. Every cited anchor resolves on the merged tree: the `grep -n` line number
   equals the number the citing file states.
2. The guards pass on the **merge commit**, not on either parent.
3. A repo-wide grep for the retired numbers returns nothing.
4. The full documentation or lint leg that contains those guards is green — a
   targeted run of two tests does not cover the file you moved code inside.

## Example

Observed 2026-09-16 in the repository this came from, across three trees in one
morning.

**My merge.** A runtime branch had inserted a 22-line block into one handler and
re-stamped three citations: one test's reference tuple and one published page's
two figures. The base branch had meanwhile added 64 lines to a *different*
module and re-aimed the same two guard files for its own tree. `git merge`
reported `Auto-merging` on both guard files and no conflict. Measured on the
merged bytes rather than derived: the three anchors resolved at the numbers the
branch had written, and both guards passed — all 22 of their test cases, in
1.00 s. In this instance the clean merge happened to be right, and running the
guards is what established that; the skill's claim is that a clean merge is no
EVIDENCE either way, not that it always lands wrong.

**A peer's merge, the same morning** (their measurement, relayed to me, not
mine). Their side cited lines 3154–3155, the base cited 3189–3190, and the
merged tree's real answer was **3194–3195** — a value neither parent predicted.
They found it by re-grepping the anchor on the merged bytes instead of carrying
an offset.

So of two merges in one morning, one landed exactly where its branch had
written and one landed on a number neither parent had written — and **the
merge looked identically clean in both cases**. That is the whole argument for
putting the check in the merge routine rather than in a reviewer's memory: the
merge's own quietness does not distinguish them.

## Notes

- **A dated audit's citation disagreeing with the base branch is the EXPECTED
  state**, not a defect: it described the tree it was measured on. Before
  "fixing" someone else's number, find the commit their document was reading.
- **Guards in your own worktree answer about your branch.** When the question is
  what the base branch says, read the ref (`git show origin/main:<path>`), not
  the file.
- Where a citation must survive, cite the *constant or function name* instead of
  a line, or state the commit beside the number so a later reader can tell
  staleness from disagreement.

## See Also

- `merge-conflict-generated-files` — the loud sibling: both branches changed a
  generated file and it *does* conflict, so you regenerate from the union of
  inputs rather than hand-merging. This skill is the case with no conflict at
  all, in hand-authored references.
- `synthetic-id-collision-rebase` — identifiers rather than line numbers, and
  the LOUD version of it: two branches minting the same id collide as a real
  conflict with markers, which is the case this skill is the quiet counterpart
  to.
- `conflicted-pr-starts-no-ci-run-push-resolution-first` — what to do when the
  merge is *not* clean and no CI run exists to tell you anything.
- `gha-pr-merge-ref-shows-upstream-changes` — why CI can see a collision your
  branch alone does not have.
