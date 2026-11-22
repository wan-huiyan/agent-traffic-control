---
name: lesson-that-recurs-after-being-written-becomes-a-check
description: |
  The same mistake keeps happening even though a note, memory or house rule already says not to.
  Use when you find a lesson written down that was broken again, or when deciding whether a new
  rule belongs in a document or in an automatic check.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# A Lesson That Recurs After Being Written Down Becomes an Automatic Check

## Problem

Agents read notes only when they think to look, and a note is easy to skim past under pressure.
In one project, a memory note about stating facts from a stale copy existed, and the mistake still
happened four times in one session while the memory index pointed at that note. Other rules held
only once a hook enforced them:

- shell loops over an unquoted variable that splits into words;
- running local tests while a peer held the shared machine for a quiet window;
- marking a pull request ready without first counting the whole queue;
- showing the user a page whose figures no second agent had checked.

Each had been written down first, in plain words, more than once.

## Context / Trigger Conditions

- You find the mistake and also find the note that should have prevented it.
- The rule is mechanical: it can be decided from a command line, a file's presence, or a record
  on disk, without judgement.
- A wrong step is expensive or hard to undo (a paid test run, lost work, a user misled).

## Solution

1. **Once a written rule has been broken again, stop adding words to it.** Write a check instead:
   a hook on the tool call, a pre-commit or CI step, or a script the workflow must run.
2. **Make the refusal message the instructions.** It names the rule, why it exists, and the one
   allowed way through (the correct command, or the record that unlocks the step).
3. **Fail open only when the check itself is missing**, never when it cannot decide. A launcher
   that skips a deleted hook keeps work moving; a check that cannot read its inputs refuses.
4. **Give it a named override that needs the owner's word for a specific job**, and log every
   use.
5. **Keep the rule's numbers in one place.** If the document says "up to two at once" and the hook
   says one, the hook wins in practice; update both in the same change, or point the document at
   the hook's constant.
6. **Write down what the check cannot see.** A hook that reads only the command typed cannot see
   work a script starts; say so beside the rule.

## Verification

- Re-run the exact command that broke the rule: the check refuses it with the message from step 2.
- Run the allowed way through: the check lets it pass.
- Remove the check's input on purpose (missing record, unreadable state): it refuses, not passes.

## Notes

- Judgement calls stay in documents; checks are for rules a program can decide.
- A check that refuses more than the rule allows is a cost too. Review its numbers whenever the
  rule changes.

## See also

- `guard-refuses-a-step-hand-it-to-the-person`: what to do when a check refuses you.
- Before trusting a new check, reintroduce the old mistake and watch the check refuse it.
