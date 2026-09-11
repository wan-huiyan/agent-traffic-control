---
name: ci-leg-skipping-moves-minutes-it-does-not-remove-them
description: |
  You are about to propose, price or approve a CI cost saving that works by
  making a job or matrix leg SKIP on pull requests — a path filter, a safe
  list, a changed-files gate, an exemption list. Check first whether the
  pipeline runs a complement or backstop on merge, on push, or nightly:
  many do, and then the legs a pull request skipped are exactly the legs some
  later run executes, so a branch that goes green once and merges bills the
  same total either way and the wall clock does not move at all. Use when
  pricing a filter change, when a percentage saving is quoted with no basis,
  or when choosing between filtering legs and batching pull requests. The
  question that separates money from bookkeeping is whether the change
  removes RUNS or merely moves LEGS.
version: 1.0.0
date: 2026-09-11
author: wan-huiyan
disable-model-invocation: true
---
# Skipping a CI Leg Moves Its Minutes, It Does Not Delete Them

## Problem

The bill is too high, so someone proposes the obvious fix: this job does not
need to run on this kind of change, so filter it out and save its minutes.
The reasoning is clean, the change is small, and it is usually wrong.

**A leg removed from the pull-request run is not a leg removed from the
bill if the pipeline runs it somewhere else.** Many pipelines deliberately
carry a backstop: the merge or push run executes the COMPLEMENT of what the
pull-request run skipped, precisely so that a wrong filter cannot make a leg
stop running anywhere. Under that design the minutes are redistributed, not
deleted.

**For a branch that is made ready once and merges, the total is unchanged.**
The saving exists only from the SECOND ready run onward, and its size is:

```
saving = (ready runs − 1) × the skipped legs' minutes
```

So a change that looks like "we no longer pay for this leg" is really "we pay
for this leg once per merge instead of once per ready run", and on a branch
that lands first time those are the same number.

**And on wall clock it usually saves nothing at all.** Matrix legs run in
parallel, so removing a leg that was never the long pole changes the pull
request's wall clock by zero — while making the merge run longer. Wall-clock
minutes and billed minutes are different quantities with similar digits, and
quoting one while meaning the other is how a saving gets approved twice.

## Context / Trigger Conditions

You are in the right place if any of these is true:

- Someone proposes a path filter, safe list, changed-files gate or exemption
  list whose stated benefit is the removed job's minutes
- A saving is quoted as a percentage or a minute count with no basis named
- The pipeline has a merge, push, nightly or merge-queue run whose job set is
  derived from what the pull-request run did — a complement, a backstop, an
  unfiltered sweep
- You are choosing between two cost proposals and one of them removes whole
  runs (batching, fewer ready flips, cancelling superseded runs) while the
  other rearranges legs within a run

**The reasoning this retires**, in its exact intuitive form: *"this leg does
not need to run here, so we save its minutes."* Whether that is true is a
property of the whole pipeline, never of the leg.

## Solution

### Step 1 — Find out where the leg still runs

Before pricing anything, enumerate every trigger that can execute the leg you
are about to filter: pull request, push to the default branch, merge queue,
scheduled run, manual dispatch. Read the workflow rather than remembering it.

```bash
grep -n "^on:" -A 20 .github/workflows/<workflow>.yml
grep -rn "complement\|exempt\|backstop\|schedule:" .github/workflows/ .github/scripts/
```

A leg named in more than one trigger has not been removed from the bill by a
pull-request filter. It has been moved.

### Step 2 — Price it with the arithmetic above, per branch

You need three numbers, and all three are per branch rather than global:

1. **Ready runs to land** — how many times this branch actually fired the
   full matrix. Read it from the API, do not assume one.
2. **The skipped legs' billed minutes** — per job, rounded UP to the whole
   minute if your provider bills that way, taken from the same runs.
3. **Whether the merge or backstop run then executes them.** If yes, subtract
   one run's worth: that is the leg coming back.

Then `(ready runs − 1) × skipped minutes` is the saving for that branch. Do
this over a real sample of branches, not a representative one.

### Step 3 — Report the zeros, not just the mean

A mean over branches hides the shape. Branches that land on the first ready
run save EXACTLY ZERO, and there are usually more of them than expected. A
saving quoted as an average, on a distribution where half the cases are zero,
is a true number that misleads whoever is spending the money.

### Step 4 — Name the basis in the same sentence as the figure

Write "billed minutes" or "wall clock" beside every number. They diverge here
by design: this class of change can move billed minutes while leaving wall
clock untouched, and a reader who assumes the other basis will conclude the
pipeline got faster when it did not.

### Step 5 — Ask the question that actually separates the two kinds

> **Does this proposal remove RUNS, or does it merely move LEGS?**

- **Removing runs is money.** Landing several small pull requests in ONE run
  instead of N. Not flipping a branch ready until it is actually next to
  merge. Letting a superseded run be cancelled instead of updating a branch
  mid-run. Fixing whatever makes a branch take several attempts to land.
- **Moving legs is bookkeeping.** Path filters, safe lists, exemptions,
  matrix trimming — real work, sometimes worth doing for wall clock or for
  queue pressure, but do not book it as savings without Step 2.

**Where the money usually is:** the number of runs it takes to land one
change. If that average is well above 1, it dominates every leg-level saving,
because each extra run pays for the WHOLE matrix rather than for one leg.

### Step 6 — Keep the backstop honest if you do filter

A complement or backstop is what makes a wrong filter safe, so do not weaken
it while chasing its minutes. If a leg's only remaining home is the merge run
or the nightly sweep, that run is now load-bearing rather than
belt-and-braces: losing it stops the leg running anywhere at all, silently.

## Verification

A correctly priced proposal states, for a named sample of branches:

```
sample: 6 branches, real merged file lists, ready-run counts from the API
basis:  BILLED minutes, each job rounded up to the whole minute

before 270 billed minutes   after 254   saved 16 across the sample
per branch 45.0 -> 42.3 billed minutes, about 6%
3 of the 6 save EXACTLY ZERO (single ready run)
wall clock: unchanged — the removed legs were never the long pole
```

If the write-up has a percentage but no basis, no sample size, and no mention
of the zero cases, it has not been measured — it has been reasoned.

## Example

*Worked example from a route-generation repository whose CI bill was the
subject of an owner ruling. The pipeline's own script names are that repo's;
the pattern is not.*

That repository's merge run passes a `--complement` flag to the script that
decides which legs to run: on a push to the default branch it executes exactly
the legs a pull-request run over the same diff would have SKIPPED, and nothing
else. That design exists so a wrong safe list cannot silently stop a leg
running, and it is the reason a pull-request filter there moves minutes rather
than deleting them.

A proposal to make two legs skip on a class of pull requests was priced over
six real branches, using their actual merged file lists, their actual ready
run counts from the API, and per-leg billed minutes from those same runs:

| | billed minutes |
|---|---|
| before | 270 across six branches |
| after | 254 |
| saved | 16, about 6% |
| per branch | 45.0 → 42.3 |
| branches saving zero | **3 of 6** |

**On wall clock it saved nothing.** The matrix's long pole was a different leg
at a median 604 s; the two candidates for removal ran 185 s and 136 s, well
inside it. Removing them changed the pull request's wall clock by zero and
made the merge run longer.

**The contrast that settled where to spend the effort.** In the same
repository a pull request averaged **3.7 runs to land one change**, and four
small pull requests landed together in a single run on 2026-09-11 saved
roughly **90 billed minutes** — several times the six-branch total above, from
one act of batching. Batching deletes runs. Filtering redistributes legs.

## Notes

- **This is not an argument against filters.** A safe list that keeps a slow
  leg off unrelated pull requests can still be worth having for queue pressure
  and for feedback time. The point is to book it under the right heading and
  not to spend a decision-maker's trust on a number that is mostly zeros.
- **The same shape appears one layer up.** Moving a leg from the pull request
  to the merge run, and then from the merge run to a nightly sweep, each time
  looks like a saving and each time is a relocation — until the last hop,
  where it stops running per change at all and the trade becomes coverage
  timing rather than money.
- **Ask where a leg went, not whether it left.** "This job no longer runs on
  pull requests" is a true sentence that answers a different question from
  "this job costs less per week".
- **When the person reading the number is spending real money**, say plainly
  which cases save nothing. A range with its zeros visible survives contact
  with a sceptical reader; a flattering mean does not.
- **The worked instance of the RIGHT kind of saving** is
  [`merge-queue-thrash-stop-inflow-and-open-prs-as-drafts`](../merge-queue-thrash-stop-inflow-and-open-prs-as-drafts/SKILL.md):
  opening every pull request as a draft and promoting it only when it is next
  to land removes whole RUNS, and measured about 46 seconds against about 16
  minutes for a full one. Read the two together — that skill is what to do,
  this one is why the other lever does not pay.
- **A different ledger with the same trap** is
  [`fan-out-cost-control`](../fan-out-cost-control/SKILL.md), which prices a
  fan-out's token budget rather than CI minutes. Both go wrong the same way: a
  saving that is reasoned from one unit and never measured in the unit that is
  actually billed.
- **The correctness side of the same lever** is
  [`merged-pr-not-deployed-gate-label-missing`](../merged-pr-not-deployed-gate-label-missing/SKILL.md):
  a path filter that quietly excludes your files stops a workflow running at
  all. This skill asks what a filter costs; that one asks what it breaks. Both
  questions are owed before a filter ships.
- **Round up per job if your provider does.** Several sub-minute jobs each
  billed as a whole minute is its own line in the bill, and it is one of the
  few leg-level changes that genuinely removes cost — merging two tiny jobs
  that each pay a rounded minute for seconds of work.

## References

- GitHub docs: [About billing for GitHub Actions](https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions)
  — minutes are rounded up to the nearest whole minute PER JOB, which is why
  billed minutes and wall-clock minutes diverge.
- GitHub docs: [Using conditions to control job execution](https://docs.github.com/en/actions/using-jobs/using-conditions-to-control-job-execution)
  — job-level conditions are how a leg is skipped on one trigger while still
  running on another.
- GitHub docs: [Using concurrency](https://docs.github.com/en/actions/using-jobs/using-concurrency)
  — superseded runs are billed for what they ran before being cancelled, which
  is a run-level cost and therefore the kind worth attacking.
