#!/usr/bin/env python3
"""Break each of leg-guard's guards in turn; fail if the suite does not notice.

A passing suite is not evidence the suite can fail. This one earned its place:
on first run it found that `test_a_wrapper_shell_is_not_counted_as_a_leg`
passed for the wrong reason -- its fixture lacked the `python -m pytest` text,
so it never reached the wrapper filter it was named after.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE.parent / "leg_guard.py"

MUTATIONS = [
    ("the block never fires",
     "    return 2                                       # 2 is what blocks",
     "    return 0                                       # 2 is what blocks"),
    ("wrapper shells are counted as legs",
     "        if WRAPPER_PATTERN.search(cmd):\n            continue",
     "        if False:\n            continue"),
    ("the override is ignored",
     "    if OVERRIDE in cmd:",
     "    if False:"),
    ("xdist workers are not collapsed",
     "        if ppid in {h[0] for h in hits}:\n            continue                      # a worker of another matched row",
     "        if False:\n            continue                      # a worker of another matched row"),
    ("the peer match becomes case-sensitive",
     "% _SUITE_ALT, re.I)", "% _SUITE_ALT, 0)"),
    ("a leg is matched as flat text again (fires on a mere mention)",
     "    try:\n        argvs = command_argvs(cmd)\n    except _Unparseable:\n        return False                        # the shell would refuse it too\n    return any(_is_leg(a) for a in argvs)",
     "    import re as _re\n    return bool(_re.search(r\"pytest[^|;&]*\\b(%s)\\b\" % _SUITE_ALT, cmd))"),
    ("single quotes are not honoured",
     "            elif c == \"'\":\n                j = t.find(\"'\", i + 1)",
     "            elif False:\n                j = t.find(\"'\", i + 1)"),
    ("heredoc bodies are read as commands",
     "                i = self._heredoc_bodies(i + 1, pending)\n",
     "                i = i + 1\n"),
    ("commands inside $( ) and <( ) are dropped",
     "        return _Parser(self.t, self.out, self.depth + 1).parse(i, stop=True) + 1",
     "        return _Parser(self.t, [], self.depth + 1).parse(i, stop=True) + 1"),
    ("an unquoted heredoc's $( ) is not read",
     "            if not quoted:                 # an unquoted body still runs $( ) and ``",
     "            if False:                      # an unquoted body still runs $( ) and ``"),
    ("wrapper commands are not stripped",
     "    return argv[i:]\n\n\ndef _dash_c_string",
     "    return argv\n\n\ndef _dash_c_string"),
    ("`sh -c` strings are not read",
     "            script = _dash_c_string(argv[1:])",
     "            script = None"),
    ("the fast path forgets the receipt runner",
     "    if \"pytest\" not in cmd and \"gate_receipt\" not in cmd:",
     "    if \"pytest\" not in cmd:"),
    ("an unparseable command blocks instead of starting nothing",
     "    except _Unparseable:\n        return False                        # the shell would refuse it too",
     "    except _Unparseable:\n        return True                         # the shell would refuse it too"),
    ("the nesting limit is removed (a crash would stand in for an answer)",
     "_MAX_DEPTH = 64 ",
     "_MAX_DEPTH = 10 ** 9 "),
    ("our own ancestry is not excluded",
     "        if pid in my_pids or ppid in my_pids:\n            continue",
     "        if False:\n            continue"),
]


def main() -> int:
    original = HOOK.read_text()
    failures = []
    try:
        for name, old, new in MUTATIONS:
            if original.count(old) != 1:
                failures.append("%s: anchor matched %d times, not 1"
                                % (name, original.count(old)))
                continue
            HOOK.write_text(original.replace(old, new))
            r = subprocess.run([sys.executable, "-m", "pytest", str(HERE), "-q"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                failures.append("%s: SURVIVED -- the suite passed with this broken"
                                % name)
            else:
                print("  caught: %s" % name)
    finally:
        HOOK.write_text(original)

    r = subprocess.run([sys.executable, "-m", "pytest", str(HERE), "-q"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        failures.append("the suite does not pass on the RESTORED file")

    if failures:
        for f in failures:
            print("  FAIL: %s" % f)
        return 1
    print("all %d mutations caught; suite green on the restored file" % len(MUTATIONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
