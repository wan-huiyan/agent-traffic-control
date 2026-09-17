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
  which are theirs to make.
version: 1.0.0
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
are different claims; do not let the stronger one stand in for the weaker.

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
