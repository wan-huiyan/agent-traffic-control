---
name: peer-cited-platform-limit-may-be-a-conflation
description: |
  A coordinator or peer session hands you a constraint stated as a platform fact
  ("the provider's ceiling forbids N workers, so that run is not a machine you
  could buy"), and it is their own conflation of two quantities that happen to
  share a number in today's configuration. Use when: (1) a peer message tells you
  an option is impossible, unsupported or not purchasable, and names no source;
  (2) you are about to drop a measurement arm, narrow a brief or tell the user an
  option does not exist, on the strength of that sentence; (3) the constraint
  arrives inside a message whose other instructions are correct and specific;
  (4) you are the one about to assert a platform limit to a peer. The reply that
  settles it in one round is your own wording PLUS an offer to adopt theirs if the
  source exists: "unless you have a page I have not read, in which case send it
  and I will use your wording". It keeps the exchange about evidence rather than
  authority, and it puts the check on whoever asserted the limit. Correctness
  elsewhere in the message is not evidence about this clause, and a peer who is
  quoting the limit upstream to the user will keep quoting it until it is
  corrected at the source. NOT for a limit the peer cites with a link or a command
  output, and NOT a reason to ignore a coordinator's timing or ordering decisions,
  which are theirs to make. Once you have refuted the platform's limit, check your
  OWN code for the same limit one layer down: a silent clamp there makes the run
  measure the control twice.
version: 1.1.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Peer's Cited Platform Limit May Be Their Own Conflation

## Problem

A coordinating session sends a brief that is mostly right — the ordering, the
budget, the reporting format, the thing to measure — and one sentence in it
states a platform limit that does not exist:

> "12 workers is above the provider's 8-CPU ceiling for a job task, so that arm
> is a cost-per-worker measurement, not a machine the user could actually buy.
> Do not let it read as an option."

The instruction that follows is reasonable, the tone is certain, and the rest of
the message is verifiable and correct. Accepting it costs an arm of the
measurement and tells the user an option does not exist.

**It was a conflation of two different quantities: worker PROCESSES and CPUs.**
The provider's published ceiling is on vCPU and memory per task. Nothing in it
constrains how many worker processes the task starts. Twelve workers on an
eight-CPU task is legal and deployable; it means twelve processes sharing eight
CPUs, each slower, each still paying its own memory.

## Why it survives being written down

**The two quantities share a number in the current configuration.** Production
ran four workers on four CPUs, so every recent observation is consistent with
either reading, and no local check disagrees. A conflation between two
quantities that coincide today is invisible until someone proposes a
configuration where they differ — which is exactly the configuration a
measurement arm exists to test.

**A brief's overall quality is not evidence about one clause.** The message that
carried this also carried a correct order of work, a correct rate per
task-second, a correct stop line and a correctly identified control run. There
is no signal in "this session is usually right" for the sentence in front of you.

**The limit reaches the user through the peer, not through you.** A coordinator
relaying to the person paying will quote it. Quietly running the arm your way
fixes your arm and leaves the false constraint in the record, where it will
retire a future option.

## The reply that settles it

Give your wording, say what you will do, and offer to adopt theirs if the source
exists:

> "12 workers on 8 vCPU is a machine the user CAN buy. The ceiling is on CPUs and
> memory, not on how many worker processes we start; it means 12 processes
> sharing 8 CPUs. I will write it as 'allowed, and measured to see whether
> oversubscribing helps or hurts' — unless you have a provider limit I have not
> read, in which case send me the page and I will use your wording."

Three things make that work:

- **It is falsifiable in one step by whoever asserted it.** They either produce
  the page or they do not.
- **It concedes the framing, not the fact.** You are offering to use their
  sentence if it is true, so there is nothing to defend.
- **It names what you will write instead**, so agreement ends the exchange rather
  than opening a second round about wording.

In the observed case the coordinator checked, found no such page, replied *"the
claim was mine and it was false"*, and corrected it in the design document where
it had been written down — having first grepped the design, the rulings folder
and its own log to confirm that was the only copy. Two sessions, one round, and
the false constraint did not reach the user.

## When you are the one asserting the limit

- **Name the source in the same sentence as the limit**, or say plainly that you
  have not read one. "The provider's job page says 8 vCPU / 32 GiB per task" is
  checkable; "the ceiling forbids that" is not.
- **Say which quantity the limit is on.** Most of these mistakes are a limit on
  quantity A being applied to quantity B: CPUs against processes, per-task
  against per-project, concurrent against total, requests against instances.
- **Grep for other copies when you retract one.** A constraint that was written
  into a design note, a ruling or a handoff is still being read after the
  message that carried it has scrolled away. Correcting the message and leaving
  the note is the half-fix that keeps the claim alive.

## Verification

Before dropping an option on a cited limit, run whichever of these applies:

```bash
# the provider's own words, not a summary of them
gh api ... | jq ...            # for an API-visible limit
curl -s <docs-url> | grep -i "maximum\|limit\|per task"

# or the cheapest empirical check: ask the platform to accept the configuration
<deploy/describe command> --dry-run
```

**A configuration the platform accepts is stronger evidence than any page**, and
it costs one submission. Say which of the two you have: in the observed case the
correction rested on the published per-task limits, because the twelve-worker arm
was still queued behind other work when the exchange happened — the job spec was
written and validated, not yet run. "The spec validates" and "the run completed"
are different claims; do not let the stronger one stand in for the weaker. **That
run has since completed and the platform did accept it**, so the empirical check
is now in hand — and it brought a second finding the exchange had missed, in the
amendment below.

## What happened next: the limit was real one layer down (amendment, v1.1.0)

The run completed. The platform accepted twelve worker processes on an eight-CPU
task and never complained, so the peer's claim about the provider was false, as
stated above.

**The run did not use twelve workers.** The codebase clamped it:

```python
MAX_WORKERS = 8
def workers_requested(n): return min(n, MAX_WORKERS)   # clamps, does not refuse
```

`min()` is the whole defect. Asking for twelve returned eight with no warning, no
error and nothing in the log saying a request had been reduced. So the arm built
to measure oversubscription ran the control configuration a second time, and the
write-up above — correct about the platform — was incomplete about the thing that
actually decided the run.

**The guard did not catch it because it checked the request.** The unit asserted
the environment variable said `12` and refused to start otherwise. The
environment variable was `12`. What it needed to assert was how many processes
forked, which the run recorded a few lines further down and nobody compared.

**So: assert the EFFECT, never the REQUEST.** Anything that can silently reduce
what you asked for — a clamp, a quota, a scheduler, a pool that reuses workers, a
retry that halves a batch — makes "I asked for N" worthless as evidence. Record
what actually happened (processes started, rows written, bytes fetched) and fail
the unit when it differs from N.

**And when you refute one layer's limit, sweep the others in the same breath.**
Platform quota, runtime default, your own constant, the library's internal cap.
The exchange above ended one round early: "the platform allows twelve" was true
and felt like the whole answer.

**Two things worth keeping about the accident.**

- **An accidental replicate is evidence, not waste.** Two runs in the same
  configuration measured run-to-run variation at about 8%, which is what let the
  round's real result stand clear of noise. Reporting it as a failed arm would
  have thrown away the only variance estimate the round produced. Say what it
  measured, not what it was meant to measure.
- **A constant like that is a production setting, so measuring it is somebody
  else's decision.** Raising the clamp in a research build changes how the
  production path behaves; the session that wants the number does not get to
  make that call. Report the clamp, name who owns it, and leave it alone.

## Notes

- **The failure is not insubordination in either direction.** The peer's job is
  ordering and scale; the fact is whatever the platform says. Treating a
  coordinator's claim as an instruction confuses the two.
- **Two quantities sharing a number is the general pattern.** It is worth a
  second look whenever a constraint is stated as a bare number and the current
  configuration makes two different meanings agree.
- **Sister skill**: [`inherited-scope-doc-names-may-not-exist`](../inherited-scope-doc-names-may-not-exist/SKILL.md)
  — the same shape where the inherited artefact is a scope document naming a
  dataset or table that does not exist, settled by a cheap probe rather than by
  argument.
