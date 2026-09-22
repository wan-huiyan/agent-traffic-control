#!/usr/bin/env python3
"""leg-guard — refuse to start a heavy local test leg while a peer's is running.

A PreToolUse hook on Bash. It exists because the advisory rule did not work:
`parallel-gate-legs-killed-for-memory-count-cannot-see-ram` has said
"test for ZERO, not for under N" and "put the guard inside the command that
starts the leg" since 2026-09-17, and on 2026-09-22 four sessions ran the same
pytest suite concurrently on one laptop anyway, at load average 14. One of those
legs was killed at 537s with exit=-15 and wrote no measurement at all.

WHAT IT DOES

  Bash command does not look like a heavy leg  -> allow, immediately
  DR_LEG_FORCE=1 present in the command        -> allow, and say so on stderr
  no peer leg running                          -> allow
  a peer leg is running                        -> BLOCK (exit 2), naming it

FOUR THINGS THAT ARE EASY TO GET WRONG, ALL LEARNED THE HARD WAY

1. The top-level `matcher` is a regex on the TOOL NAME ONLY. It cannot see the
   command a Bash call runs, so the command test has to happen in here. (A
   handler-level `if` can pre-filter, but it is a permission-rule matcher and
   does not express "contains pytest" reliably; see install.py.)

2. Exit 2 is what BLOCKS a PreToolUse hook. Exit 0 allows. Any other exit code
   is an error and does NOT block, so a crash must never be relied on to refuse.

3. A bare process count is unreliable. One leg can read as 2, and the SAME
   machine reports 5, 2 or 7 depending on one letter's case in the pattern,
   because a virtualenv `python` execs a binary whose argv[0] is capitalised.
   So this reads LINES with parentage and filters wrapper shells explicitly,
   and tests for ZERO rather than for "under N".

4. It must FAIL OPEN. This runs on every Bash call in every session; an
   exception here would brick them all. Any internal error allows the command
   and prints the reason, because a guard that silently blocks everything is
   worse than one that silently blocks nothing.

WHAT IT DELIBERATELY DOES NOT DO

  It does not judge memory. A process count is a CPU-and-contention rule and
  cannot see RAM -- that is the whole point of the skill above. It prints a
  memory reading as context and never decides on it.

  It does not kill anything. A peer's leg is a peer's measurement; killing one
  destroys a result silently and the owner reads the corpse as a test failure.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Suite directories whose runs are heavy enough to be worth serialising.
SUITES = ("prototype", "server", "tracker", "docs", "stravart")

# What counts as starting a heavy leg, in the command WE are about to run.
_SUITE_ALT = "|".join(SUITES)
LEG_PATTERNS = (
    re.compile(r"\bpytest\b[^|;&]*\b(%s)\b" % _SUITE_ALT),
    re.compile(r"gate_receipt\.py\s+run\b"),
)

# What counts as a peer's leg, in a `ps` line. Deliberately case-insensitive:
# a venv python execs a framework binary with a capitalised argv[0], and the
# same machine reports different counts for [p]ython and [P]ython.
PEER_PATTERN = re.compile(r"python[^|;&]*-m\s+pytest\b[^|;&]*\b(%s)\b" % _SUITE_ALT, re.I)

# Lines that are a shell WRAPPING a leg, not the leg itself. Counting these
# double-counts every run and makes any threshold unsatisfiable.
WRAPPER_PATTERN = re.compile(r"^/bin/(?:ba|z)?sh\s+-c\b|\bclaude/shell-snapshots\b")

OVERRIDE = "DR_LEG_FORCE=1"


def _ps_lines() -> list[tuple[int, int, str, str]]:
    out = subprocess.run(
        ["ps", "-axo", "pid,ppid,etime,command"],
        capture_output=True, text=True, timeout=10,
    ).stdout.splitlines()
    rows = []
    for line in out[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        rows.append((pid, ppid, parts[2], parts[3]))
    return rows


def peer_legs(my_pids: set[int]) -> list[tuple[int, int, str, str]]:
    """Peer legs, one row per real interpreter, wrappers and our own excluded."""
    hits = []
    for pid, ppid, etime, cmd in _ps_lines():
        if pid in my_pids or ppid in my_pids:
            continue
        if WRAPPER_PATTERN.search(cmd):
            continue
        if PEER_PATTERN.search(cmd):
            hits.append((pid, ppid, etime, cmd))
    # xdist workers share a parent; collapse them so one leg reads as one leg.
    seen_parents, collapsed = set(), []
    for pid, ppid, etime, cmd in hits:
        if ppid in {h[0] for h in hits}:
            continue                      # a worker of another matched row
        if ppid in seen_parents:
            continue
        seen_parents.add(ppid)
        collapsed.append((pid, ppid, etime, cmd))
    return collapsed


def free_mb() -> int | None:
    """Real free memory, read with THIS machine's page size, not a constant."""
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        page = int(re.search(r"page size of (\d+) bytes", vm).group(1))
        free = int(re.search(r"Pages free:\s+(\d+)", vm).group(1).replace(".", ""))
        return free * page // 1048576
    except Exception:
        return None


def my_process_ancestry() -> set[int]:
    """Our own pid and forebears, so we never count ourselves as a peer."""
    pids, pid = set(), os.getpid()
    rows = {p: pp for p, pp, _, _ in _ps_lines()}
    for _ in range(12):
        if pid in pids or pid <= 1:
            break
        pids.add(pid)
        pid = rows.get(pid, 0)
    return pids


def _readable(cmd: str, width: int = 88) -> str:
    """Show the part that identifies the LEG, not the interpreter path.

    A venv interpreter path is ~90 characters, so a left-truncated command
    line shows ".../Versions/3.12/Resources/P" and nothing about which suite
    is running -- which is the one thing the reader needs.
    """
    m = re.search(r"(-m\s+pytest\b.*)$", cmd)
    tail = m.group(1) if m else cmd
    head = cmd.split()[0].rsplit("/", 1)[-1] if cmd.split() else "?"
    out = "%s %s" % (head, tail)
    return out if len(out) <= width else out[: width - 1] + "\u2026"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                                   # fail open: not our business
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not cmd or not any(p.search(cmd) for p in LEG_PATTERNS):
        return 0                                   # not a heavy leg

    if OVERRIDE in cmd:
        sys.stderr.write(
            "leg-guard: %s present, starting anyway. Peers running: %d\n"
            % (OVERRIDE, len(peer_legs(my_process_ancestry())))
        )
        return 0

    legs = peer_legs(my_process_ancestry())
    if not legs:
        return 0

    mb = free_mb()
    lines = [
        "BLOCKED by leg-guard: %d peer test leg(s) are already running on this machine."
        % len(legs),
        "",
    ]
    for pid, ppid, etime, c in legs[:6]:
        lines.append("  %-7s %-9s %s" % (pid, etime, _readable(c)))
    lines += [
        "",
        "Two suites at once make every session slower and every timing unquotable,",
        "and a leg killed under contention writes NO measurement -- it reads as a",
        "test failure to whoever finds it next. Wait for these to finish.",
        "",
        "If you genuinely must proceed, say so deliberately:",
        "",
        "  %s %s" % (OVERRIDE, cmd.strip()[:120]),
        "",
        "Do NOT kill a peer's leg to clear the way: it destroys a measurement its",
        "owner will read as red.",
    ]
    if mb is not None:
        lines.append("")
        lines.append("Free memory now: %d MB (context only -- this guard counts" % mb)
        lines.append("processes and cannot see RAM).")
    sys.stderr.write("\n".join(lines) + "\n")
    return 2                                       # 2 is what blocks


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                        # fail open, loudly
        sys.stderr.write("leg-guard: internal error, allowing command: %r\n" % (exc,))
        sys.exit(0)
