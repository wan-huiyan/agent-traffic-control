---
name: waiter-pgrep-matches-its-own-command-line
description: |
  You are about to trust a process search on a machine several sessions share:
  a wait loop that spins until some pattern stops matching, a liveness check
  before deleting a worktree or killing a run, or a "is the other session still
  going?" question answered from `ps`. The harness runs every shell command
  inside a wrapper shell whose argv carries the whole command text, so your
  pattern is present in the argv of the shell doing the searching, and in every
  other session's wrapper that merely mentions the same words. Use when a wait
  loop never exits, when a check reports something busy that you believe is
  idle, when you are about to kill or skip something because a process list
  said it was in use, or when you are deciding from `ps` whether a peer session
  is alive. The search finds the searcher, and a bare count cannot tell you
  which hit is the real work.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Waiter's Process Search Matches Its Own Command Line

## Problem

You want to know whether something is still running — a peer session's test
leg, a build, your own backgrounded gate run — so you search the process list
for it. **The search is itself a process, and on this harness its command line
contains the pattern you are searching for.**

Every shell command the Bash tool runs is wrapped in a shell invoked as
`/bin/zsh -c '<the whole command text>'`. That text includes your pattern. So:

- `pgrep -f "<pattern>"` matches the wrapper shell running that very `pgrep`.
- A wait loop never exits. `until ! pgrep -f "xcodebuild test -scheme X"; do sleep 30; done`
  is waiting for itself to stop existing.
- On a shared machine it also matches **every other session's wrapper** that
  merely mentions the same words — including a session that only printed the
  command, or grepped for it, and never ran it.

**Measured, 2026-09-17.** A session checked whether its own gate legs were
still going (the suite names below are generalised; the shape is what matters):

```
pgrep -fl 'pytest (unit|api|docs|e2e)' | head -3
```

The first line it returned was not a test process:

```
31853 /bin/zsh -c source /Users/me/.claude/shell-snapshots/snapshot-zsh-….sh 2>/dev/null || true && …
```

A wrapper shell, carrying the pattern in its own argv. With `| head -3` and no
`-l`, that line is indistinguishable from a real hit — and with `pgrep -q` or
`| wc -l` it is invisible.

**It fails in both directions, and the noisy one is not the dangerous one.**

| Reading | What it does to you |
|---|---|
| False BUSY | The waiter never exits. A cleanup skips a worktree whose owner died hours ago. You decline to start a leg because "another session is running it". |
| False ALIVE | You report a run still in progress after it finished, because what matched was a wrapper — or a PID the OS has since recycled. |
| False "two of mine" | Double counting: the work plus the shell that went looking for it. |

The false-busy readings are the ones nothing corrects, because a waiter that
is still waiting looks exactly like a job that is still running.

## Context / Trigger Conditions

Reach for this when:

1. a wait loop has not exited long after the thing it waits for should have
   finished — especially if the log it should be following stopped growing;
2. a liveness check says busy while nothing is producing output (the log's
   mtime is not moving, CPU is idle);
3. you are about to kill, delete or skip something because a process search
   said it was in use;
4. you are deciding whether a peer session is alive from `ps` alone;
5. a bracketed pattern is in play and the regex has more than one alternative;
6. a timing gate went red on a machine several sessions share.

## Solution

### Step 1 — Print what matched; never trust a count

```bash
pgrep -fl "<pattern>"                      # -l, so you can SEE each hit
ps -o pid,ppid,etime,command -p <pid>      # then read the ones you kept
```

A hit whose command begins `/bin/zsh -c` is a wrapper, not the work. A bare
`pgrep -q`, `| wc -l` or `| head -3` cannot make that distinction, and each of
them turns a wrapper into a confident yes.

### Step 2 — The bracket trick protects exactly one alternative

`grep -E "[x]codebuild"` stops that one word matching the grep's own line. It
does nothing for the rest of the pattern: a waiter's command line usually also
carries the command it is queued to run next, so it can still self-match on a
**different alternative of the same regex**. Either give every alternative the
same treatment, or stop matching text altogether (Steps 4 and 5).

### Step 3 — Filter on `args`, never on `comm`

`ps -eo comm,args` truncates `comm` for long interpreter paths, so a filter on
that first field can match **zero** processes while five real ones are running
— and zero reads as "all clear". Match on `args`.

### Step 4 — Decide ownership by working directory, not by argv text

```bash
lsof -a -p <pid> -d cwd -Fn      # where the process actually is
ps -o lstart= -p <pid>           # when it started
```

Argv *shape* — `-q -m not slow` versus `-m not slow -q` — is a fact about
someone's typing habits, not about ownership. On a fleet doing the same work,
a command line you would swear is yours belongs to a peer. The cwd says which
worktree it is in, and a process that started at a moment you launched nothing
cannot be yours: your own transcript records when you launched what.

### Step 5 — For status, use a PID you recorded, not a pattern

Capture the PID at launch (`$!`, or read it once from `ps` and keep it), then
ask `ps -p <pid>` from then on. Pair it with the start time: a PID can be
**recycled** by the OS, so a bare "the PID still exists" is not "my job is
still running" — `ps -o lstart=,command= -p <pid>` settles both at once.

### Step 6 — Kill by PID, never by pattern

`pkill -f "<anything>"` is safe on a shared machine exactly until a second
session runs a command whose line is a superset or a subset of yours.
Specificity buys nothing against a fleet doing the same work. Identify
read-only first (Steps 1 and 4), then kill the one PID you have traced to your
own launch. Better still, do not kill: a contended run is slower, never wrong,
and a stale one exits on its own.

### Step 7 — Prefer a signal the work itself writes

The reliable completion signal is not a process list. Have the run write a
sentinel as its last line, and watch that file's contents and mtime. It cannot
match itself, it survives the waiter being killed, and it distinguishes
"finished" from "died" — which no process search can do, because both look
like absence.

## Verification

**Run the waiter's condition once while the resource is definitely busy and
confirm it reports busy. A waiter that cannot report busy is not a waiter** —
and a condition that can only ever say "clear" passes every test you were
going to run.

Then the self-match test, which takes one command:

```bash
pgrep -fl "<pattern>"                                  # everything that matched
pgrep -fl "<pattern>" | grep -v ' /bin/zsh -c '        # with wrappers removed
```

If the second is empty and the first was not, every hit was a shell, and the
answer you were about to act on was about your own command.

## Example

**The gate check above.** The session read the first three hits of
`pgrep -fl 'pytest (unit|api|docs|e2e)'` to decide whether its
legs were still running. Hit one was a `/bin/zsh -c` wrapper carrying the
pattern. The question it was asking — *is the leg still going?* — was
answerable from the log file it was already tailing, whose last line and mtime
say both whether the run is alive and how far it has got.

**The loop that cannot end.** `until ! pgrep -f "xcodebuild test -scheme X"; do sleep 30; done`
never exits on this harness. The waiting shell's own argv contains
`xcodebuild test -scheme X`, so the condition it is polling is guaranteed true
for as long as the waiter exists. Nothing errors, nothing times out; the
session simply sleeps until something else kills it.

## Notes

- **`| grep -v pgrep` does not fix this.** It removes the `pgrep` process
  itself. It does not remove the wrapper shell that carries the pattern —
  those are two different processes, and only the second one looks like a
  real hit.
- **A slow leg on a shared machine is contention before it is your diff.** Two
  sessions' test legs inflate each other's wall clock; one measurement on
  2026-09-02 recorded a **6.8× slowdown with identical pass counts** — pure
  machine load. Read `uptime` and the process list before filing a timing
  failure against your branch.
- **Absence is not death.** A process search that finds nothing cannot tell
  "finished", "killed" and "never started" apart. Only an artefact the work
  wrote can.
- Sister skills: `git-auto-maintenance-recurring-worktree-index-lock` decides
  whether a lock's holder is alive and prints a process search to do it;
  `safe-bulk-worktree-branch-cleanup` asks the same question before removing a
  worktree; `subagent-external-wait-orchestrator-takeover` is the layer above
  — whether the polling should be happening in that session at all.

## References

- `pgrep(1)`, `pkill(1)` — pattern matching is against the full argv with `-f`,
  which is what makes the searcher a candidate.
- `ps(1)` — `comm` is truncated; `args` is not.
- `lsof(8)` — `-d cwd` is how you learn which checkout a process is working in.
