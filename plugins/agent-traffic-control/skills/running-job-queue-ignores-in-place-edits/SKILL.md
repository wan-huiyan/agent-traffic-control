---
name: running-job-queue-ignores-in-place-edits
description: |
  A shell loop feeds jobs one at a time from a queue file to a remote runner, and you edit that
  file while it runs. Use when a `sed -i` change to the queue never took effect, when you rebuild
  the queue to reorder it, or when a job you meant to keep never ran.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# A Running Job Queue Ignores In-Place Edits; Rebuild It From the Runner's Own Log

## Problem

A common shape for "one job at a time on a shared test machine":

```zsh
while read -r WORKTREE SHA LEG TARGET <&3; do
  submit ...; wait-for-final ...
done 3< jobs.txt
```

The loop opened `jobs.txt` once, on file descriptor 3. Two things follow.

1. **`sed -i` does not edit the file the loop is reading.** It writes a new file and renames it
   over the old name, so the name points at a new inode while the loop keeps reading the old one.
   Every swap, removal and reorder made this way is invisible: the loop goes on submitting the
   jobs you thought you had removed. Appending with `>>` does reach the loop, because it writes
   to the same inode, but it can only add to the end.
2. **Rebuilding the queue loses jobs when you count lines.** To reorder, you stop the loop and
   write a new file with "the lines not yet run". In one incident a rebuild took "lines 8 onward"
   when the loop had stopped after line 6. Line 7, a whole test leg another agent was waiting
   for, silently disappeared. Nothing failed; the other agent noticed hours later.

## Context / Trigger Conditions

- A background loop reads a queue file through a held file descriptor or a single `while read`.
- You want to drop stale jobs (a pull request moved to a new head), move a batch to the front, or
  swap a job's commit.
- Several agents depend on jobs in the queue.

## Solution

1. **To add at the end, append** (`echo ... >> jobs.txt`). That is the only safe live edit.
2. **To change anything else, rebuild:**
   1. Find the last job the runner actually submitted **from its own log line**
      (`submitted <sha> <leg> <target> <id>`), and locate that exact line in the queue file with
      `grep -n`. Never derive it from a count or from memory.
   2. Write a **new** file: the jobs you want first, then every line after the submitted one, with
      stale entries filtered by commit. Diff it against the old remainder and account for each
      dropped line by name.
   3. Check every job's checkout is still at its pinned commit and clean before restarting.
   4. Stop the loop (the in-flight remote job keeps running), then start the new loop behind a
      small wrapper that waits for that job's final state before the first submit.
3. **Point each job at its own pinned checkout** (one clone per pull request head), so a later
   push to the branch can't change what a queued job tests.
4. **If the starter has not opened the file yet** (it is still in the wait-for-the-running-job
   step), rewriting the file in place is safe. Check that no loop process holds it first.

## Verification

- `pgrep -fl '<loop script> <old file>'` is empty after the stop, and one loop runs the new file.
- Every line of the old file after the last submitted job appears in the new file, or is on your
  written list of deliberate drops.
- The first entry in the new loop's log is the job you put first.

## Notes

- The same inode trap applies to any reader holding a file open: `tail -f` on a rotated log,
  a config read once at start, a lock file replaced rather than truncated.
- Rebuilds are cheap; a silently dropped job costs a full re-run, and the person waiting on it.

## See also

- `peer-window-grant-copy-the-parser-and-stay-quiet-while-live`: pausing the queue while a peer
  holds the shared host.
- `job-reports-success-while-its-worker-was-oom-killed`: reading the runner's final state honestly.
