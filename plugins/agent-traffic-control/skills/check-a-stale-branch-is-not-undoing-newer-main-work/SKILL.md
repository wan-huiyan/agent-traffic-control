---
name: check-a-stale-branch-is-not-undoing-newer-main-work
description: |
  A branch built on an out-of-date main is about to merge, or has merged, and may undo work
  that landed since. Use when a green, conflict-free PR deletes files you never touched,
  newer values or a whole redesign vanish after a sibling PR merged, rows of a shared ledger
  (tracker, registry, CHANGELOG) disappear or revert, or when `git diff main...HEAD` or a
  reviewer says your small PR touches dozens of files you did not change.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Check a Stale Branch Is Not Undoing Newer Main Work

Merged from: pr-from-stale-branch-silently-reverts-newer-main-files,
stale-base-pr-silently-reverts-upstream-content, stale-base-drops-rows-from-a-shared-ledger,
worktree-stale-local-main-ref-inflates-pr-diff.

## Problem

Sibling work lands on main all day. A branch whose content predates some of it can, on merge,
**undo** that work: delete files, put old values back into lines, drop or roll back rows of a
shared ledger. There is usually **no merge conflict**, the PR is `mergeable: MERGEABLE`, CI is
green and the repo's validators pass. The opposite also happens: a correct branch **looks** like it
undoes dozens of files because the diff was measured wrongly. Both are settled by the same check,
measured against fetched `origin/main` at content level.

### What actually causes a silent undo, and what does not

Be precise, because the loose version ("my branch is behind, so it reverts things") is false.

- **Merely being behind does not undo anything.** A branch that never had files B/C/D, and never
  recorded deleting them, does not delete them: GitHub diffs from the **merge base**
  (`git diff origin/main...HEAD`, three dots) and runs a three-way merge, which keeps B/C/D. And a
  branch that edits the **same lines** as a newer main commit **conflicts loudly**.
- **A stale TREE under a current parent does.** The commit then genuinely records the removal,
  and git applies it faithfully with nothing to conflict against. It gets that way by accident:
  - `git reset --soft origin/main` (or `--mixed` then `git add -A`) from a branch whose base was
    old: the pointer lands on current main, the index still holds the old tree, so the commit
    records "delete everything added since";
  - committing a stale worktree with `git add -A`;
  - a branch re-created or re-pointed onto a newer base while its working tree stayed old;
  - a rebase or merge whose conflicts were resolved by taking the stale side.

Measured on a synthetic shared ledger where two sessions append to one file:

| case | merge-tree | rows survive? |
|---|---|---|
| branch appends its own row from a stale base | **exit 1, CONFLICT** | — (loud) |
| branch regenerates the file from a stale copy | **exit 1, CONFLICT** | — (loud) |
| **branch's TREE is stale under a current parent** | **exit 0, clean** | **LOST** |

In the third case the diff from the merge base contains `-{id:'D'}` and `-{id:'E'}` as literal
deleted lines. Git is not choosing your side; it is doing what your commit says.

**Every behindness check passes on the variant that does the damage:**

- `git log --oneline -2` shows your commit directly on top of the newest main commit;
- `git merge-base --is-ancestor origin/main HEAD` → true;
- `git rev-list --count HEAD..origin/main` → 0;
- `git merge origin/main` → "Already up to date.";
- no conflict, `mergeable: MERGEABLE`, CI green.

So the question is never "am I behind?" It is "**does my branch record removing or reverting
something main has?**"

### Variant 1 — whole files deleted

The commit records deleting files that are on main. The removals sit in the diff stat where nobody
reads them; the PR's deletion count is suspiciously high for the work done; the deleted files are
often someone else's analysis, handoff or docs from a sibling session that merged while you
worked. Checks that rely on git raising a conflict miss it entirely.

### Variant 2 — values or a whole design inside a shared file reverted

PR A updates specific lines in a file (new numbers: `50% vs 6%`, `n=117`). PR B, built from pre-A
content, rewrites copy in the same file with the **old** numbers and says "all numbers preserved"
in its body, which is true against its own base. After B merges, the file shows the old values,
while other files A touched and B did not (`app.py`, a JS module, another template) keep A's values.
The result is a display-versus-backend mismatch that no PR diff, CI signal or conflict flagged.

Mechanism note: an earlier version of this lesson said git's three-way merge "takes B's version
wholesale" for overlapping lines. That is wrong: overlapping edits to the same lines conflict. A
silent revert means B's commit genuinely carries the old values relative to the merge base (a
stale tree, as above) or someone resolved the conflict by taking B's side. The detection and
recovery below are the same either way.

Adjacent symptoms: "the numbers look wrong" while recent backend changes look fine; backend
constants and test fixtures match A while rendered HTML and snapshot tests use B's text with old
numbers; the difference is small enough not to look like a bug (`50%` → `48%`, `n=117` → `n=408`).
The same thing happens to config keys, enum values, route paths, role names and link labels.

**Complete-file form.** If A rewrote the whole file (hundreds of lines, new structure, new CSS
classes) and B carries the old file, the merge restores the entire pre-A design. Signals: the user
says "I don't see PR A's changes at all" (rule out deploy lag and browser cache first, then confirm
the serving revision is the post-B image); B's description focuses on other files and mentions the
shared one only in passing ("fixed CSS grid"); B's stat for the file is a big `++++----` such as
`1155 +++++---------------` whose net effect restores the old design;
`git diff <A-merge>..origin/main -- <file>` removes all of A's additions.

### Variant 3 — rows dropped from, or rolled back in, a shared ledger

One hand-edited, machine-parseable file that every session appends to: a tracker
(`docs/site/assets/data.js`), a registry, a manifest, a CHANGELOG with structured entries, a
`mkdocs.yml` nav, an owners file. With a stale tree, other sessions' rows vanish on merge, and:

- `git diff --diff-filter=D --name-only origin/main...HEAD` is **empty**: no file was deleted, so a
  file-level gate never fires;
- the diffstat reads `data.js | 800 +++---`, exactly like a legitimate large edit;
- there is no conflict; the validator passes (the payload is valid whichever rows are in it); test
  suites pass (they do not assert the ledger's contents);
- the diff **against your own base** is clean, additions only. That is the check a session
  naturally runs, and it is the wrong one.

And the half that survives an id check: a row can **survive while its body is rolled back**. Your
branch carries an older copy of a task whose `detail` text another session rewrote; their rewrite
is reverted byte for byte while id, status and position stay put.

### Variant 4 — the false alarm: nothing is being undone

`git diff main...HEAD --stat` reports 92 files and 8,000+ insertions when your one commit touched 6.
Three ways to get a big number from a correct branch:

- **Two dots.** `git diff origin/main..HEAD` compares tip to tip, so every file main gained after
  your branch point shows as a deletion. Synthetic example: main gains `docs/setup.md` after
  `feature/help-text` diverges; two-dot shows it missing from the feature tip, three-dot reports
  only the feature's own edits, and a normal merge keeps the file. Three-dot is not the lax
  option: deleting an 80-line file shows `80 deletions` under three-dot too. It reports real
  removals and drops invented ones.
- **A stale local `main` ref.** Three dots measure from the merge base of the two refs, and with
  `main` (not `origin/main`) that is your local ref. In a multi-worktree repo it is whatever the
  primary worktree last pulled, often far behind, because siblings merge on GitHub and nobody
  pulls the parked checkout. The merge base is then ancient and every file landed since appears.
  Even `origin/main` is only as fresh as your last `git fetch`.
- **A reviewer's scope claim.** A code-review subagent says your one-commit PR "also carries a
  subsystem you didn't author", because it read whole files for context and took code already on
  main for your hunks; your own `git diff main...branch` against a stale local main seems to agree.

Fix the operator **and** the ref: three dots against a stale `main` still over-reports.

## Context / Trigger Conditions

- About to `gh pr create` or squash-merge, especially after `git reset --soft`, a rebase, or
  `git add -A` in a worktree left sitting for hours; or the branch has been open more than about an
  hour in a busy repo.
- Many parallel branches and a squash-merge flow, so main moves while your tree stands still; you
  rebased once and believe you are current (the window reopens with every merge).
- Two PRs open on the same file, one refreshing values, one polishing copy; the polish PR's body
  says "all numbers preserved", "zero logic changes" or "preserves all findings".
- The branch edits a file every session appends to.
- After someone else's stale-base incident, when everyone asks "did my work survive?" Also ask
  "is my open branch about to do it to someone else?"
- A diff, stat or reviewer reports far more files than `git show --stat HEAD`.

## Solution

### Step 1 — Measure against fetched `origin/main`, with three dots

```sh
git fetch origin main -q
git diff --stat origin/main...HEAD                         # only files you meant to touch
git diff --diff-filter=D --name-only origin/main...HEAD    # only files you meant to delete
```

Falsify a big number before acting on it:

```sh
git show --stat HEAD                          # what your commit really changed
gh pr view <N> --json files -q '.files[].path'   # what GitHub will merge
gh pr diff <N> --name-only                    # same, authoritative
gh pr diff <N> | grep -E '^\+def |^\+class '  # the ADDED hunks, not file context
git log origin/main..<branch> --oneline       # how many commits the PR really has
git rev-list --count HEAD..origin/main        # commits main has that you lack
git rev-list --count origin/main..HEAD        # your commits
gh pr view <N> --json mergeable,mergeStateStatus
```

If `git show --stat HEAD` matches `gh pr view --json files`, the PR is `MERGEABLE / CLEAN`, and the
deletion list is empty, the big number was an artifact: **proceed**, do not rebase, do not block. A
reviewer's findings on your real hunks still stand; only its scope claim was wrong. Do not try to
fix the local `main` ref from inside a worktree (`git checkout main` fails: "main is already used by
worktree at <primary>"); just name `origin/main`.

`git merge-base --is-ancestor <base-sha> origin/main` is useful but **necessary, not sufficient**:
the stale-tree variant satisfies it exactly. Only the deletion and content checks close the gap.

### Step 2 — Check content, not only files

**Shared ledger: parse both sides and compare ids AND bodies** against current `origin/main`,
immediately before merging:

```python
#!/usr/bin/env python3
"""Does this branch REMOVE or ROLL BACK any ledger row that main has?"""
import json, re, subprocess, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
MINE = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
LEDGER = "docs/site/assets/data.js"        # <-- your ledger path
# ids this session legitimately added or edited; everything else must match main
MINE_IDS = {"s-2026-08-07-my-session", "d-my-ruling", "t-my-task"}
COLLECTIONS = ("tasks", "decisions", "sessions", "artifacts")

def load(ref):
    src = subprocess.run(["git", "show", f"{ref}:{LEDGER}"],
                         capture_output=True, text=True, check=True).stdout
    # a bare .json file needs no regex — this unwraps `window.DR = {...};`
    return json.loads(re.search(r"window\.DR\s*=\s*(\{[\s\S]*\})\s*;\s*$", src).group(1))

base, mine, bad = load(BASE), load(MINE), False
for coll in COLLECTIONS:
    b = {r["id"]: r for r in base[coll]}
    m = {r["id"]: r for r in mine[coll]}
    if gone := sorted(set(b) - set(m)):
        print(f"*** {coll}: REMOVED {gone}"); bad = True
    # the half an id check cannot see
    if rolled := [i for i in set(b) & set(m)
                  if b[i] != m[i] and i not in MINE_IDS]:
        print(f"*** {coll}: CHANGED BUT NOT MINE {rolled}"); bad = True
    print(f"{coll:12s} main {len(b):3d} -> mine {len(m):3d}")
sys.exit(1 if bad else 0)
```

`REMOVED` rows die on merge. `CHANGED BUT NOT MINE` rows differ in body: diff the fields; if main's
is newer prose and yours the older copy, you are about to revert someone's edit. It costs one
`git show` per side, well under a second on a 15,000-line ledger, so run it unconditionally.

**Values inside a shared file: grep anchored needles on both trees.**

```bash
git show origin/main:path/to/affected.html | grep -nE 'newVal1|newVal2|newVal3'
git show <PR-A-merge-commit>:path/to/affected.html | grep -nE 'newVal1|newVal2|newVal3'
git diff <PR-A-merge-commit>..origin/main -- path/to/other-file.py   # empty = survived
```

N matches on A's merge commit and M < N on main means the regression is real. **Anchor every
needle to a value that exists only after the fix**, and check the grep returns the expected count
on the known-good tree first. A bare `50%` matched `Target: >50%` in unrelated copy on both trees,
so it returned output whatever tree it ran on and "returned nothing" could never be true: a needle
that matches something you were not asking about turns a real regression into a clean result. If B
legitimately changed some values too, audit field by field rather than per file.
`gh pr view --json files` will not surface this: both PRs declared the same file changed.

For a complete-file revert, `git diff <A-merge>..HEAD -- <file>` before shipping; a `1155
+++++----` stat on a file that just got a 1155-line rewrite in the prior PR is the tell.

### Step 3 — Confirm a stale tree before changing anything

Every behindness check passes, so use arithmetic: if your branch differs from an OLD commit by
fewer files than from its own parent, the tree predates the parent.

```sh
for base in <parent> <a few older main shas>; do
  printf "%s  %s files\n" "$base" "$(git diff --name-only $base HEAD | wc -l)"
done
```

### Step 4 — Fix before merging

- **Deleted files:** restore the paths, not by merging main in (main is usually already an
  ancestor, so that is a no-op):

  ```sh
  git checkout origin/main -- <each deleted path>
  # or: branch from origin/main and re-apply only your own edits
  ```

- **Shared ledger: rebuild, never merge-and-resolve.** Two sides inserting at the head of one array
  give interleaved hunks that are easy to get subtly wrong. Take main's file and replay your own
  edits onto it; this is additive by construction:

  ```sh
  git checkout --ours docs/site/assets/data.js      # in a rebase, --ours IS main
  python3 scripts/apply_my_rows.py                  # re-run YOUR splicing script
  node docs/site/tools/validate_data.mjs
  ```

  Script your ledger edits in the first place, so they can be re-run against a newer base. If the
  ledger is hand-formatted, splice the individual object rather than re-serialising: a full
  `json.dumps` round trip is usually not byte-identical and produces hundreds of lines of diff
  that are nobody's change. Prove it with a no-op splice first (render a row, splice it back
  unchanged, assert the file is byte-identical).
- Re-run Steps 1 and 2. The deletion list must be empty and the audit clean; a clean audit is
  valid only for the commit it ran against, so expect a second hit if anything lands meanwhile.
- If a merge you run does conflict, you are in conflict territory: `pr-conflict-from-mid-flight-merges`,
  `merge-conflict-generated-files`.

**On the old advice "always `git merge origin/main` before every PR":** worth doing (conflicts
surface on your own time; tests run on the tree that will land), but it does not prevent a revert.
Against a stale tree it is a no-op ("Already up to date", the recorded deletions survive). Against
a branch that is merely behind there was nothing to prevent; merging main only makes a two-dot
diff stop showing phantom deletions. Keep it as hygiene; do not count it as the check.

### Step 5 — If it already merged: recover

`git revert <B-merge>` applies the inverse of B to the current tree. It also removes B's legitimate
changes (the language polish, the minor CSS fix) and can conflict with later edits; it is right
only when every change in that commit should go. Inspect the
offending diff and later edits first, and recover only what is missing into current main:

```sh
git worktree add .claude/worktrees/recover-A-after-B -b fix/recover-A-after-B origin/main
git diff <pre-A-base>..<PR-A-merge-commit> -- path/to/affected.html   # A's intended edits
```

- **Inventory** each lost edit against current main:

  | # | Line | Post-B (regressed) | A's intended | Notes |
  |---|---|---|---|---|
  | 1 | #237 | "based on 448 records" | "+ n=448 + 6,483-record" | lost context |
  | 2 | #354 | `48% vs 5%` | `50% vs 6%` | lost refresh |

- **Partial revert:** targeted edits that swap A's values back **inside B's rewritten text**,
  keeping B's voice and structure verbatim; restore any explanatory sentence A had added. Do not
  `git checkout <A-merge> -- file`, which overwrites B's work.
- **Complete-file revert** (B's file is the pre-A file): targeted edits cannot work, so restore A's
  file wholesale, then layer B's genuine improvements back on:

  ```bash
  git checkout <PR-A-merge-commit> -- path/to/template.html
  git diff <pre-B-base>..<PR-B-merge> -- path/to/template.html | grep "^+" | head -30
  ```

- **Files and ledgers:** `git checkout <last-good-sha> -- <path>` only when that keeps every wanted
  current edit; otherwise extract the missing hunks. For a hand-edited ledger, splice one object at a
  time from `git show <last-good-sha>:<ledger>`, and diff the field, not just the key.
- **Tests:** run the file's owning tests; if some fail, re-run them on clean `origin/main` to see
  whether they fail there too, and say so in the PR body instead of fixing them in the recovery.
- **Recovery PR:** title like `fix(<area>): restore <PR-A> values reverted by #<PR-B> stale-base
  merge`; body with the inventory table, a paragraph on why (stale base, no conflict), and the
  test evidence.

### Step 6 — Auditing as a possible victim

**Scope the check to what you TOUCHED, not what you MADE.** A check that lists the things you
created misses:

- in-place edits to records you did not create (amending someone's ruling, appending "DONE" to an
  existing task, editing a caveat block): no new id, so an id/status/PR-number sweep passes while
  the prose has reverted. One standing ruling was left publishing a superseded range because the
  sweep looked only at `status` and `prs`;
- a partial rollback inside one record: half an appended edit survived, so the entry said
  "settled" and two sentences later quoted the range the settlement replaced. A half-reverted
  record reads self-consistent, which is worse than a clean revert;
- a moved number, which grep cannot tell from a reverted one (a README count rose from 136 to 140
  as siblings added tests; a needle for 136 reports a false loss). Re-derive computed values; do
  not compare the string.

Write a needle per **claim** and save it as `needle-audit.sh`, because you will run it more than
once:

```sh
REF=${REF:-origin/main}                       # override to check a BRANCH pre-merge
f() { git show "$REF:$2" | grep -qF -- "$3" && echo "OK   $1" || echo "LOST $1"; }
f "ruling: the amendment"    path/to/ledger.js "AMENDED: approved revision"
f "caveat: pinned, not open" path/to/ledger.js "PINNED: reviewed value"
# for anything computed, re-measure instead of grepping:
test "$(pytest docs -q --co 2>&1 | tail -1 | awk '{print $1}')" = "$(grep -oE '[0-9]+ collected' README.md | head -1 | cut -d' ' -f1)"
```

**Take every needle out of the merged artifact, never out of recall,** and paste the source line
beside the check:

```sh
git show <squash-sha> -- path/to/file.py | grep '^+' | grep -i batch
# → +    batch_size = ...           ← THIS line is the needle
```

A recalled `selected_batch_size` against committed `batch_size` finds nothing and reports a phantom
deletion. The failure is two-sided:

| A guessed needle that… | …manufactures |
|---|---|
| MISSES | a phantom deletion — alarming, but someone goes and looks |
| happens to MATCH | a **false all-clear** — nobody re-checks a clean audit |

**Check the state AT the suspect commit, not only at `origin/main`.** Current state cannot tell
"never hit" from "hit and restored by someone else's recovery PR":

```sh
REF=<suspect-squash-sha> sh needle-audit.sh   # did THAT merge drop it?
REF=origin/main          sh needle-audit.sh   # is it there right now?
```

Then tell the other sessions: losses are per-session and nobody else can see yours; a broadcast
with a copy-pasteable `git cat-file -e origin/main:<path>` loop finds the ones whose owners have
wrapped. After your own merge, verify on main too:

```sh
for f in <your files>; do
  git cat-file -e origin/main:"$f" 2>/dev/null && echo "OK   $f" || echo "GONE $f"
done
```

and re-run the ledger parser against `origin/main`, asserting each of your rows is present **and
current** (status flipped, PR chip filled, text not the pre-session wording).

### Step 7 — Prevention

- A pre-merge gate on deletions and ledger rows against current `origin/main` (Steps 1-2), run
  immediately before merging, not at wrap-up.
- A CI content audit that greps anchor strings from recently merged PRs on a sample of templates;
  value anchors in markup (`data-rate-a2="50"`) unit-tested against backend constants; snapshot and
  lockstep tests on rendered templates (one such test existed during the #759 incident below but sat
  on the known-failures list).
- A PR-template question "rebased against latest main before pushing?" for copy and template PRs.
- One file per ledger entry (`entries/<id>.json`, assembled at build time) makes the ledger variant
  impossible: a stale branch simply lacks sibling files instead of overwriting a shared array.

## Verification

- For a stacked or sibling pull request, compare where B was cut with where A landed: `gh pr view <B> --json baseRefOid` against `gh pr view <A> --json mergeCommit`. If B's base is older than A's merge, B was cut before A landed and must be checked.
- `git diff --diff-filter=D --name-only origin/main...HEAD` is empty or lists only intended
  deletions; `git diff --stat origin/main...HEAD` lists only intended files; GitHub's "files changed"
  matches (it is computed the same way).
- The ledger audit exits 0 against current `origin/main`. **Watch it fail once**: take an older
  ledger (`git show origin/main~5:<ledger> > <ledger>`, or drop one row) and confirm it exits 1 and
  names rows. An audit that has only ever printed "clean" is indistinguishable from one that does
  not run.
- Anchored needles return A's count on main
  (`git show origin/main:<file> | grep -cE 'newVal1|newVal2'` equals the count at A's merge), and
  each backend constant and its displayed value agree.
- For a false alarm: `git show --stat HEAD` count equals `gh pr view <N> --json files` count,
  and `mergeStateStatus` is `CLEAN`.

## Examples

- **Stale tree under a current parent (synthetic).** An agent with an old index ran
  `git reset --soft origin/main` and committed. The commit's parent was current main, so ancestor
  checks passed, but it recorded removal of files and ledger edits absent from the old index. A
  pre-merge deletion review catches it; after merge, recovery must check edited fields as well as
  files, and every affected owner.
- **Values reverted (#751 then #759).** #751 refreshed A2 (`48% → 50%`, `5% → 6%`) and A3
  (`4.9% → 6.0%`, `48.3% → 50.5%`, `n=408 → n=117`) in a template, `app.py`, a JS module and a
  second template. #759 ("simplify copy for stakeholder readability"), built from pre-#751 content
  and saying "All numbers preserved", merged four minutes later. An anchored grep for
  `6\.0%|n=117|8× the rate|6,483-record` on main returned nothing (three lines on the pre-#759
  tree). Eight lines in the template regressed; the other three files kept #751's values. Recovery
  PR #760: eight targeted edits keeping #759's plain-English voice, merged about seven minutes after
  detection.
- **Whole design reverted (#848 then #850).** #848 rewrote `templates/library_roadmap.html`
  (+1155/-258: new hero, theme cards, timeline). #850, an "impeccable polish pass" whose description
  mentioned the roadmap only as a CSS grid fix, carried the pre-#848 file and merged 32 minutes
  later. The user saw none of #848's design; the serving revision was confirmed as #850's image, and
  `git diff 09ea9b7d..bf5fb3e6 -- templates/library_roadmap.html` removed about 911 lines. Recovery:
  `git checkout 09ea9b7d -- templates/library_roadmap.html`, then re-apply #850's grid fix.
- **Ledger near-miss (#848 in another repo, after #853).** #853 had just reverted 59 files and
  5,081 deletions of merged work from at least four sessions, while green and validated. An open
  branch, rebased, green, validated and through 41 review agents, was clean against its own base.
  Against current `origin/main` eight commits later (including the two restore PRs) it would have
  removed 3 tasks, 2 decisions, 2 session cards and 8 artifacts, and rolled back the text of 9 rows
  whose ids survived. `--diff-filter=D` was empty; the stat read `data.js | 800 +++---`; the
  validator passed. Fixed by taking main's `data.js` and re-running the branch's splicing scripts;
  the re-audit then caught a second instance mid-run (another session added PR chips meanwhile).
  #853's own restore needed a follow-up (#872, three in-place edits an id check could not see).
- **False alarm.** One commit touching 6 files; `git diff main...HEAD --stat` showed 92 files and
  8,381 insertions. `git show --stat HEAD` gave 6; after fetching, `HEAD..origin/main` was 1 and
  `origin/main..HEAD` was 1; `gh pr view 1019 --json files` listed the same 6 and `CLEAN`. The local
  `main` was parked far behind in the primary worktree. Merged without rebase.

## Notes

- The tell for a real undo is deletions or reverted content under a **three-dot** diff against
  fetched `origin/main`, or a ledger audit hit, never a conflict marker.
- A PR body saying "X preserved" is true against its base, not necessarily against current main.
- This is the per-branch, at-merge check; `large-redesign-parallel-branch-collision-audit` is the
  pre-plan audit across many branches.
- `gh pr merge --delete-branch` from a worktree may fail with "main is already used by worktree
  at ..."; the merge succeeded. Delete the remote ref with
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`.
- A build that packages files from a stale local checkout is a different problem:
  `deploy-from-stale-worktree-silent-rollback`.

## See also

- `git-diff-2dot-vs-3dot-merge-safety`: the operator rule. Fetch, then name `origin/main`, three dots.
- `pr-conflict-from-mid-flight-merges` and `merge-conflict-generated-files`: when git does conflict.
- `parallel-pr-template-fork-duplicates-moved-section`: duplication rather than reversion.
- `synthetic-id-collision-rebase`: two entries claiming one id during a rebase.
- `shared-file-redesign-parallel-author-serial-integrate`: structuring parallel work on one hot file.
- `shared-mutable-index-rmw-race-use-marker-blob-per-item`: the runtime version of per-entry files.
- `worktree-outer-ls-mistaken-for-main-state`: stale local state read through `ls`.
- `gh-pr-merge-worktree-checkout-trap`: why checkout of `main` and `--delete-branch` fail from a worktree.
