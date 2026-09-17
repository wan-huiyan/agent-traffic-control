---
name: poll-loop-treats-an-unreadable-status-as-finished
description: |
  You are watching a long-running job you dispatched — a hosted batch
  execution, a remote build, a queued run — by asking its API for status on a
  loop, and the loop decides "finished" by pulling one field out of the reply
  and testing that the field is not empty. An error line, a fallback token or a
  truncated reply is also not empty, and `cut` without `-s` hands a
  delimiter-free line back whole whatever field you asked for — so the test
  passes on a reply that carries no status at all. Use when a
  watch loop reports done and you are about to act on it — report the work
  complete, cancel a sibling, delete the inputs, start the next stage — when
  the machine slept or the session resumed mid-watch, or when a status reading
  disagrees with how long the work should have taken. Parse a completion fact,
  keep UNKNOWN as its own state, and re-read the source before an
  irreversible act.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Poll Loop Treats an Unreadable Status as Finished

## Problem

A watch loop asks a remote system "is it done yet?" and has to turn the answer
into a boolean. The usual shape projects a few fields out of the reply, splits
them on a delimiter, takes one position, and treats a non-empty value as the
completion signal.

**Three things make that decision unsound, and they compound:**

1. **"Not empty" is the weakest predicate available.** An error line, a quota
   message, an expired-credential notice, a proxy's HTML page and a
   human-readable "unreadable" are all non-empty strings. None of them is a
   status, and every one of them passes.
2. **A field POSITION is not a field NAME, and the splitters disagree about a
   malformed line.** A projection that returns five delimited values gives you
   five only while the reply is well formed. A reply with no delimiter at all
   collapses to ONE field, and what your extractor then returns depends
   entirely on which extractor you used: **`cut -d, -f5` hands back the WHOLE
   LINE** whatever field you asked for, unless `-s` is given, while
   `awk -F, '{print $5}'` and ordinary shell field splitting return empty.
   Verified, not assumed — the three commands are in the References below. Only
   the first turns an error string into "the completion time".
3. **The gap that produces the malformed reply is invisible from inside the
   loop.** A laptop that suspended, a token that expired mid-watch, a network
   blip, a session that resumed hours later: the loop wakes and its first
   reading is the broken one.

**The two failure directions are not symmetric, and the quiet one is the
expensive one.** A false BUSY is loud and cheap — the loop keeps spinning and
somebody notices. A false FINISHED is silent and is the reading you ACT on: you
report the work done, you cancel the sibling that was "no longer needed", you
delete the inputs, you launch the next stage against half-written output, or
you release a coordinator that was holding a queue for you. By the time the job
really finishes, the acts are done.

**Measured, 2026-09-17.** A session watched hosted batch executions with a
background poll whose status call projected five comma-delimited fields and
read field 5, the completion time, as the done signal. The laptop slept
overnight, so the watch did not fire while the work ran. On waking, the status
query did not return a record: what reached the field test was a single token
with no comma in it, so the split produced one field, the field was non-empty,
and the check — nominally "the completion time is populated", actually "the
reply is not empty" — passed. The monitor printed a terminal state.

**The part that makes this worth a skill: the verdict was CORRECT, and that is
luck rather than evidence.** Read directly, both executions had genuinely
finished hours earlier, overnight. So the broken check and a working one agreed
on the only occasion anyone looked, and **the same reply would have passed
identically over a job still running** — the test cannot tell those apart,
which is precisely what it was there to do. A check that returns the right
answer for the wrong reason is the hardest kind to notice, because nothing
downstream ever disagrees with it. What found it was reading the executions
themselves before reporting anything, not the monitor's own output.

## Context / Trigger Conditions

- A watch loop reports a terminal state and you are about to act on it —
  report completion, cancel a peer job, delete inputs or intermediate data,
  start a dependent stage, or tell a coordinator it can move.
- The machine slept, the session was resumed, a credential was refreshed, or
  the poll interval shows a gap far longer than it was set to.
- A job "finished" much sooner than its own work could possibly take, or
  several independently watched items reached a terminal state in the same
  tick.
- Your done test is a non-emptiness check, a truthiness check, a
  `$(... | cut -d, -f5)`, a `[[ -n "$field" ]]`, or an `awk '{print $3}'` over a
  projection you chose by position.
- The status command exits 0 while printing something that is clearly not a
  status.

## Solution

### Step 1 — Test for a completion FACT, never for a non-empty field

Require a value the running state cannot produce:

```bash
# a terminal state from a closed set — not "the state field is populated"
case "$state" in
  SUCCEEDED|FAILED|CANCELLED) done=1 ;;
  RUNNING|PENDING|QUEUED)     done=0 ;;
  *)                          done=unknown ;;   # everything else lands here
esac
```

If the signal is a timestamp, **parse it**. A string that does not parse as a
date is not a completion time, however non-empty it is.

### Step 2 — Ask by name, and prefer one field per call

Positional projections renumber silently when a field is empty, when the API
adds a column, or when the reply is not a record at all. Where the client can
return a single named value, or JSON you address by key, take that: a missing
key is an absence you can detect, where a missing position is a shift you
cannot.

### Step 3 — Keep UNKNOWN as a third state

An unparseable reply is neither done nor busy. Collapsing it into "busy" hangs
the loop forever; collapsing it into "done" is this skill. Count consecutive
unknowns, print the raw reply when one appears, and escalate after a few rather
than deciding.

### Step 4 — Separate the CLIENT's exit status from the JOB's status

They are different questions and neither answers the other. A client can exit 0
having printed an error; a non-zero exit says your query failed, not that the
work did. Check the exit status first, and on a non-zero exit record UNKNOWN
without looking at stdout at all.

The mirror of this step — a waiter that trusts an exit status which FOLDS
several results into one — is
`gh-pr-checks-exit-code-folds-a-by-design-red-wait-on-the-row`. Between them:
never decide from the exit status alone, and never decide from the payload
without checking the exit status.

### Step 5 — After any gap, discard the first reading

A suspend, a resume, a re-auth or a poll interval that plainly overran means the
loop's next reading is the one most likely to be malformed. Throw it away, read
again, and only then compare.

### Step 6 — Re-read the source before an irreversible act

A monitor's verdict is a COPY of a state that lives elsewhere. Before reporting
completion, deleting inputs, cancelling a sibling or starting a dependent stage,
query each job directly, one at a time, and read the state out yourself. That
one call is the cheapest step here and it is what keeps a bad parse from
becoming a bad act.

### Step 7 — Prefer a completion marker the work itself writes

An output object, a results file, a row with the run's id in it — written LAST,
by the job, on the path it actually produces. An error string cannot forge one,
and unlike a state field it distinguishes "finished" from "died". Pair it with
the job's own terminal state: the marker proves the output exists, the state
proves how the run ended.

## Verification

**Feed the parser its failure replies, not its happy one.** Extract the
done-decision into a function that takes the raw reply text, then assert on:

- an error line with no delimiter in it → UNKNOWN, never done
- an empty reply → UNKNOWN, never done
- a well-formed reply with an EMPTY middle field → still the right field read
- a truncated line → UNKNOWN
- a genuine running reply → busy
- a genuine terminal reply → done

A monitor exercised only against a running job and a finished job has never run
the branch that actually fires. If the loop is already written and running, do
not edit it in place — a running script edited under itself is its own failure
mode; verify the parser in a copy and fix the loop on its next launch.

## Example

**The watch that was right by accident.** Hosted executions, watched by a
background poll that ran one status call per job, projected five comma-separated
fields and took the fifth as the completion time. The laptop slept overnight, so
the poll did not fire while the work ran. On wake the status query returned no
record and a single comma-free token reached the field test, which passed it as
a completion time. The monitor printed a terminal state.

Both executions had in fact finished overnight, so the verdict matched reality
— **and that is the trap, not the reprieve.** Nothing about the output looked
wrong, nothing downstream disagreed, and the same token would have produced the
same verdict over a job with hours left. The check was found by Step 6 and
nothing else: before reporting completion, the session read each execution
directly rather than trusting the monitor's line. What would otherwise have
followed the verdict — telling the waiting session the work was done, and
deleting the inputs as the next step in the brief — is where the cost of this
bug actually lands, and none of it is recoverable by noticing later.

**The shape to copy into the loop instead:** read the state field by name; map
it through a closed set of terminal values; treat anything else as UNKNOWN and
print the raw reply; and re-read each job directly before the act.

## Notes

- **The predicate drifts from the sentence that describes it.** "The completion
  time is populated" and "the reply is not empty" are the same line of code once
  the split degrades, and only one of them is what the comment says. When a
  check's meaning depends on the shape of what it is parsing, state the shape as
  an assertion rather than assuming it.
- **Absence and garbage are different unknowns.** An empty reply usually means
  the query failed; a non-empty unparseable one usually means something
  answered that is not the service you wanted. Both are UNKNOWN, but the second
  is the one that slips past a non-emptiness test.
- **A monitor that watches several jobs should report them separately.** One
  aggregated "all done" hides the simultaneity that would have given the parse
  away.
- **Do not re-derive a terminal verdict from elapsed time either.** "It has
  been long enough" is the same guess in a different costume; a job that hangs
  looks exactly like one that is still working.
- **A correctly parsed terminal state is still not proof the work happened.**
  Everything above gets you an honest reading of what the platform says; what
  the platform says can itself be hollow —
  `job-reports-success-while-its-worker-was-oom-killed` is a job listed as
  SUCCEEDED whose forked worker was killed and whose output is empty. That is
  the case for Step 7: a marker the work writes last is the only signal that
  survives both a bad parse and an honest-but-hollow success.
- Sister skills: `waiter-pgrep-matches-its-own-command-line` asks this question
  of a LOCAL process list, where absence cannot tell finished from died;
  `subagent-external-wait-orchestrator-takeover` is the layer above — whether
  the polling should be happening in this session at all;
  `scheduled-fallback-check-cites-stale-task-id` covers the identifier a delayed
  check names going stale between scheduling and firing; `fan-out-cost-control`
  covers what a job loses when it is stopped before it writes anything out.

## References

- A status projection is a contract with the client's output format, not with
  the service's API — read the client's own documentation for what it prints
  when the call itself fails.
- Shell field splitting, measured rather than recalled — a line containing no
  delimiter is ONE field, and the splitters disagree about what that means:

  ```
  printf 'ERROR: could not read the execution\n' | cut -d, -f5     # the WHOLE line
  printf 'ERROR: could not read the execution\n' | cut -d, -f5 -s  # nothing
  printf 'ERROR: could not read the execution\n' | awk -F, '{print $5}'  # empty
  ```

  `cut(1)` passes a line with no delimiter through unchanged whatever field you
  asked for, unless `-s` is given — so the error text becomes "field 5" and a
  non-emptiness test passes on it. `awk` returns empty for the same input and
  would have failed safe. That single flag is the mechanism behind the
  measurement above; it is not a reason to trust `awk` either, because an empty
  field read as "not finished" only fails in the quieter direction.
