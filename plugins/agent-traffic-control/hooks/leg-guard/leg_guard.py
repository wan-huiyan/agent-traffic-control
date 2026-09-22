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

FIVE THINGS THAT ARE EASY TO GET WRONG, ALL LEARNED THE HARD WAY

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

4. It must match a leg being RUN, not one being TALKED ABOUT. A substring
   match blocked an edit writing a test for one; anchoring to the start of a
   shell segment was not enough either, because the segments were cut without
   knowing about quotes or heredocs -- five false blocks on 2026-09-22 from
   heredocs and a quoted `|`. So the command is now READ like a shell reads it
   (see starts_a_leg), and a heredoc body or a quoted string is data.

5. It must FAIL OPEN. This runs on every Bash call in every session; an
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

# What counts as STARTING a heavy leg, in the command WE are about to run.
#
# The command is READ THE WAY A SHELL READS IT, not matched as flat text. The
# first version split on `|`, `;`, `&&` and newlines without knowing where
# quotes, heredocs and comments begin and end, then asked whether any piece
# began with a leg invocation. On 2026-09-22 that produced five false blocks in
# one session: heredocs writing documents that QUOTE the gate commands, a
# `gh pr edit` whose body quoted the receipt runner, and a read-only
# `ps | grep -E 'Python -m pytest|gate_receipt.py run'` whose QUOTED `|` became a
# command boundary. It also missed 14 of 22 real ways of starting a leg,
# including `time`, `caffeinate -i`, `timeout 600` and `env VAR=...`.
#
# So: quoted text is one argument; a heredoc body is data unless it is fed to a
# shell; `$( )`, backticks, `<( )`, `bash -c "..."` and `eval "..."` are real
# commands and are read too; assignments, keywords and wrapper commands in front
# of the real command are stripped before asking what it is.
#
# This is a SMALL reader, not a shell. Where it cannot follow (an unterminated
# quote, pathological nesting) it answers "starts nothing": the shell would
# refuse the first, and a guard that misfires gets switched off, so it errs quiet.
_SUITE_ALT = "|".join(SUITES)
_SUITE_RE = re.compile(r"\b(%s)\b" % _SUITE_ALT)
_PYTHON_RE = re.compile(r"^python(\d+(\.\d+)*)?$", re.I)   # python, python3.12, Python
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_KEYWORDS = frozenset(("{", "}", "!", "if", "then", "elif", "else", "do", "done",
                       "fi", "while", "until"))
_SHELLS = frozenset(("bash", "sh", "zsh", "dash", "ksh"))
_MAX_DEPTH = 64          # nested substitutions or `sh -c` strings; past this, fail open
_MAX_CHARS = 1000000     # a longer command is answered "starts nothing" unread
_FAST_WORDS = ("pytest", "py.test", "gate_receipt")   # no leg without one of these


class _Unparseable(Exception):
    """A shell would refuse this outright, so it cannot start a leg."""


class _Cmd(object):
    """One simple command: its words, and the heredoc bodies fed to it."""
    __slots__ = ("words", "heredocs")

    def __init__(self):
        self.words = []
        self.heredocs = []                  # (body, delimiter_was_quoted)


class _Parser(object):
    """Split shell text into simple commands, appending each to `out`.

    Commands found inside substitutions are appended to the same `out`, so the
    caller sees every command the shell would run, at any depth.
    """

    def __init__(self, text, out, depth=0):
        if depth > _MAX_DEPTH:
            raise _Unparseable("nested too deep")
        self.t, self.n, self.out, self.depth = text, len(text), out, depth
        self._cmd, self._word, self._in_word, self._skip = _Cmd(), [], False, False

    # -- words and commands -------------------------------------------------
    def _take(self, s):
        self._word.append(s)
        self._in_word = True

    def _end_word(self):
        if self._in_word:
            if self._skip:                  # a redirection target, not an argument
                self._skip = False
            else:
                self._cmd.words.append("".join(self._word))
        del self._word[:]
        self._in_word = False

    def _end_cmd(self):
        self._end_word()
        self._skip = False
        if self._cmd.words:
            self.out.append(self._cmd)
        self._cmd = _Cmd()

    # -- the pieces a shell treats specially --------------------------------
    def _subst(self, i):
        """`i` is just past `$(`, `<(` or `>(`: read the command inside it and
        return the index just past its closing `)`. It is parsed, not
        paren-counted, because a heredoc inside it may hold a `)` of its own."""
        return _Parser(self.t, self.out, self.depth + 1).parse(i, stop=True) + 1

    def _arith_end(self, i):
        """`i` is at the `$` of `$((`: return the index just past its `))`."""
        depth, j = 0, i + 1
        while j < self.n:
            if self.t[j] == "(":
                depth += 1
            elif self.t[j] == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise _Unparseable("unterminated $((")

    def _backtick_end(self, i):
        """`i` is just past an opening backtick: return the closing one's index."""
        j = i
        while j < self.n:
            if self.t[j] == "\\":
                j += 2
            elif self.t[j] == "`":
                return j
            else:
                j += 1
        raise _Unparseable("unterminated backtick")

    def _backticks(self, i):
        j = self._backtick_end(i + 1)
        _Parser(self.t[i + 1:j], self.out, self.depth + 1).parse(0)
        return j + 1

    def expansions(self, i, closer):
        """Read double-quote-like text from `i`, where only `\\`, `$(`, `$((`
        and backticks are special. With closer='"', stop past the closing quote;
        with closer=None (an unquoted heredoc body), read to the end. Returns
        (next index, the text read)."""
        t, n, buf = self.t, self.n, []
        while i < n:
            c = t[i]
            if closer is not None and c == closer:
                return i + 1, "".join(buf)
            if c == "\\" and i + 1 < n:
                buf.append(t[i + 1])
                i += 2
            elif t.startswith("$((", i):
                j = self._arith_end(i)
                buf.append(t[i:j])
                i = j
            elif t.startswith("$(", i):
                j = self._subst(i + 2)
                buf.append(t[i:j])
                i = j
            elif c == "`":
                j = self._backticks(i)
                buf.append(t[i:j])
                i = j
            else:
                buf.append(c)
                i += 1
        if closer is not None:
            raise _Unparseable("unterminated double quote")
        return i, "".join(buf)

    def _delimiter(self, i):
        """Read a heredoc delimiter from `i`: (word, was_quoted, next index)."""
        t, n = self.t, self.n
        while i < n and t[i] in " \t\r":
            i += 1
        buf, quoted = [], False
        while i < n and t[i] not in " \t\r\n;&|<>()":
            c = t[i]
            if c in "'\"":
                j = t.find(c, i + 1)
                if j < 0:
                    raise _Unparseable("unterminated quote in a heredoc delimiter")
                buf.append(t[i + 1:j])
                quoted, i = True, j + 1
            elif c == "\\" and i + 1 < n:
                buf.append(t[i + 1])
                quoted, i = True, i + 2
            else:
                buf.append(c)
                i += 1
        return "".join(buf), quoted, i

    def _heredoc_bodies(self, i, pending):
        """`i` starts the line after a newline: read each pending heredoc's body
        off the following lines and attach it to the command it feeds."""
        t, n = self.t, self.n
        for cmd, delim, strip_tabs, quoted in pending:
            lines = []
            while i < n:                   # an unterminated body runs to the end
                j = t.find("\n", i)
                line = t[i:] if j < 0 else t[i:j]
                i = n if j < 0 else j + 1
                line = line.rstrip("\r")
                if (line.lstrip("\t") if strip_tabs else line) == delim:
                    break
                lines.append(line)
            body = "\n".join(lines)
            cmd.heredocs.append((body, quoted))
            if not quoted:                 # an unquoted body still runs $( ) and ``
                _Parser(body, self.out, self.depth + 1).expansions(0, None)
        return i

    # -- the main loop ------------------------------------------------------
    def parse(self, i=0, stop=False):
        """Read commands from `i`. With stop=True, return the index of the `)`
        that closes the enclosing substitution."""
        t, n = self.t, self.n
        pending, parens = [], 0
        while i < n:
            c = t[i]
            if c == "\\":
                if i + 1 < n and t[i + 1] != "\n":
                    self._take(t[i + 1])
                i += 2                                      # `\<newline>` joins lines
            elif c == "'":
                j = t.find("'", i + 1)
                if j < 0:
                    raise _Unparseable("unterminated single quote")
                self._take(t[i + 1:j])
                i = j + 1
            elif c == '"':
                i, s = self.expansions(i + 1, '"')
                self._take(s)
            elif t.startswith("$'", i):                     # $'...' ANSI-C quoting
                j = i + 2
                while j < n and t[j] != "'":
                    j += 2 if t[j] == "\\" else 1
                if j >= n:
                    raise _Unparseable("unterminated $'")
                self._take(t[i + 2:j])
                i = j + 1
            elif t.startswith("$((", i):
                j = self._arith_end(i)
                self._take(t[i:j])
                i = j
            elif t.startswith("$(", i):
                j = self._subst(i + 2)
                self._take(t[i:j])
                i = j
            elif c == "`":
                j = self._backticks(i)
                self._take(t[i:j])
                i = j
            elif c in "<>" and i + 1 < n and t[i + 1] == "(":   # <( ) and >( )
                j = self._subst(i + 2)
                self._take(t[i:j])
                i = j
            elif c == "#" and not self._in_word:            # a comment, to end of line
                j = t.find("\n", i)
                i = n if j < 0 else j
            elif c in " \t\r":
                self._end_word()
                i += 1
            elif c == "\n":
                self._end_cmd()
                i = self._heredoc_bodies(i + 1, pending)
                pending = []
            elif t.startswith("&>", i):                     # &> and &>> redirect
                self._end_word()
                i += 3 if t.startswith("&>>", i) else 2
                self._skip = True
            elif c in ";&|":
                self._end_cmd()
                i += 2 if t.startswith(("&&", "||", "|&", ";;"), i) else 1
            elif c == "(":
                self._end_cmd()
                parens += 1
                i += 1
            elif c == ")":
                self._end_cmd()
                if parens == 0 and stop:
                    return i
                parens = max(0, parens - 1)
                i += 1
            elif c in "<>":
                if self._in_word and "".join(self._word).isdigit():
                    del self._word[:]                       # the `2` of `2>`
                    self._in_word = False
                else:
                    self._end_word()
                if t.startswith("<<<", i):                  # here-string: its word is data
                    i += 3
                    self._skip = True
                elif t.startswith("<<", i):
                    strip_tabs = t.startswith("<<-", i)
                    delim, quoted, i = self._delimiter(i + (3 if strip_tabs else 2))
                    pending.append((self._cmd, delim, strip_tabs, quoted))
                else:
                    i += 2 if t.startswith((">>", ">|", ">&", "<&", "<>"), i) else 1
                    self._skip = True
            else:
                self._take(c)
                i += 1
        self._end_cmd()
        if stop:
            raise _Unparseable("unterminated $(")
        return i


def _strip_prefix(argv):
    """Drop what runs BEFORE the real command: assignments, shell keywords and
    wrapper commands (`time`, `caffeinate -i`, `timeout 600`, `env X=1`, ...)."""
    i, n = 0, len(argv)
    while i < n:
        w = argv[i]
        base = os.path.basename(w)
        if _ASSIGNMENT.match(w) or w in _KEYWORDS:
            i += 1
        elif base in ("time", "nohup", "exec", "command", "builtin", "noglob"):
            i += 1
            while base == "time" and i < n and argv[i].startswith("-"):
                i += 1                                      # time -p
        elif base == "env":
            i += 1
            while i < n and (argv[i].startswith("-") or _ASSIGNMENT.match(argv[i])):
                i += 2 if argv[i] in ("-u", "-C", "-S", "-P") else 1
        elif base == "nice":
            i += 1
            if i < n and argv[i] == "-n":
                i += 2
            elif i < n and argv[i].startswith("-"):
                i += 1
        elif base == "caffeinate":
            i += 1
            while i < n and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-t", "-w") else 1
        elif base in ("timeout", "gtimeout"):
            i += 1
            while i < n and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            i += 1                                          # the duration
        else:
            break
    return argv[i:]


def _dash_c_string(args):
    """The command string of `bash -c STRING` (or `-lc`, `-ec`, ...), else None."""
    k = 0
    while k < len(args):
        a = args[k]
        if a in ("-o", "-O", "+o", "+O"):
            k += 2
        elif a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
            return args[k + 1] if k + 1 < len(args) else None
        elif a.startswith(("-", "+")):
            k += 1
        else:
            return None                                     # `bash script.sh`
    return None


def _reads_stdin(args):
    """True if a shell with these arguments reads its script from stdin: it
    has no script-file operand, or `-s` says its operands are positional
    parameters (`sh -s -- a b <<EOF`)."""
    k = 0
    while k < len(args):
        a = args[k]
        if a in ("-o", "-O", "+o", "+O"):
            k += 2
        elif a.startswith("-") and not a.startswith("--") and "s" in a[1:]:
            return True
        elif a.startswith(("-", "+")):
            k += 1
        else:
            return False                                # `bash script.sh`
    return True


def command_argvs(cmd, depth=0, memo=None):
    """Every command a shell would run for `cmd`, each as an argv with its
    prefix stripped -- including those inside substitutions, in `sh -c` and
    `eval` strings, and in heredocs fed to a shell. Raises _Unparseable.

    `memo` maps each inner text already read in this call to its result. It is
    the whole defence against nesting: a substitution's commands are collected
    by the enclosing parse AND its text is read again inside every enclosing
    `eval` / `sh -c` / heredoc-to-shell string, so without it the work grew 2-3x
    per level (182 characters took 21.6 s and 776 MB on 2026-09-22)."""
    if memo is None:
        memo = {}
    if cmd in memo:
        return memo[cmd]
    if depth > _MAX_DEPTH:
        raise _Unparseable("nested too deep")
    parsed = []
    _Parser(cmd, parsed).parse(0)
    argvs = []
    for c in parsed:
        argv = _strip_prefix(c.words)
        if not argv:
            continue
        argvs.append(argv)
        base = os.path.basename(argv[0])
        inner = []
        if base == "eval":
            inner = [" ".join(argv[1:])]
        elif base in _SHELLS:
            script = _dash_c_string(argv[1:])
            if script is not None:
                inner = [script]
            elif _reads_stdin(argv[1:]):
                inner = [body for body, _quoted in c.heredocs]
        for text in inner:
            try:
                argvs.extend(command_argvs(text, depth + 1, memo))
            except _Unparseable:
                pass                        # a broken inner string runs nothing
    memo[cmd] = argvs
    return argvs


def _names_a_suite(args):
    return any(_SUITE_RE.search(a) for a in args)


def _is_leg(argv):
    """Is this argv a heavy leg: pytest on a heavy suite, or the receipt runner?"""
    base = os.path.basename(argv[0])
    rest = argv[1:]
    if base in ("pytest", "py.test"):
        return _names_a_suite(rest)
    if base == "gate_receipt.py":
        return bool(rest) and rest[0] == "run"
    if not _PYTHON_RE.match(base):
        return False
    k = 0
    while k < len(rest):
        a = rest[k]
        if a == "-m":
            return (k + 1 < len(rest) and rest[k + 1] in ("pytest", "py.test")
                    and _names_a_suite(rest[k + 2:]))
        if a in ("-c", "-"):
            return False                    # a code string or a script on stdin
        if a in ("-X", "-W"):
            k += 2
        elif a.startswith("-"):
            k += 1
        else:                               # the first positional: a script
            script = os.path.basename(a)
            if script == "gate_receipt.py":
                return k + 1 < len(rest) and rest[k + 1] == "run"
            if script in ("pytest", "py.test"):
                return _names_a_suite(rest[k + 1:])
            return False
    return False


def starts_a_leg(cmd: str) -> bool:
    """True only if the shell would actually RUN a heavy leg for `cmd`."""
    if not any(w in cmd for w in _FAST_WORDS):
        return False                        # the fast path: nearly every Bash call
    if len(cmd) > _MAX_CHARS:
        return False                        # reading it would stall the call; err quiet
    try:
        argvs = command_argvs(cmd)
    except _Unparseable:
        return False                        # the shell would refuse it too
    return any(_is_leg(a) for a in argvs)

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
        capture_output=True, text=True, errors="replace", timeout=10,
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
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    cmd = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(cmd, str) or not cmd or not starts_a_leg(cmd):
        return 0                                   # not a heavy leg

    if OVERRIDE in cmd:
        sys.stderr.write(
            "leg-guard: %s marker present, starting anyway. Peers running: %d\n"
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
        "If you genuinely must proceed, say so deliberately by putting this",
        "marker ANYWHERE in the command. The guard looks for the text, so it",
        "needs no shell export and works inside a `cd x && ...` chain, or as",
        "a trailing comment:",
        "",
        "  <your command>   # %s" % OVERRIDE,
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
