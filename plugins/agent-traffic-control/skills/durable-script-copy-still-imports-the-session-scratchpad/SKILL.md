---
name: durable-script-copy-still-imports-the-session-scratchpad
description: |
  You copied a script out of the session scratchpad into a durable directory so the
  next session (or the next you) can re-run it — but it still imports a helper from
  the scratchpad, so the copy dies with `/tmp` and looks complete until someone runs
  it. Use when: (1) you are saving a wrap-up, re-run or analysis script anywhere
  outside the scratchpad; (2) a handoff note, issue or pull request body points a
  reader at a script "saved to" a durable path; (3) you are about to say a script,
  log or artefact is preserved; (4) you are re-running a predecessor's saved script
  and hit `ModuleNotFoundError`, `source: no such file`, or `Cannot find module`.
  A copy is durable only if its DEPENDENCIES are: a `sys.path.insert` of the session
  directory, a relative `source helper.sh`, a `require('./lib')`, or a data file read
  by absolute scratchpad path all outlive the copy by exactly as long as the temp
  directory lives. The failure is deferred to whoever trusts the handoff, and the
  bytes look identical to a working script. Copy every local import beside it,
  repoint the path to the script's own directory, and run the durable copy from the
  durable directory before you call it saved.
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# A Durable Copy of a Script That Still Imports the Session Scratchpad

## Problem

The session scratchpad — a per-session directory under the system temp tree — is where a
session writes its working scripts. At the end of the run you copy the useful one somewhere
durable so the next session can re-run it: a logs directory outside the temp tree, a
repo path, a shared folder.

The copy is a real copy and reads as finished. It is also **dead on arrival** if it still
reaches back into the scratchpad for anything: a helper module on `sys.path`, a sourced
shell fragment, a relative `require`, a data file named by absolute path. Nothing fails at
copy time. Nothing fails while this session is alive, because the scratchpad is still there.
It fails for the reader, later, with a `ModuleNotFoundError` naming a directory that no
longer exists — and by then nobody knows what the helper contained.

## Context / Trigger Conditions

- You are copying a script out of the scratchpad and calling it preserved.
- Your handoff note, issue comment or pull request body says a script "is saved at
  `<durable path>`" so a successor can re-run it.
- A predecessor's saved script fails on import, source, or a missing data file whose path
  starts with a temp directory or a session UUID.
- You are writing a wrap-up script that you already know a later session will re-run (a
  tracker update, an idempotent report rebuild, a re-check of a published figure).

## Solution

### Step 1 — Grep the copy for anything that points at the scratchpad

```bash
grep -rnE '/(private/)?tmp/|/var/folders/|scratchpad|sys\.path|source |require\(' <durable-dir>
```

Every hit is either a dependency to bring along or a path to rewrite. A `sys.path.insert`
naming the session directory is the classic; an absolute input path is the quiet one,
because the script starts fine and dies in the middle.

### Step 2 — Bring the dependencies, do not just the entry point

Copy each local helper beside the script. One directory, everything it needs.

### Step 3 — Repoint the path to the script's OWN directory

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

Shell: `. "$(dirname "$0")/helper.sh"`. Node: a relative `require` already resolves against
the file, so what breaks there is data paths rather than modules.

### Step 4 — Run the durable copy FROM the durable directory

```bash
cd <durable-dir> && python3 ./wrapup.py --dry-run
```

Running it from the scratchpad proves nothing: the scratchpad is on the path and the helper
is right there. If the script has no dry-run mode, run it in a throwaway copy of its target.

### Step 5 — Make the check unfakeable while the scratchpad still exists

The honest test is whether the copy works with the scratchpad **unreachable**:

```bash
mv "$SCRATCHPAD" "$SCRATCHPAD.hidden"      # your own session's, never a peer's
( cd <durable-dir> && python3 ./wrapup.py --dry-run ); rc=$?
mv "$SCRATCHPAD.hidden" "$SCRATCHPAD"
echo "durable-copy-exit=$rc"
```

That is the state the next reader is in. Anything else is a rehearsal on a stage that will
have been struck.

## Verification

- The grep in Step 1 returns nothing that names a temp path or the session directory.
- The script runs to completion from the durable directory, with the scratchpad renamed.
- The handoff note names the durable path, and a reader following it needs nothing else.

## Example

A wrap-up script that edits a hand-maintained data file was written in the scratchpad
alongside a small parsing helper, then copied to a durable directory outside the temp
tree at the end of the session. The copy carried
`sys.path.insert(0, "<session scratchpad>")` and imported the helper by name. It would have raised `ModuleNotFoundError` the first time a later session ran
it — after the temp directory was cleared — while the directory listing showed a complete,
recently-saved script. Fixed by copying the helper beside it and repointing the insert at
`os.path.dirname(os.path.abspath(__file__))`.

## Notes

- **A note's stale path is visibly a path; a script's is one line of setup nobody reads.**
  The existing rule for handoff NOTES — rewrite scratchpad paths to repo-relative ones — does
  not cover this, because here the path is code rather than prose.
- **The same class covers data, not only code**: a script that reads its input from an
  absolute scratchpad path is exactly as dead, and fails later in the run, which is worse.
- **Do not solve it by pointing the durable copy at a peer's directory** or at anything under
  another session's tree — that trades a dead path for a path that moves under you.
- **Preservation claims are claims.** "Saved to `<path>`" belongs in a handoff only after
  Step 4 has been run; until then, say the script exists and is untested outside the session.

## References

- [`recover-killed-session-from-transcript-and-worktree`](../recover-killed-session-from-transcript-and-worktree/SKILL.md)
  — the reader on the other end of this: a later session reconstructing a dead run from its
  leftovers, for whom a script that cannot run is a dead end rather than a head start.
- [`session-context-runs-out-mid-brief-measure-first-hand-back-early`](../session-context-runs-out-mid-brief-measure-first-hand-back-early/SKILL.md)
  — what to put where the next reader will find it when a session ends early.
