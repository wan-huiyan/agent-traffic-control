"""install.py: the live hook must run from a copy nothing else can move.

The first install pointed settings.json at leg_guard.py INSIDE the git checkout
under ~/Documents. Two ways that blocks every Bash call on the machine, found by
review on 2026-09-22: a missing hook file makes Python exit 2 ("can't open
file"), and 2 is exactly the code that BLOCKS a PreToolUse call. The file goes
missing if anyone checks out a branch without it (main did not have it while
the hook's pull request was open), and ~/Documents is iCloud-synced, where
files can be evicted. With no `timeout`, a stalled read could also hold a Bash
call for the 600 s default. Every other hook here lives in ~/.claude/tools/<name>/
with a 10 s timeout; this pins leg-guard to the same shape.
All tests use temp dirs and never touch the real settings or home directory.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import install as ins  # noqa: E402


def _run(*args):
    return subprocess.run([sys.executable, str(HERE / "install.py")] + list(args),
                          capture_output=True, text=True, timeout=60)


def _entry(settings):
    for e in settings["hooks"]["PreToolUse"]:
        for h in e["hooks"]:
            if "leg_guard.py" in h["command"]:
                return e, h
    raise AssertionError("no leg-guard entry")


def test_the_handler_runs_the_deployed_copy_with_a_timeout():
    d = Path(tempfile.mkdtemp())
    settings, what = ins.install({}, deployed=d / "leg_guard.py")
    e, h = _entry(settings)
    assert e["matcher"] == "^Bash$"
    assert h["command"] == "%s %s" % (ins.INTERPRETER, d / "leg_guard.py")
    assert h["timeout"] == ins.TIMEOUT_S == 10
    assert str(ins.SCRIPT.parent) not in h["command"], "must not run from the checkout"


def test_an_old_entry_pointing_into_the_checkout_is_replaced_in_place():
    d = Path(tempfile.mkdtemp())
    old = {"hooks": {"PreToolUse": [{"matcher": "^Bash$", "hooks": [
        {"type": "command",
         "command": "/usr/bin/python3 /Users/x/Documents/repo/hooks/leg-guard/leg_guard.py"}]}]}}
    settings, what = ins.install(old, deployed=d / "leg_guard.py")
    assert what == "updated in place"
    entries = [h for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]
               if "leg_guard.py" in h["command"]]
    assert len(entries) == 1 and entries[0]["timeout"] == 10
    assert "/Documents/" not in entries[0]["command"]


def test_install_deploys_before_it_points_settings_at_the_copy_and_reads_it_back():
    d = Path(tempfile.mkdtemp())
    settings_path, tools = d / "settings.json", d / "tools" / "leg-guard"
    p = _run("--settings", str(settings_path), "--deploy-dir", str(tools))
    assert p.returncode == 0, p.stderr
    deployed = tools / "leg_guard.py"
    assert deployed.read_bytes() == ins.SCRIPT.read_bytes()
    _, h = _entry(json.loads(settings_path.read_text()))
    assert h["command"].endswith(str(deployed)) and h["timeout"] == 10
    # and the deployed copy really runs as a hook: a non-leg command is allowed
    r = subprocess.run([ins.INTERPRETER if os.path.exists(ins.INTERPRETER) else sys.executable,
                        str(deployed)],
                       input=json.dumps({"tool_input": {"command": "ls"}}),
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


def test_check_reports_a_stale_or_missing_copy_rather_than_the_source_file():
    d = Path(tempfile.mkdtemp())
    settings_path, tools = d / "settings.json", d / "tools" / "leg-guard"
    assert _run("--settings", str(settings_path), "--deploy-dir", str(tools)).returncode == 0
    ok = _run("--check", "--settings", str(settings_path), "--deploy-dir", str(tools))
    assert "deployed copy: CURRENT" in ok.stdout, ok.stdout
    (tools / "leg_guard.py").write_text("# an older version\n")
    stale = _run("--check", "--settings", str(settings_path), "--deploy-dir", str(tools))
    assert "deployed copy: STALE" in stale.stdout, stale.stdout
    (tools / "leg_guard.py").unlink()
    gone = _run("--check", "--settings", str(settings_path), "--deploy-dir", str(tools))
    assert "deployed copy: MISSING" in gone.stdout, gone.stdout


def test_uninstall_removes_the_entry_before_the_copy():
    d = Path(tempfile.mkdtemp())
    settings_path, tools = d / "settings.json", d / "tools" / "leg-guard"
    assert _run("--settings", str(settings_path), "--deploy-dir", str(tools)).returncode == 0
    p = _run("--uninstall", "--settings", str(settings_path), "--deploy-dir", str(tools))
    assert p.returncode == 0, p.stderr
    s = json.loads(settings_path.read_text())
    assert not any("leg_guard.py" in h["command"]
                   for e in s["hooks"]["PreToolUse"] for h in e["hooks"])
    assert not (tools / "leg_guard.py").exists()
