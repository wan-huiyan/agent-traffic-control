---
name: parallel-gate-legs-killed-for-memory-count-cannot-see-ram
description: |
  Two sessions run local test legs on the same machine and one session's leg is
  killed for memory mid-run, while the concurrency guard everybody uses — a
  count of running test processes — reads well inside its limit the whole time.
  Use when: (1) a background test run ends with a harness notice like "stopped
  because the system is running low on memory" and its log simply stops, with no
  traceback, no summary line and no exit code, (2) you are about to re-report
  that leg as RED, (3) your "at most N heavy legs" rule keeps letting a second
  leg start next to a peer's, (4) a process-count check reads 2 while exactly
  one leg is running, so "start only if the count is under 2" can never be
  satisfied, (5) a free-memory percentage looks comfortable while the machine is
  actually swapping. The count is a CPU and contention rule and cannot see RAM;
  the same leg that dies in the background completes in the foreground. A killed
  leg is not a failed leg — re-run it and read the result. NOT for a genuine
  test failure (those end with a recorded exit status), and NOT a licence to run
  two heavy legs at once because the count allows it.
author: Claude Code
version: 1.0.0
date: 2026-09-17
disable-model-invocation: true
---

# Parallel Gate Legs Killed for Memory — the Count Cannot See RAM

## Problem

Two sessions share one developer machine. Each runs the repo's local test legs
before pushing, and each obeys a concurrency rule of the form *"at most two
heavy legs machine-wide"*, implemented as a count of running test processes.

Your background leg dies. What you get is not a failure: the log **stops**, with
no traceback, no `N passed` summary and no exit status, and the harness says the
task was stopped because the system was low on memory. The count, sampled
throughout, read **1**.

Three wrong conclusions are one step away, and all three are natural:

1. **"My leg went red."** It did not run to a verdict at all.
2. **"My loop is broken."** The obvious fix — restart it — walks straight back
   into the same collision, because nothing about the machine changed.
3. **"The concurrency rule did not fire, so concurrency was not the problem."**
   The rule cannot see the resource that ran out.

## Context / Trigger Conditions

- A `run_in_background` test leg ends with a low-memory notice, or its output
  file ends mid-run with no summary
- A process-count check reads **2 for one leg**, so any "under 2" threshold is
  unsatisfiable (the cause is not the obvious one — see Root cause)
- Your rule is phrased "start only if the count is under 2", so it is
  unsatisfiable while any leg runs anywhere on the machine, yours or a peer's
- `memory_pressure`'s free-percentage headline looks healthy (40%+) while
  `Pages free` × page size is tens of megabytes and swap is nearly full
- A peer session is part-way through its own full leg script in another worktree
- The same leg, run alone in the foreground, finishes normally

## Root cause

**The guard measures the wrong resource.** A count of test processes is a CPU
and contention rule: it stops two suites fighting for cores and for a shared
fixture directory. Memory is not in it at all, so a machine with room for one
copy of the heaviest leg will happily admit a second and then kill one of them.

**And the count itself is unreliable — but not for the reason it looks like.**
The inflation is real and measured (one leg alone read **2**), and the tempting
explanation — that the pattern catches both a wrapper shell and the interpreter
it spawns — **did not hold up when it was checked**, so do not carry it. Two
contributors *were* isolated, both re-derivable with one command:

1. **A leg whose own tests spawn a test subprocess counts twice.** Measured:
   two interpreters, both with the same test-file argument and both parented to
   `1`, for a single leg running a test that launches its own runner.
2. **The pattern's CASE decides which processes you count**, because a
   virtualenv `python` execs a framework binary whose `argv[0]` is capitalised.
   On one machine, at one moment: `[P]ython -m pytest` matched **5** lines, all
   of them interpreters; `[p]ython -m pytest` matched **2**, both of them
   wrapper shells carrying the literal `.venv/bin/python …` command text; a
   case-insensitive match returned **7**, the sum. So the same machine reports
   5, 2 or 7 running legs depending on one letter of your pattern.

```bash
# the discriminator: read the lines and the parentage, never just the count
ps -axo pid,ppid,etime,command | grep -iE '[p]ython -m pytest'
```

**The failure is silent by construction.** A process killed by the OS or by a
supervising harness writes no summary, so the artefact of a kill looks much like
the artefact of a session that stopped early.

## Solution

### Step 1 — Read the lines, not the count

A bare count is the thing that misled everybody here, so do not build a
threshold on one until you have seen what it matches:

```bash
# case-insensitive, with parentage and elapsed time: one line per PROCESS
ps -axo pid,ppid,etime,command | grep -iE '[p]ython -m pytest'
```

Then count what you actually care about — **distinct top-level legs** — by
eye or by parent: sibling interpreters sharing a `ppid`, or sharing the same
test-file argument, are one leg. The elapsed column and the wrapper's own `cd
<path>` are the only things that say WHOSE leg it is; never kill or wait out a
peer's leg as if it were yours.

### Step 2 — Read real free memory, not a percentage

```bash
vm_stat | awk '/Pages free/  {gsub(/\./,"",$3); printf "free %d MB\n",     $3*16384/1048576}'
vm_stat | awk '/Pages inactive/ {gsub(/\./,"",$3); printf "inactive %d MB\n", $3*16384/1048576}'
sysctl -n vm.swapusage
```

A free-**percentage** headline is not free memory: one reading showed 43% while
about 60 MB was genuinely free and swap was 89% full. Do not use
`free + inactive` as "available" either when swap is already full — inactive
pages are not free at that point. Take several samples and report a range; free
memory swung 56–526 MB within minutes on the machine this came from.

### Step 3 — Put the guard inside the command that starts the leg

A check one round-trip earlier is already stale: a peer can start a leg in
between, so the reading you acted on described a machine that no longer exists.

```bash
# case-insensitive, so "zero" is genuinely zero whichever spelling is running
legs=$(ps -axo command | grep -icE '[p]ython -m pytest')
freemb=$(vm_stat | awk '/Pages free/ {gsub(/\./,"",$3); print int($3*16384/1048576)}')
[ "$legs" -eq 0 ] && [ "$freemb" -ge 200 ] && run_the_leg   # one command, no gap
```

Test for **zero**, not for "under N". Zero is the one threshold that survives
the counting problems above, because every contributor to the inflation adds
lines rather than removing them.

### Step 4 — Prefer the foreground for short legs, and never report a kill as red

Short legs (seconds to a minute) run in the foreground and cannot be reaped by a
background sweep. When a leg is killed, **re-run it and read the result**; a
killed leg carries no verdict, so reporting it as a failure publishes a claim
nothing measured.

**Record the exit status; do not infer a verdict from the log.** This is the
only check here that discriminates, because a kill is defined by how the
process ended:

```bash
run_the_leg >>leg.log 2>&1; echo "exit=$?" >>leg.log
# no `exit=` line at all  -> killed (or still running)
# exit=0                  -> green      | exit=1 -> failures
# exit=2                  -> pytest could not even collect: a REAL failure
```

**Do not use `grep -cE "[0-9]+ (passed|failed)"` as the kill test** — it is the
obvious check and it has two blind spots, both measured rather than supposed:

| Real outcome | What it prints | That grep says |
|---|---|---|
| pytest collection error (genuine failure, exit 2) | `1 error in 0.08s` | **0** |
| `node --test`, all green (exit 0) | `pass 1` / `fail 0` | **0** |

Both read identically to a kill, so a whole class of leg — any Node suite, and
any pytest leg that dies at import rather than at a test — would be re-reported
as RED. If you must parse a log, cover the real forms:

```bash
grep -cE "([0-9]+ (passed|failed|error|errors|skipped)|no tests ran|(pass|fail) [0-9]+)" leg.log
```

## Verification

- The leg you re-ran ends with a recorded **exit status**, and you quote that
  rather than the absence of a summary line.
- You have looked at the matched process LINES at least once on this machine and
  know what one leg looks like there. Do not assume one leg reads as 1 or as 2 —
  it depends on your pattern's case and on whether the leg spawns its own
  runner, so measure it with `ps -axo pid,ppid,etime,command` before any
  threshold rests on it.
- Starting a leg while a peer's is running, then reading free memory, shows
  whether the machine can actually hold both — the number, not the policy, is
  the evidence.

## Example

Observed 2026-09-16 on a 24 GB laptop with two sessions active. A six-leg local
run was launched in the background; the heaviest leg (four parallel workers)
completed, and the runner was then killed twice for memory while a peer session
ran its own full leg script from another worktree. The process count read **1**
at every sample, so the "at most two" rule never fired.

The same legs, started one at a time in the foreground once the machine was
quiet, all completed: the research-data leg in 42 s and the Node checks in 10 s,
with summary lines. Nothing about the code changed between the kill and the
pass — only the concurrency.

Two readings from the same incident worth carrying: the free-percentage headline
said 42–47% while `Pages free` was 115–143 MB, and a later measurement on the
same machine paired 43% against about 60 MB free with swap 89% full.

A third reading, taken on the same laptop the following day purely to re-check
these commands, makes the point without any incident at all: **five** pytest
interpreters were live across several sessions, `Pages free` was **58–68 MB**,
`Pages inactive` was 5.4 GB and swap was **85% full** — and nothing had been
killed yet. That is what the edge looks like while everything still appears to
be working, which is why the reading has to be taken before starting a leg
rather than after losing one.

## The same signature WITHOUT memory pressure — 2026-09-22

**A killed leg does not mean memory.** Read this before applying any remedy above,
because the artefact is identical and the cause was not.

Observed on the same laptop six days later: a `prototype` leg ended
`exit=-15 collected=None passed=None failed=None 537.19s` — SIGTERM, no JUnit
XML, no collected count. That is exactly what the memory kill looks like. But:

    system-wide memory free   81%       (not tight)
    Pages free                ~68 MB    (tight)
    load averages             8.40  14.01  11.44
    concurrent prototype runs 2 full suites, one with 4 xdist workers,
                              plus a six-file subset and a four-leg loop
                              = FOUR sessions in one suite

**So the discriminator is not the signal number and not the free percentage.**
`-15` is SIGTERM, which an OS memory kill does not normally send (`-9`), and the
skill's own note already says a `-9` beside a timeout is not evidence of memory
either. Both directions of that inference are wrong. What actually distinguishes
them is a measured reading taken at the time — swap, `Pages free`, and whether
anything else was competing for CPU.

**The better detector was not the log at all.** `gate_receipt.py check` refused
the run and named it precisely, where the leg table just showed a number:

    REFUSED  4 problem(s)
      [leg-red]               prototype exit=-15 failed=None error=None
      [zero-collected]        prototype never reported a collected count
      [deselected-unmeasured] no measured `deselected` count, the only witness
                              that its test filter removed anything
      [evidence-missing]      prototype recorded no JUnit XML

Four independent statements that no measurement exists, rather than one ambiguous
exit code. **If your harness writes a receipt, read its refusal before reading the
log** — a leg table carries no evidence of its own completeness, and a green one
can describe a tree you no longer have (see `working-tree-edits-stranded-on-squash-merge`
for the neighbouring failure).

### Why the advisory form of this rule did not hold

This skill has said "test for ZERO, not for under N" and "put the guard inside the
command that starts the leg" since 2026-09-17. On 2026-09-22 four sessions ran the
same suite concurrently anyway, and the session that lost a leg had not consulted
this skill before starting its own. **A rule that every session must remember,
and that costs nothing to skip, is not a rule.**

The enforceable form is `hooks/leg-guard`: a `PreToolUse` hook on `Bash` that
refuses to start a heavy leg while a peer interpreter is running one, with an
explicit `DR_LEG_FORCE=1` override so a session that genuinely must proceed does
so deliberately and visibly rather than by forgetting. It counts LINES with
parentage, collapses xdist workers onto their parent, excludes wrapper shells,
matches case-insensitively, tests for zero, and fails OPEN on any internal error —
every one of those directly from the measurements above.

It does **not** judge memory, and says so in the block message: a process count is
a CPU-and-contention rule and cannot see RAM. It prints free memory as context
only. And it never kills a peer's leg, because killing one destroys a measurement
its owner will read as a test failure.

## Notes

- **The `16384` in those one-liners is one machine's page size, not a
  constant.** `vm_stat`'s own first line prints it (`page size of 16384
  bytes`); where it is 4096 instead, a copied one-liner over-reports free
  memory four-fold — in the reassuring direction. Read it rather than trust it:
  `vm_stat | head -1`, or `pagesize`.
- **A subprocess `returncode` of `-9` next to a timeout is not evidence of
  memory pressure** — a timeout handler sends the same signal. Only a measured
  reading (kernel log, swap and RSS figures) is evidence of a kill for memory.
- **Deleting a peer's derived test artefacts to free memory is not a remedy** —
  a booted simulator or a live worktree may belong to a session mid-run.
- **A blanket `pkill -f pytest` to clear contention is not a remedy.** It
  destroys peers' measurements silently, and each owner then reads a corpse as a
  red leg. If a leg genuinely must be stopped, telling its session costs less than
  the wrong conclusion it will otherwise publish.
- The mirror of this rule lives in the queue rather than the machine: the local
  test slot belongs to whoever is next to merge, because certifying a tree that
  will be replaced before it lands spends the slot for nothing.

## See Also

- `worktree-does-not-isolate-shared-installed-artefacts` — the same shape one
  layer down: a worktree isolates the source tree and nothing else, so two
  sessions still share caches, installed packages and the machine itself.
- `verify-pytest-imports-worktree-not-primary-checkout` — before blaming the
  machine for a red leg, check the leg was importing the tree you think.
- `prove-test-failures-pre-existing-via-clean-worktree` — what to do once you
  have a real verdict and need to know whose diff owns it.
