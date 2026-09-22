# leg-guard — one heavy test leg at a time, machine-wide

A `PreToolUse` hook on `Bash`. It refuses to start a heavy local test leg while
another session's is already running, and names the peer rather than guessing.

    python3 install.py --check      # say what is installed, change nothing
    python3 install.py              # install into ~/.claude/settings.json
    python3 install.py --uninstall

## Why it exists

`parallel-gate-legs-killed-for-memory-count-cannot-see-ram` has said *"test for
ZERO, not for under N"* and *"put the guard inside the command that starts the
leg"* since 2026-09-17. On 2026-09-22, **four sessions ran the same pytest suite
concurrently** on one laptop at load average 14, and one leg was killed at 537 s
with `exit=-15`, writing no measurement at all. Nobody had broken a rule they
knew about; they had not consulted it. A rule that costs nothing to skip is not
a rule.

## What a blocked session sees

    BLOCKED by leg-guard: 3 peer test leg(s) are already running on this machine.

      9167    00:51     Python -m pytest docs -q -m not slow
      77378   08:28     Python -m pytest prototype -q
      79113   07:50     Python -m pytest prototype -q

    Two suites at once make every session slower and every timing unquotable,
    and a leg killed under contention writes NO measurement -- it reads as a
    test failure to whoever finds it next. Wait for these to finish.

    If you genuinely must proceed, say so deliberately:

      DR_LEG_FORCE=1 .venv/bin/python -m pytest prototype -q

    Do NOT kill a peer's leg to clear the way: it destroys a measurement its
    owner will read as red.

    Free memory now: 68 MB (context only -- this guard counts
    processes and cannot see RAM).

## Decisions worth not re-litigating

**It blocks rather than warns, with an override.** Warning is what the skill
already did in words, and four sessions ignored it. The `DR_LEG_FORCE=1` escape
means a stuck peer leg can never deadlock the machine, and an override is
visible in the transcript, where forgetting is not.

**It counts lines, not a bare count, and tests for zero.** One leg can read as
2; the same machine reports 5, 2 or 7 depending on one letter's case, because a
venv `python` execs a binary with a capitalised `argv[0]`. So the peer pattern
is case-insensitive, wrapper shells are excluded explicitly, xdist workers are
collapsed onto their parent, and the threshold is zero — the one value that
survives every counting error, since each contributor adds lines rather than
removing them.

**It fails OPEN.** This runs on every `Bash` call in every session. A crashing
hook that blocked everything would be far worse than one that blocked nothing,
and exit codes other than 2 do not block anyway, so refusing could never be made
reliable through failure. Internal errors allow the command and say why.

**It never kills anything and never judges memory.** A peer's leg is a peer's
measurement. And a process count is a CPU-and-contention rule that cannot see
RAM — it prints free memory as context and decides nothing on it.

## Cost

About **28 ms** on an ordinary `Bash` call and **90 ms** on one that is a heavy
leg, measured on the machine this was written for. The ordinary-call cost is
Python start-up: the script returns before running `ps` for anything that is not
a leg. If that is too much, add a handler-level `if` pre-filter — but read
`install.py`'s docstring first, because putting `if` in the wrong place disables
the hook silently and completely.

## Tests

    python3 -m pytest tests/ -q

Thirteen cases, each paired so an allow-case and a block-case differ in exactly
one thing. Every guard has been mutation-checked: breaking it makes the suite
fail. The mutation check found **two real defects on its first run**. One was a
vacuous test: the wrapper-shell fixture lacked the `python -m pytest` text, so it
passed without ever reaching the filter it was named after — it now asserts the
fixture still matches the peer pattern before testing that the wrapper filter
excludes it. The other was a missing test entirely: nothing covered the hook
excluding its own process chain, so it could have counted itself as a peer and
blocked every leg on an idle machine.

Like `resume-gate`'s check since v1.27.0, it refuses rather than reporting a
vacuous pass when pytest is unavailable, by re-running the suite on the restored
file — verified under an interpreter with pytest blocked.
