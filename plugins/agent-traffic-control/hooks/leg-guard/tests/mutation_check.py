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
     "re.I)", "0)"),
    ("matching is un-anchored again (fires on a mere mention)",
     "def starts_a_leg(cmd: str) -> bool:\n    \"\"\"True only if some shell SEGMENT begins with a heavy-leg invocation.\"\"\"\n    segments = [cmd] + _SEGMENT.split(cmd)\n    return any(p.search(s) for s in segments for p in LEG_PATTERNS)",
     "def starts_a_leg(cmd: str) -> bool:\n    import re as _re\n    return bool(_re.search(r\"pytest[^|;&]*\\b(%s)\\b\" % _SUITE_ALT, cmd))"),
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
