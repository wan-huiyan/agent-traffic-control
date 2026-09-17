---
name: session-context-runs-out-mid-brief-measure-first-hand-back-early
description: |
  A dispatched session can run out of its context budget before it finishes, and
  what survives is only what it MEASURED and sent — never the orientation it did.
  Hours of reading a call path leave nothing transferable; the two cheap readings
  the brief called unmeasured are the whole inheritance. Use when: (1) a brief
  names facts as unknown, unchecked or "not measured" and you are deciding what to
  do first; (2) you are partway through a task and can see the budget will not
  cover reading plus building plus gating; (3) a coordinator offers you another
  workstream and you suspect you cannot finish it; (4) you are tempted to start
  coding so the session has "something to show". Two rules: measure the named
  unknowns FIRST, because a measurement is the only artefact that outlives the
  session, and once the budget is visibly short DECLINE the next assignment
  BEFORE reading anything or claiming a worktree — a clean no is reassigned in
  minutes while a claimed-then-abandoned task costs the next session a worktree,
  a claim file and a hand-off nobody can use. NOT for a session that is merely
  slow or blocked on a dependency, and NOT a licence to decline work you can
  finish.
author: Claude Code
version: 1.0.0
date: 2026-09-17
disable-model-invocation: true
---

# A session that runs out mid-brief leaves its measurements, not its progress

## Problem

A coordinator hands a session a brief. The brief is honest about its own gaps: it
names two or three facts as **unmeasured** and says to settle them before relying
on them. It also describes the change to build, the tests to add, and the gates to
run.

The natural order is to understand the system first. So the session reads the code
path, maps the callers, finds the guards that will fire, works out the design — and
somewhere in there its context budget runs out.

Now measure what survives. **Orientation is worth nothing to anyone else.** The
understanding lived in a context window that is gone. No file changed, no branch
exists, and the next session cannot inherit "I read the reap path and it makes
sense". If the named unknowns were also left unmeasured, the successor starts from
exactly where the first session started, minus the hours.

The inversion is the finding: **the cheapest work in the brief is the only work
that is transferable.** A grep that answers "where is this value written?" and a
single read-only policy query that answers "can this identity already do that?"
take minutes each, fit in any budget, and go straight into the next brief as facts.
The expensive work — reading, designing, deciding — is exactly the part that cannot
be handed on.

The second half of the problem arrives right after the first. A session that has
spent its budget still looks idle and available, so more work gets offered to it.
Accepting one and stopping partway is worse than refusing: it leaves a claimed
worktree, a claim file, a half-written branch and a hand-off the next session has to
audit before it can trust any of it.

## Context / Trigger Conditions

Reach for this at three moments.

**When a brief names its own unknowns** — "not checked: whether X", "unmeasured:
whether Y". That wording is the signal. Those lines are the brief telling you which
of its facts are load-bearing and unverified, and they are almost always the cheap
ones.

**When you can see the budget will not cover the whole task.** The tell is
arithmetic, not a feeling: the task needs reading plus building plus tests plus
gates plus a wrap-up, and you are already deep into the first of five.

**When another workstream is offered and you doubt you can finish it.** Especially
after you have already stopped one task short — the same limit applies to the next
one, and nothing about a fresh brief resets it.

**Not for:** a session that is blocked on someone else (that is a dependency, say so
and wait), one that is merely slow, or one that can finish but would rather not. This
is about a hard limit you can see coming, not a preference.

## Solution

### 1. Order the brief by what survives you, not by what you need to know

Before the first substantive read, split the brief into two lists:

| List | Contains | Do it |
|---|---|---|
| **Transferable** | facts the brief calls unmeasured; readings of live state; anything that ends as a sentence someone else can act on | FIRST, whatever the logical order of the work |
| **Perishable** | understanding the call path, choosing a design, writing the code | after, knowing it may not survive |

This is not the order that makes the *work* easiest — orientation first is usually
better for building. It is the order that makes the *session* safe to lose.

A measurement qualifies as transferable only if you write it down somewhere outside
your own context: a message to the coordinator, a committed file, a comment on the
issue. A measurement you merely made is perishable too.

### 2. Make every measurement a sentence, not a state

Record the answer, its method and its date, so the next reader can re-check it
without redoing it:

```
(a) where the value is written: <path/function>, not <the place the brief guessed>.
    Read off the code that writes it, at <commit>.
(b) whether the identity may already do it: yes — <role> covers <permission>.
    Read-only, <timestamp>. No grant needed.
```

Both lines are useful to a successor who has none of your context. "I looked into
it and it seems fine" is not.

### 3. Once the budget is short, decline BEFORE reading anything

The cost of a refusal is not symmetric, and the asymmetry is the whole rule:

| | Cost if you decline | Cost if you accept and stop partway |
|---|---|---|
| Coordinator | one reassignment, minutes | the same reassignment, later |
| Next session | nothing | audit a claimed worktree, a claim file, a partial branch |
| Repo | nothing | a stale branch and a claim nobody dares delete |

So the refusal has to come **before** the first read and before any claim. A no
after you have created a worktree is a cleanup task you are handing someone.

Say three things and nothing else: that you cannot take it, the reason in one clause,
and that you have touched nothing. Naming the reason matters — "I am out of budget"
is reassignable, silence looks like a session that is stuck.

### 4. Say it once, then hold the line

The same limit applies to every later offer in that session. Re-deciding each time
invites the failure this skill exists to prevent, because each new brief looks small
in isolation.

## Verification

Before you start building anything:

- Every fact the brief called unmeasured either has an answer written outside your
  context, or you can name why it does not.
- You can point at where those answers live — a message, a file, an issue comment —
  not at your own reasoning.

When you stop short:

- The hand-off states what is measured, what is not, and what you did NOT do, as
  three separate lists.
- Your worktree is either clean and removed, or you have said exactly what is in it.
- `git status --porcelain` in it is empty before you remove it.

When you decline:

- No worktree, no fetch, no claim file — verifiable, not asserted.
- The refusal names a reason the coordinator can route on.

## Example (real)

A session was handed a server fix whose brief named two facts as unmeasured: **where
a started job's identifier is recorded**, and **whether the running service's identity
was already allowed to read a cloud API** it would need. The brief also carried the
design, the tests and the gate rules.

The session read the code path first, as anyone would. Its budget ran out before a
line was written. It then spent what was left on the two named unknowns:

- one grep showed the identifier was **not** in the record the brief assumed, but in
  a different object written by the start path;
- one read-only policy query showed the service already held a role covering the
  reads, so **no permission grant was needed** — the brief had been prepared to ask
  for one.

Both went into the next session's brief. The worktree was removed unchanged, because
nothing in it was worth keeping. The successor started with two settled facts and a
correction to an assumption, which is strictly more than it would have had, and the
hours of reading were simply lost.

Four further workstreams were offered to that session over the following day. Each
was declined **before** reading the issue or creating a worktree, with the reason
given. Each was reassigned within minutes and left nothing to clean up. The one
earlier task that had been started and stopped left a worktree and a branch that
someone had to check and remove.

## Notes

- **The budget is not the only reason this shape appears.** A session can be stopped
  by a usage limit, a crash, a machine reboot or a user closing the terminal. The
  ordering rule is the same under all of them: measurements survive, understanding
  does not.
- **"Something to show" is the trap.** Starting the code makes a session feel
  productive and produces the least transferable artefact available — a partial diff
  whose author is gone. A message containing two verified facts is worth more.
- **A brief's own guesses are worth checking cheaply.** In the example the brief was
  wrong about where the identifier lived. That correction cost one grep and would
  have cost the successor an hour of confusion.
- **Do not let a live reading go undated.** A permission or a piece of state read
  today may not hold next week; a reading with a timestamp is a fact, one without is
  a rumour.
- **Declining is not the same as going quiet.** A session that stops answering looks
  broken and gets chased. State the limit plainly and stay reachable.

## References

- [`inherited-scope-doc-names-may-not-exist`](../inherited-scope-doc-names-may-not-exist/SKILL.md)
  — the other half of "a brief is a claim": verify the names a predecessor's scope
  doc cites before a long dispatch, rather than after
- [`workflow-agent-unreachable-mid-flight-check-output-not-brief`](../workflow-agent-unreachable-mid-flight-check-output-not-brief/SKILL.md)
  — a brief frozen at dispatch, and why the correction has to be caught at output
  review; here the brief is fine and the session is the thing that runs out
- [`parallel-impl-agent-dies-mid-stream-verify-working-tree`](../parallel-impl-agent-dies-mid-stream-verify-working-tree/SKILL.md)
  — the involuntary version: an agent that died mid-stream, where the working tree
  may hold the only copy of its product
- [`agent-refusal-with-evidence-beats-literal-compliance`](../agent-refusal-with-evidence-beats-literal-compliance/SKILL.md)
  — refusing because the instruction is wrong, which is a different reason from
  refusing because you cannot finish; both want the reason stated, not silence
- [`fan-out-cost-control`](../fan-out-cost-control/SKILL.md)
  — budget spent sideways across a fan-out rather than downwards in one session
