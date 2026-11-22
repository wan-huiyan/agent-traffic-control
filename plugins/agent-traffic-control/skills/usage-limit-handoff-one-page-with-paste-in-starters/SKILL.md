---
name: usage-limit-handoff-one-page-with-paste-in-starters
description: |
  Your account's usage limit is near and another account (or a fresh session) must pick up
  several live workstreams. Use when a limit warning appears, when the user says usage is low,
  or when you inherit work from a session that ran out.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Running Out of Usage: Hand Over on One Page, With a Paste-In Line Per Workstream

## Problem

A coordinator holding many workstreams (a pull request queue, background test runners, peer
sessions, grants on a shared machine) hits its account's usage limit. A different account picks
up. The new account has none of the old conversation, and the user is the only bridge between
them. Handovers went wrong the same few ways, repeatedly:

1. **The handover arrived too late.** Written at the limit, it was cut off mid-list, and the last
   workstreams had no entry at all.
2. **The user became the router.** Each workstream needed the user to explain it again to a new
   session, which is exactly the load the handover was meant to remove.
3. **Live machinery was invisible.** A background loop kept submitting test jobs, a peer still held
   a window on the shared laptop, and a session had uncommitted edits on disk. None was on the
   page, so the new account started a second runner, or a peer's edits were lost.
4. **The page was not where the new account looked.** It sat in a scratch folder the new account
   never opened, and the memory index that loads every session did not point at it.
5. **Something changed under the new account.** After the switch, a tool needed an extra setting
   (an inherited environment variable broke one command). The old account knew; the page did not.

## Context / Trigger Conditions

- A usage warning, the user saying "usage is low", or a weekly reset that is days away.
- More than two workstreams, or anything running unattended (loops, monitors, scheduled checks).
- Peers or shared hosts that the next coordinator must not disturb.

## Solution

1. **Start the handover while about 10 to 15 percent of the budget is left**, not at the limit.
   Write it first, then keep working and update it.
2. **One page, in a durable place outside any worktree or temp folder**, and add one line pointing
   to it in the memory index that loads every session. Name it with the date and "usage limit".
3. **List the workstreams in the order they should start, coordinator first.** For each:
   - what it is, in one plain sentence;
   - where it stands: branch, head commit, pull request and its state, what is running;
   - what waits on the user, and what must never be redone (decisions already made);
   - **a paste-in starter line**: the exact message to start a fresh session on it, naming the
     files to read first. The user pastes it; they do not explain anything.
4. **A "live right now" section**: every background loop (what it runs, its log, how to stop it
   safely), every hold or grant on a shared host and when it ends, every uncommitted edit on disk
   (path and owner), every scheduled check.
5. **A "changed under you" section**: tool quirks, credentials or settings that differ for the new
   account, and the one command that proves each works.
6. **Last line: what to do first.** Usually "read this page to the bottom, then check the live
   section before starting anything".

When you are the one inheriting: read the whole page, re-measure the "live right now" section
(processes, hold files, branch heads) before acting on it, and correct the page where it is wrong.

## Verification

- A fresh session given only the page and one starter line can say what to do next without asking.
- Every process in `ps` that belongs to the old work appears on the page.
- The memory index has the one pointer line, and the page path in it exists.

## Notes

- The page is a copy the moment it is written. Put a timestamp beside each claim, so the reader
  knows what to re-check.
- Keep the user's decisions out of the page's paraphrase: link where their words are recorded.

## See also

- `session-context-runs-out-mid-brief-measure-first-hand-back-early`: the same problem for one
  dispatched session's context budget.
- `credit-stall-mid-orchestration-revive-collision`: stalled agents reviving beside their
  replacements.
