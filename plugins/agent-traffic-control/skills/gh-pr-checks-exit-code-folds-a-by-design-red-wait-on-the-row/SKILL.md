---
name: gh-pr-checks-exit-code-folds-a-by-design-red-wait-on-the-row
description: |
  `gh pr checks` returns ONE exit status for the whole pull request, so a check
  your repo keeps red ON PURPOSE — a required aggregation context that is red
  while a PR is a draft, a placeholder context, a job the workflow allows to
  fail — makes the command exit non-zero on a pull request where everything
  that actually ran passed. Use when: (1) you are writing a background wait loop
  or watchdog that polls a PR and decides from `$?`; (2) a background poll came
  back "failed with exit code 1" and you are about to diagnose a red that may
  not exist; (3) you are about to report a PR as failing, or hold a queue on it,
  on the strength of an exit status; (4) your repo deliberately reds a context
  on drafts so a draft cannot merge on a green no suite produced. The exit code
  cannot tell a by-design red from a real one, and a non-zero exit from a
  backgrounded poll is surfaced by the harness exactly like a failing job.
  Poll the ROW for the check you care about and exit 0 yourself; `8` means
  pending, not failure; and confirm a red is the by-design one by reading that
  job's log, not by assuming it.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# `gh pr checks` Folds a By-Design Red Into One Exit Status — Wait on the Row

## Problem

You want a session to keep working while a pull request's cheap checks finish, so you
background a poll and let the harness notify you when it exits. The obvious loop ends with
`gh pr checks <n>` and trusts its exit status.

On a pull request where **everything that ran passed**, that loop reports failure — because
one context is red on purpose and the exit status has no room to say so. The notification
reads `failed with exit code 1`, which is indistinguishable from the run genuinely going
red, so the next thing the session does is diagnose a defect that does not exist, or hold a
landing queue on a branch that is fine.

## Context / Trigger Conditions

- You are writing a wait loop, watchdog, or `until`-style poll around a pull request.
- A repo keeps a **required aggregation context red while the PR is a draft**, so that a
  draft cannot merge on a green produced by jobs that never ran. (This is a real and good
  pattern: the aggregate job prints a line in its own log saying it is red because the PR is
  a draft and no test suite has run on the code.)
- A workflow has a job that is **allowed to fail**, a placeholder context, or a check that a
  third-party app posts as failed until a human acts.
- A background command you started returned non-zero and the harness told you it FAILED.
- You are about to write "the checks are failing" into a report, an issue, or a peer message.

## Solution

### Step 1 — Read the exit-code table before you key anything on it

```bash
gh pr checks --help | sed -n '/Additional exit codes/,+3p'
```

Measured on `gh` 2.97.0: **`0`** every check passed, **`8`** checks are still pending,
**`1`** something is not passing. A loop written as `until gh pr checks "$PR"; do sleep 30;
done` therefore treats *pending* and *failed* the same way, and treats a by-design red as a
reason to keep waiting forever.

### Step 2 — Poll the row for the check you actually care about

```bash
# The per-check rows are TSV: name, state, elapsed, link.
state() { gh pr checks "$1" 2>/dev/null | awk -F'\t' -v n="$2" '$1==n{print $2}'; }

for _ in $(seq 1 40); do
  s=$(state "$PR" "$CHECK")                # $CHECK = the job whose verdict you want
  [ -n "$s" ] && [ "$s" != "pending" ] && break
  sleep 30
done
echo "$s"                                   # and exit 0 yourself
```

`gh pr checks <n> --json name,state,bucket` is the structured form where available;
`--required` narrows to required contexts, which is usually what a queue cares about.
Whichever you use, **the loop's own exit status must be something you set**, not something
`gh` handed you about a different check.

### Step 3 — Name the by-design red, once, in the script

Keep the list of contexts your repo reds on purpose next to the waiter, and treat any OTHER
red as real. A waiter that ignores every red is worse than one that trusts the exit code.

### Step 4 — Confirm a red is the by-design one from its log, never by assumption

```bash
gh run view <run-id> --job <job-id> --log | grep -i "draft"
```

The aggregate job that is red on purpose says so in words. If the grep finds nothing, you
have a real failure wearing a familiar name.

## Verification

On a pull request whose expensive suites are skipped and whose cheap checks are green:

```bash
gh pr checks "$PR" > /dev/null; echo "exit=$?"     # exit=1, and nothing is wrong
gh pr checks "$PR" | awk -F'\t' -v n="$CHECK" '$1==n{print $2}'   # pass
```

Exit 1 beside a passing row is the whole finding. Then run your waiter against the same
pull request and confirm it exits 0 and prints the row's state. A waiter you cannot make
exit 0 on a healthy draft has not been tested.

## Example

A draft pull request, measured 2026-09-17. The rows:

| check | state | note |
|---|---|---|
| whole-diff guard job | pass (1m33s) | the only job a draft runs |
| label check | pass | |
| test-suite matrix | skipping | skipped on drafts by policy |
| node suites | skipping | skipped on drafts by policy |
| aggregate required context | **fail** | red on drafts **by design** |

`gh pr checks` → exit 1. The background poll that ended on that command was reported as
`failed with exit code 1`, and the first reading was that the fix had broken something. It
had not: the aggregate context's own log carries the sentence explaining that it is red
because the pull request is a draft and no suite has run on the code.

## Notes

- **The same fold bites `--watch --fail-fast`**, which exits the moment the by-design red
  appears — on a draft, that is immediately.
- **This is the same shape as a waiter's process search matching its own command line**: the
  instrument answers confidently about something adjacent to the question. See
  [`waiter-pgrep-matches-its-own-command-line`](../waiter-pgrep-matches-its-own-command-line/SKILL.md).
- **A red context is not the only mis-read available on a pull request.** A conflicted PR
  starts no new run at all, so its newest run — and its checks — can be a day old and still
  answer:
  [`conflicted-pr-starts-no-ci-run-push-resolution-first`](../conflicted-pr-starts-no-ci-run-push-resolution-first/SKILL.md).
- **Do not "fix" this by making the by-design context green.** A required context that is
  green over an empty set is how a pull request merges on a result no suite produced; the red
  is the safer failure and exists deliberately. Fix the reader, not the signal.

## References

- `gh pr checks --help` — the `Additional exit codes` block (`8: Checks pending`).
- [`solo-repo-branch-protection-stable-gate-and-self-merge`](../solo-repo-branch-protection-stable-gate-and-self-merge/SKILL.md)
  — why a required check is an *aggregation* context rather than a matrix leg, which is what
  puts a single by-design red in front of every waiter.
