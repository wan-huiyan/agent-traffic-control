---
name: conflicted-pr-starts-no-ci-run-push-resolution-first
description: |
  A conflicted pull request stops producing NEW CI runs for as long as the
  conflict stands, because the provider rebuilds the synthetic merge ref
  whenever either side moves and cannot build it for a conflicting PR. The run
  list is usually NOT empty: it still holds the head's PRE-conflict run, and
  that run's red is then read as the blocker. Use when: (1) a landing script
  refuses to step a PR and prints something like `DRAFT  UNKNOWN (git:
  CONFLICTED vs origin/main <sha>)  gates=failure  auto-merge=NOT armed`, (2)
  the newest run on your head predates the base branch's last merge and no new
  one arrives, (3) `gh pr view N --json mergeable,mergeStateStatus` returns
  `UNKNOWN` and you are about to read that as "not conflicted", (4) a
  coordinator reports it cannot land your work because it is "conflicted, not
  merely behind". Two of the three fields in that status line are non-facts:
  the red required check can be a draft's designed red or a stale pre-conflict
  run, and `UNKNOWN` most often means only "not recomputed since the base
  moved". The fact is `git merge-tree`. Push the resolution IMMEDIATELY —
  before your local test legs finish — because the push is what lets a run
  start at all, and the cheap draft run then clears the whole-diff guards in
  about ninety seconds while the legs are still going. NOT for a PR that is
  merely BEHIND (nothing to resolve), and NOT for a run that is only slow to
  be created.
author: Claude Code
version: 1.0.0
date: 2026-09-17
disable-model-invocation: true
---

# A Conflicted PR Starts No CI Run — Push the Resolution First

## Problem

Your pull request is conflicted. Someone — a coordinator, a landing script, or
you — reads its status and sees three fields:

```
#1234  DRAFT  UNKNOWN (git: CONFLICTED vs origin/main abc1234de)  gates=failure  auto-merge=NOT armed
```

**Two of those three are non-facts.** The required check is red because the PR
is a draft (in repos where a draft's required context is deliberately red) or
because the newest run on that SHA is a *stale* one that died — either way it is
not the blocker. `UNKNOWN` is not "not conflicted": the provider invalidates
mergeability for every open PR each time the base moves and returns `UNKNOWN`
until it recomputes, which is the usual cause on a busy base. The only fact in
the line is the parenthesis, which came from `git merge-tree`.

The expensive half is what is *missing*: **no NEW run is created for as long as
the conflict stands.** A `pull_request` workflow runs against the synthetic
merge ref, and the provider rebuilds that ref whenever either side moves — so
when the two genuinely conflict there is nothing to check out and no run is
created. Waiting produces nothing. `update-branch` cannot fix a conflict. An
empty commit does nothing for one either.

**And the run list is probably not empty, which is the part that misleads.**
The head keeps whatever run it earned when it was first pushed, *before* the
base moved and the conflict arose. Measured on the incident below: the
conflicted head's run list held exactly one run, created the previous day, whose
`changes` job had SUCCEEDED and whose only red job was the draft's designed-red
aggregator. So the queue script's `gates=failure` was a true reading of a run
that had nothing to do with the conflict, and a session checking
`total_count` gets a reassuring non-zero answer. **What is diagnostic is the run's
AGE, not the count** — compare the newest run's `created_at` against the base
branch's last merge.

## Context / Trigger Conditions

- A landing or queue script **stops rather than stepping** a PR, and says
  conflicted where its other fields say `UNKNOWN`
- The newest run on your head is **older than the base branch's last merge**
   and no new one arrives:
   `gh api "repos/O/R/actions/runs?head_sha=<full 40-char sha>" --jq '.workflow_runs[0].created_at'`
- Or `total_count` is `0` outright, which is the narrower case where the head
  was already conflicting the first time it was pushed, so it never had a
  buildable merge ref at all (an abbreviated SHA also returns `0` regardless —
  that is a different trap)
- `gh pr view N --json mergeable,mergeStateStatus` returns `UNKNOWN`, or flips
  between `UNKNOWN` and `CONFLICTING` on consecutive calls
- The repo requires branches to be up to date before merging, so every merge to
  the base invalidates everyone's mergeability at once
- A peer is waiting on you: whoever drives the landing script **cannot** clear
  this, because resolving a conflict is a judgement call about content

## Root cause

Two mechanisms stacked, which is why the status line reads as three problems
instead of one:

1. **No merge ref, no new run.** On a `pull_request` event the provider checks
   out the auto-computed merge of head plus base. It recomputes that ref
   whenever either side moves — and when the two genuinely conflict it cannot
   produce it, so no further run is created. Nothing reports an error. **The
   run list is not emptied, though**: whatever the head earned before the
   conflict arose stays there, which is why a bare `total_count` is not the
   check. *What would show this wrong:* a run on the conflicted head whose
   `created_at` is LATER than the base branch's last merge. If you ever see
   one, this mechanism is not what you have. (The sister skill
   `gha-pr-merge-ref-shows-upstream-changes` covers the same ref when it *can*
   be built and surfaces a collision your branch alone does not have.)
2. **Mergeability is computed lazily.** `UNKNOWN` is not an answer in either
   direction — it is "not computed yet". On a busy base branch the commonest
   cause is simply that the base moved and nothing has recomputed since, so a
   reading taken right after someone else merges says nothing at all. It is not
   the only possible cause (a very large diff or a provider incident can leave
   it unresolved too), and nothing in the field distinguishes them — which is
   the reason to stop reading it and ask git instead, rather than a reason to
   believe any particular story about it.

## Solution

### Step 1 — Ask git, not the provider

```bash
git fetch origin main --quiet
git merge-tree --write-tree origin/main HEAD >/dev/null \
  && echo "MERGEABLE" || echo "CONFLICTED"
```

`merge-tree` cannot be invalidated by somebody else's merge, so it answers when
the API will not. Record the base SHA beside the verdict — a mergeability
verdict without the two SHAs it was measured against cannot be checked later.

### Step 2 — Resolve locally, and merge rather than rebase if the base is shared

```bash
git merge origin/main -m "Merge main (<base sha>) into <branch>"
# resolve, then verify the resolution by COUNTING, not by eye:
#   the merged file must equal base plus exactly your own additions
```

A conflict in a shared, hand-edited aggregate file (a tracker, a changelog, an
index) is the common case, and the bridge between two hunks is where a row goes
missing while the JSON still parses. Count the arrays on both sides and on the
result before committing.

### Step 3 — Push the resolution BEFORE your local test legs finish

This is the step that is usually done last and should be done first:

- **It is what lets any run start at all.** Until the push lands, the PR cannot
  produce a result for anyone to read, and a queue driver cannot step it.
- **The cheap run buys a real check while you wait.** In a repo where a draft
  skips the expensive suites, the draft run still executes the whole-diff guards
  — the checks that read your PR body's declarations and the whole diff for
  silent deletions or rollbacks. Measured on the incident below: that job
  finished green in **1m14s** and **1m26s** on two successive resolutions, while
  six local suite legs still had minutes to run. A wrong declaration is then
  found for a draft's price instead of a full matrix's.

```bash
git push origin <branch>
gh api "repos/O/R/actions/runs?head_sha=$(git rev-parse HEAD)" --jq '.total_count'
```

### Step 4 — Distinguish "no run" from "slow run" before concluding anything

An absent run is only evidence of the conflict while the conflict stands. A run
can also simply be **slow to be created**: measured elsewhere in the same repo,
one took **6m23s** to appear, and an empty commit pushed as a "retrigger"
cancelled the legitimate run that was about to start. So the discriminator is
`merge-tree` plus the clock, never the empty run list alone:

```bash
# re-ask after ten minutes, with the FULL sha
gh api "repos/O/R/actions/runs?head_sha=<40 chars>" --jq '.total_count'
```

### Step 5 — Hand the new head SHA to whoever drives the queue

They are blocked on the push, not on your legs. Send the SHA and say which
checks you have and have not run yet.

## Verification

1. A run exists on the new head **whose `created_at` is after your resolution
   push** — not merely `total_count >= 1`, which can already be satisfied by a
   pre-conflict run and was, in the incident below.
2. `gh pr view N --json mergeable` reads `MERGEABLE` — re-ask if it says
   `UNKNOWN`; that is the field's "not yet", not a verdict.
3. The cheap run's whole-diff jobs conclude `success`.
4. The queue script now **steps** instead of stopping.

## Example

Observed 2026-09-16 in the repository this came from, on one pull request: a
runtime change to a single API handler, plus its records wrap-up. The base moved twice in one
morning while the PR was queued, so the same sequence ran twice. **Every figure
below was re-read from the Actions API rather than carried in prose.**

**While it was conflicted, the run list was not empty.** `total_count` on the
conflicted head was **1**, and that single run had been created **the previous
day**, when the head was first pushed and still merged cleanly. Its `changes`
job had SUCCEEDED; its only red job was the aggregated required context, which
this repo makes red on a draft by design, and every suite leg was skipped. That
run is the entire content of the `gates=failure` the queue script reported — so
the status line was three fields about a conflict, a draft convention and a
day-old run, none of them about anything you could fix by waiting.

**First resolution.** The conflict was one line in a shared hand-edited data
file (the `updated` stamp every wrap-up branch touches) plus a list where the
base had added four newer rows. Resolved, counted, committed at **08:30:00Z**
and pushed before the six local legs had finished. A run appeared on the new
head at **08:32:19Z**, and its whole-diff guard job ran **08:32:22Z →
08:33:36Z — 1m14s** — green, while the legs ran on.

**Second resolution, ninety-two minutes later**, after the base moved again:
identical shape, one conflicted hunk. Committed **10:01:50Z**; the run was
created **10:02:20Z — thirty seconds after the commit** — and its guard job ran
**10:02:22Z → 10:03:48Z, 1m26s**, green again.

**What the ordering bought, as one number.** That second guard cleared at
10:03:48Z. The branch could not be flipped for readiness until the local legs
finished, and the readiness run was not created until **10:17:57Z — fourteen
minutes later**. So pushing the resolution first bought fourteen minutes of
whole-diff guard coverage that would otherwise have been dead waiting time, and
it bought it on both resolutions at a draft's price. The full matrix then went
green at 10:38:37Z and the PR merged on it.

## Notes

- **A red required check on a draft can be by design.** Some repos deliberately
  make the aggregated context red on a draft so a vacuous green cannot merge.
  Read the job's own log before treating it as the blocker.
- **`mergeStateStatus: BLOCKED` is not trouble either** — it is the normal state
  of a healthy PR whose run is still going.
- **Do not rebase a branch whose base is shared and squash-merged**; merge. A
  rebase rewrites SHAs a peer may already be quoting, and after a squash the
  ancestry check that would "confirm" the rebase cannot return yes anyway.
- **Never carry a resolution's line numbers forward by arithmetic.** If either
  side moved code that another file cites by line, re-grep the anchor on the
  merged bytes — see
  `clean-merge-lands-line-guard-on-a-value-neither-branch-predicted`.

## See Also

- `pr-conflict-from-mid-flight-merges` — the recovery recipe once you are
  resolving: what landed, what of yours is redundant, and how to get back to a
  clean tree. This skill is its missing precondition: while the PR is
  conflicted, nothing is reporting.
- `gha-pr-merge-ref-shows-upstream-changes` — the same synthetic merge ref when
  it *can* be built.
- `gh-pr-merge-unstable-state-needs-auto-and-watch-branch-deletes` — the
  opposite confusion: the CLI cries "conflicts" when there are none.
- `merge-queue-thrash-stop-inflow-and-open-prs-as-drafts` — why the base keeps
  moving under you in the first place.
