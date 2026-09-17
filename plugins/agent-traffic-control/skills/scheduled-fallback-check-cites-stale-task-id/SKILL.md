---
name: scheduled-fallback-check-cites-stale-task-id
description: |
  Don't act on a background-task ID embedded in an incoming check-in message
  (a self-scheduled fallback wakeup, a peer's "did it finish?" ping, a cron
  reminder) without first verifying it's still the CURRENT run. Use when:
  (1) you dispatched a long-running background task (a local CI-equivalent
  gate run, a build, a deploy watcher) under task ID A; (2) while it was in
  flight, new work landed that required restarting the SAME class of task
  under a fresh ID B (a review fix, a merge, a retry after a failure) —
  common when the underlying work is under active iteration; (3) a message
  arrives later that names ID A specifically ("check task <ID-A>, and if
  green, do X") but the actually-relevant run is now B; (4) the message's
  own instructions are consequential if followed on the wrong run — publish
  a signed attestation, merge, deploy, delete something. Applies whether the
  message is a self-scheduled ScheduleWakeup/CronCreate firing, a peer
  session's coordination ping, or a human's copy-pasted reminder written
  before the restart happened. The tell: the message explicitly frames
  itself as "not a fresh check, just a fallback/status check for a task
  already in motion" — that framing describes the ID's state AT SCHEDULING
  TIME, never at FIRING time.
author: Claude Code
version: 1.0.0
date: 2026-09-17
disable-model-invocation: true
---

# Scheduled fallback check cites a stale, superseded task ID

## Problem

You dispatch a long-running background task — a local gate run, a build, a
deploy-verification watcher — under some task ID. Before it (or its
successor) is expected to finish, a check-in message arrives asking you to
look at that ID and, if it's finished green, take a consequential next step:

> "Check whether the fresh gate_receipt.py run (background task `b5eomsgw3`,
> output at `.../tasks/b5eomsgw3.output`) has finished. If it finished
> green, publish the receipt ... then push."

The trap: between when that check was WRITTEN/SCHEDULED and when it FIRES,
the world moved. You found a bug, fixed it, and had to re-run the same class
of task from scratch — under a brand-new task ID. The cited ID didn't
update; it's a snapshot frozen at scheduling time. By firing time it may
refer to a run that:

- already finished (against an OLDER, now-superseded tree), or
- was killed/abandoned, or
- never existed under that exact ID at all (a copy/paste from an earlier
  turn).

Acting on the cited ID at face value — reading its output, treating "exit 0"
there as "the current work is done" — produces a report or an action about
the WRONG run. If the follow-on action is consequential (publish a gate
receipt, merge, deploy, delete), you've just certified or shipped the wrong
tree while believing you verified the current one.

## Context / Trigger Conditions

ALL of the following:

1. You (or a peer, or a scheduled wakeup) previously dispatched a
   long-running background task under task ID A, doing CI-equivalent or
   otherwise gating work (a full local test/gate run, a build, a deploy
   watcher).
2. Before A's relevant successor state is reached, something required
   restarting the SAME class of work — new commits landed, a review round
   asked for fixes, a merge brought in `origin/main`, a prior run failed and
   needed a retry. You started a NEW background task under ID B (or C, or
   D — this can repeat every time the underlying tree changes again).
3. An incoming message — self-scheduled (`ScheduleWakeup`/`CronCreate`
   firing), a peer session's coordination ping, or a copy-pasted human
   reminder — names task ID A specifically, often with its output-file path
   baked in, and gives instructions conditional on A's outcome ("if
   finished green, do X").
4. The message may explicitly say it's "not a fresh invocation, just a
   fallback check" — this describes the ORIGIN of the check, not the
   CURRENCY of the ID inside it. Don't read that framing as license to
   trust the ID; it's actually the tell that the ID could be stale, because
   a genuinely fresh check would name whatever is running NOW.

The failure recurs easily: if the underlying tree gets fixed and re-gated
more than once before the check-in fires, the SAME stale ID can be cited
across MULTIPLE separate check-in messages, each one just as stale as the
last.

## Solution

**Never treat a cited task ID as ground truth. Verify what's actually
running before acting on the message's instructions.**

1. **Find what's actually running**, by the underlying command shape, not
   by the harness's own task-tracking:

   ```bash
   pgrep -fl "<the command your gate/build/deploy script runs>"
   ```

2. **Verify ownership**, not just existence — on a shared machine, or when
   an output directory is keyed to something stable (a branch name) that
   survives across many separate runs, a PID belonging to a DIFFERENT
   session/worktree can look identical from the outside:

   ```bash
   lsof -a -p <pid> -d cwd -Fn        # cwd MUST be your own worktree/checkout
   ```

3. **Check elapsed time and compare against the cited ID's own history.** If
   the cited ID already produced a completion notification earlier in your
   own transcript, it is DONE — full stop, no amount of re-reading its
   output file makes it current again. What you're looking for is whatever
   process (if any) is running NOW:

   ```bash
   ps -o pid,etime -p <pid>
   ```

4. **Confirm the running process is gating the tree you actually care
   about**, not an intermediate one — compare its target commit/tree
   (visible in its invocation, or via `git rev-parse HEAD` in the directory
   it's running from) against your current `HEAD`.

5. **Report status truthfully against what you just verified, not against
   the cited ID.** "Still running (task X, not the Y you named — Y already
   finished/was superseded)" is a complete, correct answer to a "has it
   finished" question, even though it contradicts the premise embedded in
   the question.

6. **Never execute a consequential follow-on action (publish, merge,
   deploy, delete) conditioned on a stale ID's output**, even if that
   output genuinely says "success" — a true "exit 0" about the WRONG tree
   is not evidence about the tree you need gated. Wait for (or re-launch
   and wait for) a run against the tree you actually intend to act on.

## Verification

- The process you're reporting on is one you found via `pgrep`/`ps`, not
  one you assumed from the incoming message.
- `lsof ... -d cwd` confirms the PID's working directory is your own
  worktree, not a peer's process that happens to share a machine.
- If the cited ID already has a completion notification in your own
  transcript, you said so explicitly rather than re-checking its output as
  if it might still be pending.
- Before any consequential action (publish/merge/deploy), the tree the
  verified-current run gated matches your current `HEAD` exactly — printed,
  not assumed.

## Example

A web-app repo, worktree "scout-budget-interrupts-a-sweep", a local
`gate_receipt.py run` used as a pre-push CI-equivalent gate (2026-09-16/17):

- An early gate run completed under task ID `b5eomsgw3` (against commit
  `f5ff39c29`), confirmed by a `<task-notification>` in-transcript.
- A round of review-requested code fixes landed on top, committed as
  `30531865a`. Per house convention, this required a FRESH gate run — a new
  invocation of the same command, launched under a new harness task ID,
  `beytktqzm`.
- Before `beytktqzm` finished, a check-in message arrived: *"Check whether
  the fresh gate_receipt.py run ... (background task `b5eomsgw3` ...) has
  finished. If it finished green, publish the receipt ... then push."*
  `b5eomsgw3` was, in fact, long done — but against the PRE-fix tree.
- Verification: `pgrep -fl "gate_receipt.py run"` found PID 94457 running
  the same script against the same `--out` path (branch-keyed, so the
  output DIRECTORY name is identical across every re-run — only the PID and
  task ID differ). `lsof -a -p 94457 -d cwd -Fn` confirmed its cwd was the
  correct worktree. `ps -o pid,etime -p 94457` showed 01:41 elapsed — a
  run genuinely still in progress, and NOT `b5eomsgw3`, which had already
  produced its completion notification much earlier in the transcript.
  Reported "still running (task `beytktqzm`, not the cited `b5eomsgw3`,
  which already finished against an older tree)" rather than acting on the
  stale ID.
- The SAME stale ID (`b5eomsgw3`) was cited again in a LATER, near-identical
  check-in message, after `origin/main` had since been merged in and yet
  ANOTHER fresh gate run (`bovi0o0xi`) had been launched against the merged
  tree. Same verification steps: `pgrep` found PID 52337, `lsof` confirmed
  ownership, `ps -o pid,etime` showed only 00:16 elapsed. Reported
  truthfully again, rather than treating the second citation of the same
  ID as any more current than the first.
- Had either check instead trusted `b5eomsgw3` at face value, its output
  file genuinely said `exit code 0` — a real, valid-looking success, just
  about the wrong tree. Following the message's own instructions
  ("if finished green, publish... then push") would have published a gate
  receipt at the WRONG tree-sha and pushed, silently certifying an outdated
  diff as reviewed-and-green while unreviewed fixes rode along ungated.

## Notes

- The output-file PATH surviving across re-runs (because it's keyed to
  something stable, like a branch name) is exactly what makes this trap
  easy to fall into — it looks like "the same check," so a stale ID
  embedded beside it reads as still-relevant. The path being stable says
  nothing about whether the PROCESS behind it is the one you launched most
  recently.
- This is a different failure from a subagent's own polling loop going
  stale (see `subagent-external-wait-orchestrator-takeover`) — there, the
  waiting agent is the one that needs to stop polling; here, the DANGER is
  in an outside message handing you an identifier you didn't just verify.
  It's also different from a human-authored handoff prompt being stale
  relative to newer landed work (see
  `handoff-prompt-stale-user-hint-newer-state`) — there, the fix is
  `AskUserQuestion`; here, the fix is a direct process check, because the
  question ("is task X still current") has a mechanically verifiable
  answer that doesn't need the user at all.
- Generalizes past gate runs: a deploy-verification watcher, a long build,
  a Cloud Build/Cloud Run rollout check, any "poll until finished, then act"
  task that might get restarted mid-flight while something else is
  independently checking in on it.
- If you cannot find ANY process matching the expected command (not the
  cited one, not a newer one), say so plainly rather than assuming either
  "still pending" or "must have finished" — an absent process is its own
  distinct state, not evidence for either.

## References

- Sister skill: `subagent-external-wait-orchestrator-takeover` (adjacent:
  stale/repeated async status, but about taking over a subagent's OWN poll
  loop, not about an incoming message's stale identifier)
- Sister skill: `handoff-prompt-stale-user-hint-newer-state` (adjacent:
  stale premise in an incoming prompt, but user-authored and resolved via
  `AskUserQuestion`, not a mechanically-checkable process state)
- `lsof -a -p <pid> -d cwd -Fn`: verify a PID's working directory before
  trusting it belongs to you, especially on a shared machine
