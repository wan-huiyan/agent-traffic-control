#!/usr/bin/env python3
"""Install leg-guard into ~/.claude/settings.json (or --settings <path>).

    python3 install.py --check      say what is installed, change nothing
    python3 install.py              copy the hook to ~/.claude/tools/leg-guard/ and
                                    point settings.json at that copy
    python3 install.py --uninstall  remove the entry, then the copy

RUN A COPY, NEVER THE CHECKOUT
------------------------------
The first install pointed settings.json at leg_guard.py inside the git checkout
under ~/Documents. A missing hook file makes Python exit 2 ("can't open file"),
and 2 is exactly the code that BLOCKS a PreToolUse call -- so checking out a
branch without the file, or iCloud evicting it, would have blocked every Bash
call on the machine. The hook now runs from a copy in ~/.claude/tools/leg-guard/,
where every other hook here lives, with a 10 s timeout. Re-run this after
changing leg_guard.py; `--check` says whether the copy is CURRENT or STALE.

THE MISTAKE THAT MAKES THIS SILENT AND TOTAL
--------------------------------------------
The top-level `matcher` is a regex on the TOOL NAME ONLY. It cannot see the
command a Bash call runs. To filter on the command you would use a
HANDLER-level `if`, which is a sibling of `type` and `command` INSIDE the inner
`hooks` array -- never a sibling of `matcher`:

    {"matcher": "^Bash$",
     "hooks": [{"type": "command", "if": "Bash(git push:*)", "command": "..."}]}

Put `if` next to `matcher` and the hook simply never fires. Nothing warns you.

leg-guard deliberately uses NO `if`. Its commands start in too many ways
(`.venv/bin/python -m pytest`, `cd x && python -m pytest`, `scripts/gate_receipt.py
run`) for a prefix-matching permission pattern to catch reliably, and a guard
that misses is worse than one that costs a few milliseconds. The command test
lives in the script, which returns 0 immediately for anything that is not a
heavy leg.

COST: about 28 ms on every Bash call (Python start-up), and about 90 ms on a
call that is a heavy leg, measured on the machine this was written for. If that
is too much, the answer is a handler-level `if`, not a weaker guard.

EXIT CODES: 2 blocks a PreToolUse hook. 0 allows. Anything else is an error and
does NOT block -- so a crash can never be relied upon to refuse, which is why
the script fails open on purpose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "leg_guard.py"
# Anchored: the matcher is an UNANCHORED regex, so a bare "Bash" also matches
# "BashOutput" and any future tool whose name contains it.
MATCHER = "^Bash$"
INTERPRETER = "/usr/bin/python3"   # absolute: hooks do not inherit a login PATH
DEPLOY_DIR = Path.home() / ".claude" / "tools" / "leg-guard"
TIMEOUT_S = 10   # caps any stall; a PreToolUse hook that times out does not block


def _handler(deployed: Path) -> dict:
    return {"type": "command", "command": "%s %s" % (INTERPRETER, deployed),
            "timeout": TIMEOUT_S}


def deploy(dest_dir: Path) -> Path:
    """Copy the hook into place atomically, then read the bytes back."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "leg_guard.py"
    tmp = dest.with_suffix(".py.leg-guard-tmp")
    tmp.write_bytes(SCRIPT.read_bytes())
    tmp.replace(dest)
    if dest.read_bytes() != SCRIPT.read_bytes():
        sys.exit("refusing to continue: %s does not match %s" % (dest, SCRIPT))
    return dest


def copy_state(deployed: Path) -> str:
    if not deployed.exists():
        return "MISSING"
    return "CURRENT" if deployed.read_bytes() == SCRIPT.read_bytes() else "STALE"


def _is_ours(h: dict) -> bool:
    return "leg_guard.py" in str(h.get("command", ""))


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        sys.exit("refusing to touch %s: it is not valid JSON (%s)" % (path, e))


def install(settings: dict, deployed: Path | None = None) -> tuple[dict, str]:
    want = _handler(deployed or DEPLOY_DIR / "leg_guard.py")
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    for entry in pre:
        inner = entry.get("hooks", [])
        if any(_is_ours(h) for h in inner):
            for i, h in enumerate(inner):
                if _is_ours(h):
                    if h == want and entry.get("matcher") == MATCHER:
                        return settings, "already installed, unchanged"
                    inner[i] = want
                    entry["matcher"] = MATCHER
                    return settings, "updated in place"
    pre.append({"matcher": MATCHER, "hooks": [want]})
    return settings, "installed"


def uninstall(settings: dict) -> tuple[dict, str]:
    pre = settings.get("hooks", {}).get("PreToolUse", [])
    before = len(pre)
    kept = []
    for entry in pre:
        inner = [h for h in entry.get("hooks", []) if not _is_ours(h)]
        if inner:
            entry["hooks"] = inner
            kept.append(entry)
        elif not entry.get("hooks"):
            continue
    settings.setdefault("hooks", {})["PreToolUse"] = kept
    return settings, "removed" if len(kept) != before else "was not installed"


def describe(settings: dict) -> str:
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        for h in entry.get("hooks", []):
            if _is_ours(h):
                bad = "if" in entry
                return ("INSTALLED  matcher=%r  command=%r%s"
                        % (entry.get("matcher"), h.get("command"),
                           "\n  WARNING: `if` sits next to `matcher`; the hook will NEVER fire"
                           if bad else ""))
    return "NOT INSTALLED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--deploy-dir", default=str(DEPLOY_DIR))
    a = ap.parse_args()
    path = Path(os.path.expanduser(a.settings))
    settings = load(path)
    deploy_dir = Path(os.path.expanduser(a.deploy_dir))
    deployed = deploy_dir / "leg_guard.py"

    if a.check:
        print(describe(settings))
        print("deployed copy: %s  (%s)" % (copy_state(deployed), deployed))
        print("source:        %s" % SCRIPT)
        return 0

    if a.uninstall:
        settings, what = uninstall(settings)
    else:
        if not SCRIPT.exists():
            sys.exit("refusing to install: %s does not exist" % SCRIPT)
        deploy(deploy_dir)                  # the copy exists BEFORE anything points at it
        settings, what = install(settings, deployed)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.leg-guard-tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n")
    tmp.replace(path)                       # atomic: never a half-written file
    print("%s -> %s" % (what, path))
    print(describe(load(path)))             # read it BACK, do not trust the write
    if a.uninstall and deployed.exists():
        deployed.unlink()                   # only after nothing points at it
        print("removed %s" % deployed)
    elif not a.uninstall:
        print("deployed copy: %s  (%s)" % (copy_state(deployed), deployed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
