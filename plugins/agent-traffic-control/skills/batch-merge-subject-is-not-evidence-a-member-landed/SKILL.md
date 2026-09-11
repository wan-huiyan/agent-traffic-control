---
name: batch-merge-subject-is-not-evidence-a-member-landed
description: |
  You are about to close, delete the branch of, or mark as landed a pull
  request because a batch, roll-up or merge-train commit on the target branch
  names it in the subject line, and because the member's own commits all
  predate that merge by wall clock. Neither of those is evidence. A batch
  branch is assembled at some moment BEFORE it merges, so anything the member
  pushed after assembly is outside it, and the subject records INTENT at
  assembly time rather than CONTENT at merge time. Use before closing a
  member, when an ancestry check against a squashed batch says no, or when a
  member's branch still shows commits ahead of the target. Compare file
  content against the target branch instead, expecting exactly one legitimate
  difference: the shared aggregate file every member appends to.
version: 1.0.0
date: 2026-09-11
author: wan-huiyan
disable-model-invocation: true
---
# A Batch's Subject Naming a Member Is Not Evidence the Member Landed

## Problem

Several small pull requests were combined into one branch and landed together
to save CI runs. The squash commit on the target branch says, in `git log`:

```
Batch: four small pull requests in one run — #2767, #2743, #2739, #2772
```

That subject is written by the batch itself, it is in the permanent history,
and it reads as a receipt. The obvious next step is to close each named member
as already landed and delete its branch.

**The subject is a claim about what was ASSEMBLED, not about what MERGED.** A
batch branch is built at some moment T by merging or cherry-picking each
member's head as it stood at T. The batch then sits in review, gates run, and
it merges at some later moment. Everything a member pushed between T and the
merge is outside the batch and is not on the target branch, while the subject
still names that member exactly as before.

Nothing in the batch notices. The member's branch is not rewritten, no
conflict is raised, no gate fails, and the batch's own diff looks complete
because it IS complete with respect to the heads it was built from.

Closing the member on the strength of the subject deletes work that was never
merged. In the worked example below, that was 261 added and 257 removed lines
across four files, including a behaviour change in application code.

## Context / Trigger Conditions

You are in the right place if:

- A batch, roll-up, train or "combined" pull request has merged into the
  target branch, and its subject or body enumerates member numbers
- You are deciding whether to close a member, delete its branch, or move its
  tracking row to done
- The member is still OPEN, or its branch still reports commits ahead of the
  target
- Optionally: an ancestry probe such as `git merge-base --is-ancestor` on the
  member's head returns non-zero, which after a squash means nothing in either
  direction

**Two things that look like corroboration and are not:**

1. **Wall-clock ordering.** Every one of the member's commits is older than
   the batch's merge timestamp. That is what you would expect either way,
   because assembly precedes merge — the batch cannot have been built from
   commits that did not exist yet, but it can easily have been built before
   the last of them arrived. The comparison that matters is member head
   against ASSEMBLY time, and assembly time is not recorded anywhere obvious.
2. **The ancestry probe.** After a squash merge the member's SHAs are not
   ancestors of the target whether or not the content landed, so a "no" is the
   expected reading for a member that landed perfectly. It is evidence in
   neither direction. The sibling skill named in Notes covers that half.

## Solution

**Compare content, file by file, against the target branch.** Ancestry and
subject lines both answer a question you did not ask.

### Step 1 — List the files the member touches

```bash
BASE=$(git merge-base origin/main <member-branch>)
git diff --name-only "$BASE" <member-branch>
```

Use the merge base rather than the target tip, so the list is the member's own
files and not everything that moved on the target since.

### Step 2 — Compare each file's blob against the target branch

```bash
for f in $(git diff --name-only "$BASE" <member-branch>); do
  a=$(git rev-parse <member-branch>:"$f" 2>/dev/null)
  b=$(git rev-parse origin/main:"$f" 2>/dev/null)
  [ "$a" = "$b" ] && echo "SAME      $f" || echo "DIFFERENT $f"
done
```

Blob equality is exact and cheap. It is stronger than line counts and it does
not care how the merge was performed.

### Step 3 — Expect exactly ONE legitimate difference

Most batches have one, and only one, file that is allowed to differ: **the
shared aggregate file that every member appends to** — a tracker data file, a
changelog, a generated index, a lockfile, a fixture registry. On the target
branch that file holds the base plus EVERY member's additions; on the member's
own branch it holds the base plus only its own. So it is different by
construction even when the member landed perfectly, and it is different in a
way no amount of comparing will resolve.

**Confirm that one by looking for the member's own entries, never by comparing
the blob:**

```bash
git show origin/main:path/to/aggregate | grep -c '<the member's own row id>'
```

A count of at least what the member added means the member's rows are there.
The blob will still differ, and that is correct.

### Step 4 — Decide on the answer, not on the subject

- **Every file SAME except the aggregate, and the member's rows present in the
  aggregate** — the member landed. Close it.
- **Any other file DIFFERENT** — the member did not fully land. Do not close
  it. Read that file's diff and find out which commits are missing.

### Step 5 — Recover the stranded part

The member is still open and its branch still exists, so there is nothing to
rescue from a reflog. Rebase it onto the current target branch, confirm the
diff is now only the stranded work, and land it on its own. If the aggregate
file conflicts, resolve it by keeping BOTH sides' rows and then COUNTING: base
plus your own additions is the whole answer.

### Step 6 — Fix the batching procedure, not just this member

A batch that can strand a member will do it again. Either freeze members
before assembly (mark them ready and stop pushing), or record the assembly
time and each member's head SHA in the batch body, so the check above has
something to compare against. The subject line cannot carry that, because it
is written once and the world moves afterwards.

## Verification

The check has to be able to return YES, or it is not a check. Run it on a
batch you already believe landed cleanly and confirm it says so — same files,
one aggregate difference, rows present. If it reports every member as
stranded, the comparison is wrong, not the batches.

A clean member reads:

```
--- is member head an ancestor of origin/main? ---
NO                                  ← expected after a squash, means nothing
--- file-by-file content comparison ---
SAME      tools/validate_data.mjs
SAME      tools/validate_data.test.cjs
SAME      scripts/test_facts.py
SAME      deliverables/night.html
SAME      README.md
--- aggregate ---
site/assets/data.js: DIFFERENT (expected), member's rows present: 1 ✓
=== Verdict: landed ===
```

A stranded member reads the same until a second file says DIFFERENT.

## Example

*Worked example from a route-generation repository that lands several small
pull requests in one run to cut CI cost. Names and paths are that repo's; the
mechanism is not.*

On 2026-09-11 a batch (#2776) merged at 04:45:37Z as squash commit
`b61f7fadd3`, with the subject quoted at the top of this skill naming four
members. One of them, #2767 (*store the option a reviewer was shown so an
unmatched card has somewhere honest to go*), was about to be closed as already
landed.

It had not landed. Measured against the target branch it was **261 added and
257 removed lines across four files**, including 78 lines in a rulings
document and a real behaviour change in application code. The batch branch had
been assembled from an older head of #2767, and #2767 kept committing
afterwards. It is still OPEN.

**All six of #2767's commits predate the batch's merge timestamp**, which is
what made the wrong answer feel verified. That ordering is guaranteed by the
mechanism and proves nothing.

**The positive control, from the same repository the same day.** A second
batch (#2792) merged at 16:20:39Z naming four members, one of which was #2788
(*a validator counted three arrays and validated four*). The same comparison
run on #2788: ancestry NO, and all five of its files byte-identical on the
target branch. That member landed, and the check said so. Closing it was
right, and it was right for a reason the subject line could not supply.

## Notes

- **Sister skill**: [`squash-merge-content-preservation-vs-ancestor-check`](../squash-merge-content-preservation-vs-ancestor-check/SKILL.md)
  covers the other half — why the ancestry probe fails after a squash even
  when the content is preserved verbatim. This skill is about the case where
  the content genuinely is NOT preserved, and every signal except a content
  comparison says it is.
- **The failure is silent in both directions of ordinary review.** The batch's
  own diff is complete with respect to what it was built from, so reviewing
  the batch cannot find this. The member's branch is untouched, so nothing
  there flags it either.
- **A merge-train or rebase-train has the same shape.** Anything that
  assembles a set at time T and lands it at time T+n can strand what arrived
  in between. The wording differs; the check does not.
- **Do not put the aggregate file in the exception list by name and forget
  it.** The exception is "the file every member appends to", which changes as
  the repo changes. Derive it from the batch's own members rather than from
  memory, or an unrelated file will one day inherit the pardon.
- **Once assembled, a member that keeps committing is the hazard.** If your
  process lets members push after assembly, the check in this skill is not
  optional hygiene — it is the only thing standing between a stranded commit
  and a closed pull request.

## References

- GitHub docs: [About merge methods](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-merge-methods-on-github)
  — squash collapses the head branch's commits, so the member's SHAs are not
  preserved on the target.
- Git docs: [`git merge-base`](https://git-scm.com/docs/git-merge-base) —
  `--is-ancestor` answers reachability in the commit graph, never content
  equivalence.
- Git docs: [`git rev-parse`](https://git-scm.com/docs/git-rev-parse) —
  `<rev>:<path>` resolves to the blob SHA, which is what makes the
  file-by-file comparison in Step 2 exact.
