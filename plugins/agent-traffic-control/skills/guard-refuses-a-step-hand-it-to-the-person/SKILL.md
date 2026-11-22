---
name: guard-refuses-a-step-hand-it-to-the-person
description: |
  A safety hook or guard refuses a step the user asked for, perhaps in a repository or context
  it was not written for. Use when a hook blocks a command and tells you not to work around it,
  or when you are tempted to reach the same result another way.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# A Guard Refuses a Step: Hand the Step to the Person, Do Not Route Around It

## Problem

Guards on an agent's commands are written for one place and usually apply everywhere. A rule
"agents open pull requests only as drafts and never mark one ready" was written for one busy
repository, where a ready flip starts an expensive test run. It also fired in a small skills
repository where marking a pull request ready costs nothing, and the user had asked for exactly
that.

The tempting moves all defeat the guard:

- the same action through another command (`gh api` instead of `gh pr ready`);
- the same action through another tool (a browser, a different CLI, a script);
- asking a peer agent, which has the same guard, or none;
- arguing that this case is harmless and running it anyway.

Each one turns a guard into a suggestion. The next time, in the place the guard was written for,
the same reasoning goes through.

## Context / Trigger Conditions

- A hook's refusal message says the step is not allowed, or says not to find a way round it.
- The user asked for the step directly, so it feels authorised.
- You can see a second route to the same result.

## Solution

1. **Stop at the refusal.** Do not try the step another way, through another tool, or through
   another agent.
2. **Tell the user plainly**: which step was refused, by which guard, and that you will not route
   around it.
3. **Give them the shortest way to do it themselves**: exact buttons or one command, in order,
   and what to tell you afterwards so you can finish (for example, "say when it is merged and I
   will update the installed copy").
4. **Name the real fix in one line**: the guard's scope or rule is theirs to change (for example,
   limit it to the repository it was written for). Do not edit the guard yourself unless they ask.
5. Carry on with every part of the task the guard does not block.

## Verification

- No command after the refusal produces the refused effect.
- The user's next step is a short, exact list they can follow from a phone.

## Notes

- A guard that refuses more than its rule intends is still a guard until its owner changes it.
- If a guard is clearly broken (it refuses everything), say so with the evidence; still do not
  bypass it.

## See also

- `orchestrator-rule-too-strict-stalls-agent-silently`: a rule so strict that nothing can satisfy
  it.
- `lesson-that-recurs-after-being-written-becomes-a-check`: where such guards come from.
