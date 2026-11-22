---
name: peer-window-grant-copy-the-parser-and-stay-quiet-while-live
description: |
  You grant another agent an exclusive window on a shared machine by writing a hold file plus a
  text grant into a shared mailbox, and its controller parses that text. Use when a grant was
  refused before entry, a live window stopped after a note you posted, or peers ran "light"
  commands inside a quiet window.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Granting a Peer a Window: Copy Its Parser, Then Stay Quiet

## Problem

A coordinator lends a shared host (a laptop, a simulator pool, a build box) to a peer agent for
a fixed window. The grant is two things: a **hold file** that tells everyone else to stay off,
and a **grant block** appended to a shared text mailbox. The peer's controller reads the block,
checks every field against its own pinned rules, and refuses on any mismatch. That is correct
behaviour for a guard, and it makes the grant text an API.

Four ways the window is lost, all seen in one afternoon:

1. **A label paraphrased.** The controller reads `Initial acknowledgement before (absolute,
   opened_at + 900 s; applies to first receipt only, not to later job starts)`. The grant said
   `... applies to first receipt only)`. Refused before entry; nothing ran.
2. **A label decorated.** The controller reads `Ends at (absolute)`. The grant said `Ends at
   (absolute, opened_at + 300 s)` because an earlier template had it. Refused before entry.
3. **A note posted mid-window.** While a window was live, the coordinator posted a routine note
   that named an *earlier, archived* hold file, whose filename contained the word `closed`. The
   peer's guard scans every note that mentions the live grant for closure words, read the note as
   a withdrawal, and stopped a 30-minute build after entry, with exit 75. Its cleanup steps were
   refused too, so a second cleanup-only window was needed.
4. **Peers inside the quiet window.** Other sessions were told "no tests while the hold exists".
   They ran a "light" `python3 -` here, a tracker checker there, a one-line edit through an
   interpreter. Each was harmless alone, and each was a breach of a window whose witness requires
   the host to read idle.

None of these is the peer being fussy. A guard that accepted a near-miss label would also accept
a forged one.

## Context / Trigger Conditions

- The grant is free text that a program on the other side parses, rather than a typed API call.
- The peer's packet ships its own controller or verifier, and its field labels live in that code.
- More than one window per day goes through the same mailbox, so old grants and archived hold
  names sit beside the live one.
- Other sessions share the host and have been told to stay off "while the hold exists".

## Solution

### Before issuing

1. **Read the labels out of the parser, not out of your last grant.**
   `grep -n "Ends at\|Start before\|Initial acknowledgement" <controller>.py <verifier>.py`.
   Copy each label character for character into the issuer. If the packet ships a
   `PRIMARY-GRANT-FIELDS.txt` (or similar), paste its lines verbatim; never retype them.
2. **Recompute every pinned hash at issuance** and refuse to issue on any mismatch. Print the
   pins into the grant so the peer can compare.
3. **Archive the previous hold and post the note about it BEFORE writing the next grant.** A
   note about an archived window that lands after the new grant reads as being about the new one.
4. **Gate on the window's own floors** (memory free for the full quiet period, disk, power, no
   build or simulator processes, no other hold), and retry on a timer rather than lowering a floor.

### While the window is live

5. **Write nothing to the mailbox except the release acknowledgement after the peer's DONE.**
   Not a status note, not a queue update, not a reply to an unrelated message. Hold them until the
   window closes.
6. **Tell peers "nothing", with no exemptions.** "No tests" invites "a checker isn't a test". The
   rule that holds is: while the hold file exists, run no interpreter, no node, no build and no
   test on this host. git reads and file reads only.

### After DONE

7. Read the live hold back, compare its hash to the one you issued, check the peer's process
   groups are gone, then rename the hold to an archived name and acknowledge. Only then issue the
   next window.

## Verification

- Every grant field label appears verbatim in the parser: `grep -F "<label>" <controller>.py`.
- No mailbox write timestamp falls between a grant's `opened_at` and the peer's DONE, other
  than the grant itself.
- The archived-hold note for window N precedes grant N+1 in the mailbox.

## Notes

- A refusal before entry costs one round trip. A stop after entry costs the work done so far,
  plus a cleanup window, plus a fresh packet from the peer.
- If the peer offers a fixed parser (for example, one that ignores archived-hold filename tokens
  in its closure scan), take it. Keep the quiet rule anyway; the next guard may scan for
  something else.

## See also

- `shared-mutable-index-rmw-race-use-marker-blob-per-item`: shared files that several agents
  write to.
- `running-job-queue-ignores-in-place-edits`: the coordinator's other shared-host instrument.
