# leg-guard — one heavy test leg at a time, machine-wide

A `PreToolUse` hook on `Bash`. It refuses to start a heavy local test leg while
another session's is already running, and names the peer rather than guessing.

    python3 install.py --check      # say what is installed, change nothing
    python3 install.py              # copy to ~/.claude/tools/leg-guard/, point settings.json at it
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

**It reads the command the way a shell does.** Quoted text is one argument; a
heredoc body is data unless it is fed to a shell; `$( )`, backticks, `<( )`,
`bash -c` and `eval` strings are real commands and are read too; assignments,
keywords and wrappers (`time`, `caffeinate`, `timeout`, `env`, `nice`, `nohup`)
are stripped before asking what runs. The flat-text matcher it replaced blocked
five harmless commands in one session and missed 14 of 22 real ways of starting
a leg. Where the reader cannot follow — an unterminated quote, pathological
nesting, a command over 1 MB — it answers "starts nothing": a guard that
misfires gets switched off, so it errs quiet.

**It runs from a copy, with a timeout.** `install.py` copies the hook to
`~/.claude/tools/leg-guard/` and points settings.json there, with `"timeout": 10`.
The first install ran it from the git checkout under iCloud-synced `~/Documents`;
a missing hook file makes Python exit 2, and 2 is the code that BLOCKS, so a
branch switch or an iCloud eviction would have blocked every Bash call on the
machine. Re-run `install.py` after changing the hook; `--check` says whether
the copy is CURRENT, STALE or MISSING.

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
    python3 tests/mutation_check.py

Fifty cases. The end-to-end ones run the hook on the interpreter `install.py`
writes into settings.json (`/usr/bin/python3`, 3.9 on the machine this was
written for), not on the one running pytest — they differed, and a hook that
only worked on the newer one would have passed every test and crashed live,
where a crash fails open and switches the guard off unnoticed. The mutation
check breaks each of 23 guards in turn and fails if the suite does not notice.
It rewrites `leg_guard.py` while it runs, which is one more reason the live hook
runs from a copy.

**Every allow-case is paired with a block-case differing in one thing**, so a
guard that simply stops blocking cannot pass.

**History, because each step was found live, not in review of a diff:**

- The first build matched the leg pattern as a bare substring and blocked an
  edit whose heredoc merely *contained* `-m pytest prototype` as test data.
- The second anchored the match to the start of a shell segment, but cut the
  segments without knowing about quotes or heredocs. On 2026-09-22 it blocked
  five commands in one session: heredocs writing documents that quoted the gate
  commands, a `gh pr edit` whose body quoted the receipt runner, and a read-only
  `ps | grep` whose QUOTED `|` became a command boundary. It also missed 14 of
  22 real invocation forms. That is what the shell reader replaced.
- A three-reviewer pass on the reader found that nested `eval $( )` made the
  work triple per level (182 characters: 21.6 s, 776 MB) — fixed by reading each
  distinct inner text once — plus a `py.test` spelling the fast path never let
  through, `sh -s -- args`, CRLF input handled only by two quirks cancelling,
  one undecodable byte in `ps` output silently switching the guard off, and the
  missing-file exit 2 above. Each is pinned in `tests/test_review_findings.py`
  or `tests/test_install.py`.
- The override text first suggested prefixing `DR_LEG_FORCE=1 `, which reads as
  shell syntax but is a text marker; it now says anywhere, including a comment.
- The mutation check's first run found a vacuous wrapper-shell test and no test
  at all for the hook excluding its own process chain.

**Known limits, deliberately not handled** (the guard errs quiet):

- A leg named only at run time — `xargs -I{} ... pytest {}` fed a suite name,
  or `eval "$(cat <<EOF ... EOF)"` — cannot be seen by reading the text.
- Wrappers outside the list above (`watch`, `parallel`, `stdbuf`, `script`,
  `unbuffer`, `xargs`) are not stripped, so a leg behind them is missed.
- A command over 1 MB is not read.
- `DR_LEG_FORCE=1` counts anywhere in the text, including inside data, so a
  document that mentions it lets a real leg in the same call through. Matching it
  only in a real comment would need the reader to keep comments, which it drops.
- bash runs the lines before a later syntax error; the reader answers "starts
  nothing" for the whole unparseable command.

Like `resume-gate`'s check since v1.27.0, the mutation check refuses rather than
reporting a vacuous pass when pytest is unavailable, by re-running the suite on
the restored file.
