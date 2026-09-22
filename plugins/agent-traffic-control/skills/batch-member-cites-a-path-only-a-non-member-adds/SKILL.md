---
name: batch-member-cites-a-path-only-a-non-member-adds
description: |
  You wrote something correct that the default reader cannot reach: a batch member citing a
  path only a NON-member adds, or a rule, ruling or ledger sitting on an unlanded branch.
disable-model-invocation: true
version: 1.1.0
date: 2026-09-22
author: wan-huiyan
---
# A Batch Member Can Cite a Path Only a Non-Member Adds

## Problem

Batch assembly asks one question about files: **do two members touch the same file?** That
decides membership, because two members editing one file collide. It is the right question and
it is asked.

There is a second question, and nothing asks it: **does a file a member adds or changes NAME a
path that only a pull request OUTSIDE the batch adds?**

The two are not the same shape. Overlap is symmetric and it is about *editing*. This one is
directional and it is about *referring*. A member can cite a path no member creates, and the
citation is just text — inside a `#` comment, a docstring, a markdown link, a JSON string in a
hand-edited data file. Nothing in a normal gate resolves it:

- the compiler and the interpreter never read comments or docstrings;
- test suites assert behaviour, not that a cited path exists;
- a link checker, if there is one, usually runs on docs and not on source comments;
- a tracker validator checks enums and required fields, not that a `href` resolves.

So the batch merges green, and the target branch now has a sentence pointing at a file it does
not have. The reader who follows it finds nothing, and cannot tell whether the path is wrong,
the file was deleted, or it never arrived.

**The failure is quiet in both directions.** If the sibling lands a day later, the citation
silently becomes true and nobody learns anything. If the sibling is abandoned, the dangling
path sits there indefinitely, and the figure it was supposed to support has no source.

## Context / Trigger Conditions

Run this check when **all** of these hold:

- you are assembling or about to flip a batch, roll-up, merge train, or any set of pull
  requests intended to land together;
- at least one member's diff adds or changes prose — comments, docstrings, markdown, a tracker
  or metadata file — as opposed to only code and tests;
- there exist open pull requests that are NOT in the batch. (If every open pull request is in
  the batch, a cited path either exists or was never coming, and the check collapses to a
  plain existence test.)

Strong smells that this has already happened:

- a member's diff contains a hedge like "(in #NNNN, which has not landed yet)", "still open",
  "see the audit when it lands" — somebody noticed the specific instance and annotated it
  rather than fixing the gap;
- a member cites a `docs/analysis/…`, `docs/research/…` or `…/findings.md` path while the
  analysis itself is a separate pull request, which is the usual split: the code fix is small
  and urgent, the write-up is large and slow;
- a reviewer's report says "N citations of X, M of them hedged" — the annotation count is the
  tell that the paths were noticed one at a time.

**Also worth running outside a batch**, on any single pull request whose prose cites paths it
does not itself add — the gap is the same, the batch just multiplies the chances.

## Solution

### Step 1 — Collect the batch's own post-merge path set

The set of paths that WILL exist is the target branch's tree plus every path any member adds.
Compute it, do not eyeball it.

```sh
BASE=origin/main
# Positional parameters, NOT a space-separated string: zsh does not word-split
# an unquoted $VAR, so `for m in $MEMBERS` passes all three SHAs as one argument
# and every git call fails with "ambiguous argument". `set --` works in sh, bash
# and zsh alike. This is not hypothetical -- it is how the first draft of this
# skill failed its own verification step.
set -- 4f51284206 c36acd613f 446144919c      # member HEADS, not branch names

git ls-tree -r --name-only "$BASE" > /tmp/will_exist.txt
for m in "$@"; do
  git diff --name-only --diff-filter=AM "$BASE...$m" >> /tmp/will_exist.txt
done
sort -u /tmp/will_exist.txt -o /tmp/will_exist.txt
wc -l < /tmp/will_exist.txt
```

Use `...` (three dots), not `..`. Two-dot reports files the base gained after you branched as
your own changes, which inflates the set with paths you did not add and makes the check pass
when it should fail.

### Step 2 — Extract every path-shaped string each member ADDS

Only added lines matter: a path already on the base and already cited was fine before this
batch and is somebody else's problem.

```sh
for m in "$@"; do
  git diff "$BASE...$m" -- . \
    | grep '^+' | grep -v '^+++' \
    | grep -oE '[A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.(md|py|json|html|js|mjs|cjs|yml|yaml|txt|csv|jsonl)' \
    | sort -u
done | sort -u > /tmp/cited.txt
wc -l < /tmp/cited.txt
```

Tune the extension list to the repository. Widen rather than narrow: a false positive costs
one `grep`, a false negative is the whole defect.

### Step 3 — Subtract, and read what is left

```sh
comm -23 /tmp/cited.txt /tmp/will_exist.txt
```

`comm` requires lexicographic sort on both inputs — `sort -u`, never `sort -n` — or it returns
a confident wrong answer with exit 0.

Every line printed is a path a member cites that the post-merge tree will not contain.

### Step 4 — Classify each survivor; most are not defects

Expect noise, and expect to look at each one:

- **a path in an unlanded sibling** — the real finding. Go to Step 5.
- **an example or placeholder** (`path/to/your/file.md`, `docs/example.md`) — fine.
- **a path in a string the code constructs at runtime**, or under a directory created on
  demand (`output/…`, `build/…`, a cache dir) — fine, and this is why the check is advisory
  rather than a gate.
- **an external path** — another repository, a URL fragment, a container path. Fine.
- **a deleted file being named in order to say it is gone** — fine, and often required by a
  deletions-declared guard.
- **a RELATIVE path** (`../rulings/…`, `../deliverables/…`) — a document linking to a sibling
  document. Resolve it against the citing file's own directory before judging it, or skip the
  `../` class entirely; the subtraction compares against repository-root paths and will always
  flag these.
- **a mangled path** (`nprototype/…`, `ndocs/…`) — the leading `n` is the tail of an escaped
  `\n` inside a JSON string in a hand-edited data file. Harmless, and a good reminder that the
  extraction is a regex over diff text rather than a parser.
- **an absolute path outside the repository** (a session transcript under
  `/.claude/projects/…`, something under the user's home) — fine.

**The measured noise profile, from running this on the batch in the Example:** 39 cited paths,
13 survivors, **1 real finding**. The other 12 were 6 relative paths, 2 absolute paths outside
the repository, 1 `\n`-mangled path, and 3 runtime or generated paths. So expect roughly a
dozen survivors on a three-member batch and expect to read all of them — the signal-to-noise is
about 1 in 13, which is cheap to scan and far too noisy to make a gate.

### Step 5 — For a genuine dangling citation, pick one of three, and write down which

1. **Pull the sibling into the batch.** Correct when the sibling is ready and does not collide.
   Best outcome: the citation is true the moment it lands.
2. **Remove or rewrite the citation** so it stands on its own — quote the figure and say where
   it came from in words, or point at something that is on the target branch. Correct when the
   sibling is far off.
3. **Keep the citation and hedge it — but only with an owner and a scheduled task.** A hedge
   is a sentence that predicts its own expiry, and somebody still has to come back and delete
   it. Create the task in the same change, name every file and line it covers, and say in the
   task that the sweep must be by CLAIM and not by phrase, because the wordings will differ.

Never choose 3 by default because it is cheapest. It is only cheap if the task is real.

### Step 6 — Fix the assembly procedure, not just this batch

Add Steps 1–3 to the batch runbook beside the overlap check, so the two directional questions
sit together and neither is mistaken for the other. Two lines in the runbook:

```
overlap   do two MEMBERS touch the same file?                       decides membership
dangling  does a member's file NAME a path only a NON-member adds?  decides citations
```

## Verification

The check has done its job when you can print both numbers and the difference:

```sh
echo "paths the merged tree will contain : $(wc -l < /tmp/will_exist.txt)"
echo "paths the members cite             : $(wc -l < /tmp/cited.txt)"
echo "cited but will not exist           : $(comm -23 /tmp/cited.txt /tmp/will_exist.txt | wc -l)"
comm -23 /tmp/cited.txt /tmp/will_exist.txt
```

**Prove the check can fail before trusting it that it passed.** Append a path you know is
absent to `/tmp/cited.txt`, re-run the `comm`, and confirm it appears. A subtraction against a
malformed or empty `will_exist.txt` prints nothing and looks exactly like a clean result.

```sh
echo "docs/this/does/not/exist.md" >> /tmp/cited.txt
sort -u /tmp/cited.txt -o /tmp/cited.txt
comm -23 /tmp/cited.txt /tmp/will_exist.txt    # must now print that line
```

And after the batch lands, verify on the target branch itself rather than on your prediction:

```sh
git fetch origin main
while IFS= read -r p; do
  git cat-file -e "origin/main:$p" 2>/dev/null || echo "MISSING $p"
done < /tmp/cited.txt
```

## Example

A batch landed three members. One carried small memory fixes to route generation; its code
comments cited the measurement audit by path in six places. The audit lived in a *fourth* pull
request, still a draft, not in the batch.

The batch's overlap analysis was done properly and found exactly one shared file, the tracker,
which was resolved by replay. Nothing asked whether a member's added comments named a path only
a non-member added. The batch merged green, and the target branch then had six sentences
pointing at `docs/analysis/route_generation_memory_audit_2026-09-21.md`, which was not there.

A reviewer had noticed the narrow instance the night before — "six citations, four hedged, two
bare" — and had the two bare ones annotated and a sweep task filed. That was the right response
to the instance and it left the gap in place: the annotation was applied by hand, per citation,
by someone who happened to look.

When the audit finally landed, the sweep found the five code sites by grep, and then **two more
in tracker rows that used different wording** and would have been missed by a phrase search —
which is why Step 5 says to sweep by claim.

Cost of the gap: a hand sweep across seven sites in two languages, plus the time of everyone who
followed a path that was not there. Cost of the check: three commands, under a minute.

**Run retrospectively on that exact batch, the check finds it.** Base `48efe4af7b`, members
`4f51284206 c36acd613f 446144919c`: 12,835 paths in the post-merge tree, 39 cited, 13 cited but
absent — and `docs/analysis/route_generation_memory_audit_2026-09-21.md` is one of the 13. That
is the verification for this skill, and it is why the numbers in Step 4 are measured rather than
estimated.

## The mirror: a rule everyone must obey, where the default reader cannot see it

The check above is about a member NAMING a path that will not exist. The same defect points the
other way, and it is worth the same instinct: **you wrote something correct, and the reader who
needs it cannot reach it.**

Three instances from one day, all in a repository where every session is an agent working from
`main`:

1. **Code on `main` cited a document that was not on `main`** — the case this skill was written
   for.
2. **An owner's ruling choosing between two approaches sat on an unlanded branch.** A session
   asked "can we do X?", another session built X, and the ruling declining X by name was an hour
   old and unreadable from `main`. The pull request was built, gated, opened and closed inside
   two hours.
3. **The single cloud-spend ledger — the file whose stated purpose is that no session keeps a
   private count — existed only on the branch of a pull request four places down the landing
   order.** Every session was being asked to check a daily ceiling against a file the default
   reader could not see.

There is a fourth that shows the real cost. A session recorded the owner's decision on a branch
it never pushed; a second session could not read it, asked her the same question again, and
**she answered twice.** The record existed, was correct, and cost her the thing it was written
to save.

**The general form: a rule, ruling or tally is not in force because it is written and correct.
It is in force when the default reader reaches it without being told which branch to look on.**
Until then it is enforced by people remembering to ask — which is what it was written to
replace.

### What to do

- **When you write a coordination artefact** — a ledger, a ruling every session must honour, a
  runbook rule — ask where its reader will look, and whether it is there yet.
- **If it is not there yet, say so IN it.** One sentence: *"Until this lands, the ceiling is
  enforced by sessions telling the coordinator, not by this file."* That converts a silent gap
  into an instruction.
- **Treat a records pull request carrying one as more urgent than its size suggests.** It looks
  low-priority because it changes no code, and everyone else is being asked to obey it.
- **Before building anything that answers a question the owner might already have answered,
  read the rulings directory** — and read it on `main` AND on unlanded branches, because
  instance 2 is exactly the case where `main` is clean and the answer exists anyway.

### One check, and it is cheap

```sh
# 1. Does the default reader have it? This is the question that matters.
git cat-file -e origin/main:path/to/the/rule.md 2>/dev/null \
  && echo "on main" || echo "NOT on main — say so in the file"

# 2. If not, which branches carry it? TWO commands, not one.
git log --all --diff-filter=A --format=%H -1 -- path/to/the/rule.md
git branch -a --contains <the sha that printed>
```

**Step 2 is two commands on purpose.** Writing it as
`git branch -a --contains "$(git log …)"` is shorter, and a session confined to one
worktree REFUSES to run it: the guard cannot verify that a git command in that shape
stays inside the worktree, so it never executes. Sessions here usually ARE confined
to a worktree, so the one-liner is unrunnable for most of its readers. Both commands
above were run, split, before this was written — which is how the shape was found.

`git branch -a` rather than `-r`, because a `+` in front of a local branch means
another worktree has it checked out — which tells you a peer is holding the file,
not just that it exists somewhere.

**A presence check against a moving branch expires.** Record the SHA you verified against, not
just the branch name — a peer pushing twice while you read makes "present on branch X" a
statement about a tree that no longer exists. "Absent from `main`" does not expire the same way,
which is why the `origin/main` check is the one to lead with.

## Notes

- **Why counting hedges does not close it.** A hedge count tells you how many citations somebody
  looked at, not how many exist. The two bare citations in the example were found by a reviewer
  reading the diff, not by any tool.
- **The tracker or metadata file is the easiest place to miss.** Paths inside JSON strings in a
  hand-edited data file are invisible to a docs link checker and to every code tool, and a
  tracker validator checks enums and required fields rather than whether an `href` resolves.
- **This is not the same as `inherited-scope-doc-names-may-not-exist`.** That one verifies that
  dataset, table and column names in a prior session's scope document exist before a long
  dispatch — same shape, different subject and a different moment. This one is about repository
  paths in a batch member's diff at assembly time.
- **Nor the same as `batch-merge-subject-is-not-evidence-a-member-landed`.** That is about
  whether a member landed. This is about what a landed member points at. Run both.
- **A cited path that exists is not a cited path that says what you think.** This check answers
  existence only. A stale figure inside a file that does exist is a different problem.

## References

- `batch-merge-subject-is-not-evidence-a-member-landed` — the other batch-hygiene check
- `inherited-scope-doc-names-may-not-exist` — same shape, scope documents rather than batches
- `git-diff-2dot-vs-3dot-merge-safety` — why Step 1 and Step 2 use three dots
