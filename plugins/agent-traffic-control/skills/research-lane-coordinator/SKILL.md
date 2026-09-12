---
name: research-lane-coordinator
listing_tier: short
description: Coordinate independent research lanes, evidence review, PR-queue handoffs and tested workflow corrections. Use for multi-session research or retrospectives, not routine single-task edits.
---
# Research Lane Coordinator

Use this as a working aid, not a fixed ceremony. Scale coordination to the question; one agent is enough when work cannot profitably split. The user's goals and current repository instructions take precedence over examples and workflow preferences here.

## Start from the real state

Read the owner's goals and latest handoff, then reconcile relevant current code, merged work, open PRs, active writers and saved experiments. Keep one progress record linking each original goal to its evidence, limitation, owner and next action. A side discovery must not erase an unfinished goal.

For lane ownership, worker briefs and the boundary with a separate PR-queue coordinator, read [coordination](references/coordination.md). Use the project's existing queue and release procedure. Research acceptance, merged content and verified deployment are separate claims.

## Explore different questions in parallel

Select independent angles that could change the decision: for example, whether the measurements represent the intended outcome; whether better alternatives can be constructed; whether a learned selector chooses better alternatives; and whether data/feedback reaches the next experiment intact. These are examples, not mandatory lanes.

Give each worker a bounded question, pinned baseline and inputs, owned files, evidence required, resource limit and stop condition. Include relevant prior failures and owner corrections. Use small briefs and durable artifacts rather than copying the full session into every worker. Never override a worker's higher-priority instructions to save time. Honor the host's delegation and model-selection permissions.

Check exact outputs before accepting summaries. Preserve failed attempts and incomplete-search limits. Investigate conflicting signals before increasing model capacity or tightening a gate. Keep tuning separate from held-out evaluation and report the population and data versions beside each result.

## Convert progress into a decision

Compare alternatives under the same meaningful conditions. A better pooled score does not necessarily improve the user-facing shortlist or delivered result. When owner judgment is needed, show distinct, exactly identified alternatives using the agreed review method; never inherit a grade from a changed artifact.

Choose the next useful experiment, prepare a tested implementation for the queue coordinator, or document the limiting evidence. Do not continue a losing branch solely to keep agents busy. At a stop, preserve process state, artifacts, resource use and exact continuation steps outside temporary-only storage.

## Improve this workflow when experience warrants it

After a material failure, owner correction, contradiction, surprising result or handoff that reveals a material gap, read [the correction loop](references/correction-loop.md). Capture evidence first; reproduce or qualify the proposed cause; compare a narrow change with the current procedure; retain, revise or retire the guidance based on outcomes. Do not add a permanent rule merely because a single run disappointed.

Routine handoffs need only a continuity checkpoint; no correction event is required when nothing material was learned. A user request to improve this workflow can itself authorize the relevant local correction; do not ask again when that scope is already clear. It does not authorize unrelated memory changes.

This is an event-driven loop within authorized work, not a background scheduler or permission to rewrite arbitrary memory. Local workflow edits can proceed within an explicit maintenance grant; publishing, changing owner policies or touching unrelated memory requires the applicable authority. For memory-hygiene compatibility, use [the integration notes](references/memory-hygiene.md).
