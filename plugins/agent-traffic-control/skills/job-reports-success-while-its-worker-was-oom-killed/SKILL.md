---
name: job-reports-success-while-its-worker-was-oom-killed
description: |
  A batch or cloud job lists as SUCCEEDED while the work inside it produced
  nothing, because the kernel's out-of-memory killer took a forked WORKER and the
  parent caught the failure, wrote its record and exited 0. Use when: (1) a run's
  own output says a worker "died"/"was terminated abruptly" but the execution
  listing says succeeded, (2) you are about to report "the job failed" or "the run
  died" to a coordinator who will quote you upstream, (3) a peer checks the
  listing, sees success and tells you your sentence is wrong, (4) a harness has
  classified the death as transient or retryable, (5) you are sizing a machine
  from a run that died and need its true peak. The platform logs a memory message
  only for a CONTAINER kill, so silence about memory is expected for a child kill
  and is NOT evidence against it. Record the cgroup counters (`memory.oom_control`
  oom_kill, `memory.failcnt`) at the start and end of every run so a kill is
  COUNTED rather than inferred, and read the kernel's own peak, because a
  half-second sampler misses a spike that arrives in five seconds. Name the layer
  that failed: "a worker was killed and the search returned nothing" and "the job
  failed" are different sentences and only one of them is true. NOT for a genuine
  application failure with a recorded exit status, and NOT for a container kill,
  where the platform does say so.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Job Reports SUCCESS While Its Worker Was OOM-Killed

## Problem

A long research run fans routing work out to forked worker processes. One worker
is killed by the kernel's out-of-memory killer. The parent process catches the
resulting "a process in the process pool was terminated abruptly", records the
failure in its own JSON, writes its log and returns 0 — which is correct
behaviour for a harness that reports rather than crashes.

The result is three artefacts that disagree in a way nobody notices:

| artefact | what it says |
|---|---|
| the execution listing | `succeededCount 1`, condition `Completed True` |
| the run's own record | the work raised "a worker died while routing item 10 of 100", zero results written |
| the platform's logs | nothing about memory at all |

So "the run died" is wrong, "the run succeeded" is wrong, and the useful sentence
is longer than either.

## Why the platform says nothing about memory

A managed runtime emits its memory-limit message when it kills the CONTAINER. A
child process killed inside a container that stays alive is invisible to it: the
task did not exceed anything the platform enforces, and from outside, nothing
failed. **Absence of a memory message is therefore the expected state for a child
kill, not evidence that memory was not the cause** — which is exactly the
inference a reviewer makes when asked "was it really memory?".

## Make it counted, not inferred

Read the kernel's own counters into the run's record, at the start and again at
the end. On cgroup v1:

```bash
CG=/sys/fs/cgroup/memory
cat $CG/memory.oom_control        # oom_kill_disable 0 / under_oom 0 / oom_kill N
cat $CG/memory.failcnt            # charges refused at the limit
cat $CG/memory.max_usage_in_bytes # the kernel's own peak, never reset
cat $CG/memory.limit_in_bytes
```

On cgroup v2 the equivalents are `memory.events` (`oom_kill`), `memory.peak` and
`memory.max`. Read both layouts: a runtime advertising a modern generation can
still present v1 inside the container, which is what the observed run did.

Two readings did the work in the observed case:

- **`oom_kill` was 0 at the moment the workers forked and 1 at the end.** One line,
  and the finding stopped being a guess. A coordinator quoting it upstream could
  say "the kernel counted the kill" instead of "we think it ran out of memory".
- **`memory.max_usage_in_bytes` was 7.41 GiB against an 8 GiB limit**, while a
  sampler polling `memory.usage_in_bytes` every half second had caught less: usage
  went from about 3 GB just after the fork to about 8 GB within roughly five
  seconds of work starting. **Sample for the shape, but report the kernel's peak.**

## Per-process peaks cannot be added up

`getrusage(RUSAGE_CHILDREN).ru_maxrss` is the peak of the LARGEST single
descendant, not a sum — and for a forked child it counts pages the child still
SHARES with the parent. A worker reading 2.70 GB beside a 2.57 GB parent has not
used 2.70 GB extra; it has copied about 0.13 GB of its own.

To get what a fan-out really costs the machine:

- read the container's total (cgroup usage or peak) and subtract the parent, or
- compare container usage just after the fork with usage at the peak.

Reporting the per-child figure as a sum overstates the workers and understates
the parent, and it points a fix at the wrong half. Say which number you read.

## Why the workers cost so much: it is copied, not built

In the observed run each worker grew by roughly 1.2 GB within seconds of
starting, on top of a 2.6 GB parent, and the cause is worth knowing because it
decides the fix:

- the shared structure was a graph held as plain interpreter objects — a
  dictionary of about 1.7 million node positions plus nested edge dictionaries;
- forked children share those pages until they touch them, and a
  reference-counting runtime WRITES to an object's header when it merely reads it;
- so traversing the structure turns shared pages private, and the container pays
  for them once per worker;
- nothing in the worker's path built an index of its own — which the readings
  support: each worker's peak sat level with the parent's rather than far above it.

**Fixes that follow:** fewer workers, more memory, or holding the shared
structure in a form that survives forking (arrays rather than per-element
objects); a pre-fork `gc.freeze()` is the cheap partial. **A fix that shares a
rebuilt per-worker index is aimed at nothing**, because no such index exists.

## The sentence to send a coordinator

Say which layer failed, what the run produced, and where each reading came from:

> "The search returned no route: a routing worker was killed for memory at the
> first item, and the job itself finished and reported the failure. Container peak
> 7.41 GiB of 8 GiB, kernel `oom_kill` 1 (0 at the fork), `failcnt` 0, read from
> the run's own record and the execution listing."

- **"The job failed" invites a peer to check the listing and correct you**, which
  is what happened: the listing said succeeded, and the peer was right to ask.
- **"The job succeeded" hides a search that produced nothing**, and if the run was
  a machine-sizing measurement, that is the whole result.
- **A harness may have filed the death as `transient`.** A memory kill is not
  retryable at the same size, so a retry classifier reading "worker died" as
  transient will loop a run that cannot pass. Say so when you report it.

## Notes

- **Deaths that predate the counters are weaker evidence.** Two earlier runs in
  the same measurement died the same way before the counters were being read;
  they can only be reported as "most likely memory". Add the counters to the
  harness the first time you see this, not the second.
- **A run that survives is not proof of headroom.** The same wish at the same size
  finished at 7.11 GiB of 8 GiB, and the pair differed only in which items each
  happened to work on. Report the margin, not the pass.
- **Prevention, where the worker is a local test leg**: [`leg-guard`](../../hooks/leg-guard/)
  refuses to start one while a peer's is running. It does **not** judge memory — a
  process count cannot see RAM — so it prevents the contention case, not this one.
  Worth installing anyway: on 2026-09-22 a leg died with `exit=-15` while memory read
  81% free, and the artefact was indistinguishable from an OOM kill. The guard that
  would have prevented it is a contention guard, and the reading that would have
  classified it is the receipt's refusal, not the exit code.
- **Sister skill**: [`parallel-gate-legs-killed-for-memory-count-cannot-see-ram`](../parallel-gate-legs-killed-for-memory-count-cannot-see-ram/SKILL.md)
  — the same killer one layer down, where a local test leg is stopped for memory
  on a shared machine and a process-count guard cannot see RAM.
