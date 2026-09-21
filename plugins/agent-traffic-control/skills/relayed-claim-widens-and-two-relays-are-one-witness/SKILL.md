---
name: relayed-claim-widens-and-two-relays-are-one-witness
description: |
  A claim that was TRUE in the document it came from arrives WIDER in the artifact
  you are about to put in front of the user, because one verb changed on the way —
  "nothing refuses X" becoming "nothing counted X". Use when: (1) you are writing a
  page, brief, card or summary downstream of an audit, analysis or report rather than
  from the system itself; (2) the sentence you are about to write is a negative
  universal ("nothing does X", "there is no Y anywhere", "no gate checks Z"); (3) two
  sessions independently say the same thing and you are treating that as
  corroboration; (4) you are about to quote the user's own words that reached you
  through a peer message rather than from the place their words are recorded; (5) a
  fact-verifier has cleared the artifact and every number in it checks out. The check
  is a word-for-word diff of your headline claim against the upstream document's
  headline claim, with attention to the verb, plus a grep for the thing that would
  falsify the universal. NOT for a claim you read out of the system yourself, and NOT
  a reason to distrust a peer's ordering, timing or scale decisions, which are theirs.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Relayed Claim Widens, and Two Relays Are One Witness

## Problem

An audit of a pipeline asked whether anything refused a candidate for a particular
behaviour. Its headline finding:

> **Nothing refuses a candidate for doing X — and that is not an oversight.**

Its own table, in the row the audit called the most important one it contained,
said something narrower and more useful: an existing advisory measure **did**
count a form of X, was recorded on every record, and excluded the plain case by
construction, because it only fired when a second condition held at the same
time.

A page built from that audit, for the owner, opened:

> "Nothing refuses a candidate for doing X, **and until now nothing counted it
> either.**"

The first clause is the audit's. The second is not in the audit, is not true,
and reached the owner as the premise of a decision they were being asked to
make. They caught it themselves, on the page, and named the existing measure.

**Nobody lied and nothing upstream was wrong.** One verb changed — *refuses*
became *counted* — and the sentence went from true to false while keeping its
shape, its author and its apparent provenance.

## Why it survives every check you would think to run

**The upstream is correct, so provenance passes.** Anyone who asks "where did
this come from" finds a careful document that says the true thing. The defect is
in the transcription, and transcription is the step nobody re-reads.

**The widened version is the more useful sentence.** "Nothing measures this" is
what motivates the work; "nothing refuses this" is a narrower observation about
gates. The claim drifts toward the version that justifies the task, which is the
direction that generates no friction.

**A negative universal cannot be checked by reading the document it came from.**
"Nothing counts X" is a claim about the whole system, so the upstream document is
not the right instrument even when it is the right source. It is settled by a
grep, and the grep is not the check anyone runs on a summary.

**Same author is not a second reading.** The audit and the page here had the same
author. "I already checked this with the source" feels true because the same
session did both — which is exactly why the second artifact never got read
against the first.

**A number-binding fact-verifier clears it.** A verifier had already passed this
page: every figure bound to its source, every attribution checked. The false
sentence carries no number, so a check that walks the figures walks straight past
it. Add "check every negative universal in this artifact against the system, not
against the source document" to a verifier's brief, or it will keep passing them.

## Two relays are one witness

The same slip reached the owner twice. The decision request a peer had used to get
the original ruling said *"nothing records it"* — independently written, by
another session, and wrong in the same way, because both artifacts were written
from the audit's headline rather than from its table.

**Two sessions saying the same thing is not corroboration when both read the same
upstream.** It reads like two witnesses and it is one. Before treating agreement
between sessions as evidence:

- Ask each one **which document it read**, not whether it is confident.
- Count **sources**, not statements. Two artifacts derived from one summary are
  one observation with two authors.
- Expect the shared upstream to be a **summary**, because that is what gets
  reused. A summary is where a claim is most likely to have been widened already.

The cost is asymmetric: the user has no way to tell one source from two, so the
repeated claim arrives with more weight than either session could give it alone.

## Quoting the user's words from a peer message

A peer relayed the owner's correction as:

> Their words, verbatim: "<sentence>"

It was almost certainly accurate. It is still a copy, arriving through a session
that had made an attribution error of its own in the same message. A peer message
is not one of the places the user's words are recorded.

**Attribute the correction, not the words.** What went on the page was the
substance — "corrected, because you caught it" — with each factual half checked
against the code, and nothing in quotation marks. If the exact wording matters,
because it is going into a commit message, a code comment or a decision record,
read the place the user's words actually live and cite that.

The failure this avoids is the expensive one: a fabricated quotation handed back
to the person who supposedly said it.

## Verification

Before an artifact goes to the user, for each claim that came from a document
rather than from the system:

```bash
# 1. The verb. Diff your headline against the upstream's headline, word for word.
grep -i -n "refus\|reject\|block\|warn\|count\|measure\|record\|report" <upstream-doc>
#    refuses / warns / counts / records / measures are five different claims.
#    Upstream chose one on purpose; ask which, before you paraphrase it.

# 2. The universal. Grep for the thing that would falsify it, in the system.
grep -rn "<the-quantity>" <source-tree>     # "nothing counts X" is a claim about all of it

# 3. The shared upstream. If a peer agrees with you, ask what they read.
#    Same document on both sides = one witness, not two.
```

A cheap tell that costs nothing: **an artifact that contradicts a comment in its
own subject matter**. The code beside this page already carried a comment saying
the two measures must never be compared — which only makes sense if both exist.
The refutation was sitting in the same tree, one file away, in the author's own
earlier writing.

## Notes

- **The direction of drift is predictable.** Claims widen toward the version that
  justifies the work in hand. A summary rarely drifts toward a narrower, less
  interesting statement, so spend the check on sentences that make your task look
  more necessary.
- **Fixing it means showing the thing you wrongly said did not exist**, not just
  deleting the clause. The repair here put the existing measure on the same
  picture as the new one, and the contrast made the case better than the false
  sentence had: on one item the old measure read exactly zero where the new one
  read about eight per cent.
- **Sister skill**:
  [`peer-cited-platform-limit-may-be-a-conflation`](../peer-cited-platform-limit-may-be-a-conflation/SKILL.md)
  — the neighbouring case where the relayed sentence is a platform fact the peer
  invented rather than a claim that widened in transit, settled by asking for the
  source page.
- **Sister skill**:
  [`factcheck-subagent-needs-complete-sources`](../factcheck-subagent-needs-complete-sources/SKILL.md)
  — a verifier given complete originals is what catches the figure-shaped half of
  this; the negative-universal half has to be asked for explicitly.
