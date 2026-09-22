"""leg-guard tests.

Every case names what it would have caught. A test that only asserts "exit 0"
on a healthy input proves nothing, so each allow-case is paired with a
block-case differing in exactly one thing.
"""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "leg_guard.py"

sys.path.insert(0, str(HOOK.parent))
import leg_guard as _lg


def PEER_PATTERN_MATCHES(ps_row):
    """True if this fixture would be seen as a leg but for the wrapper filter."""
    return bool(_lg.PEER_PATTERN.search(ps_row.split(None, 3)[3]))

# One real `ps` row per shape, taken from the 2026-09-22 incident.
PEER_SERIAL = "45106 1     07:41 /opt/homebrew/.../Python -m pytest prototype -q"
PEER_XDIST  = "55565 1     03:02 /opt/homebrew/.../Python -m pytest prototype -q -n 4 --dist loadfile"
WORKER      = "55570 55565 03:01 /opt/homebrew/.../Python -m pytest prototype -q -n 4 --dist loadfile"
# A REAL wrapper from the 2026-09-22 incident: the zsh -c line carries the
# full `python -m pytest <suite>` text in its argv, so it matches the peer
# pattern exactly as an interpreter would. A fixture without that text
# passes this test without ever reaching the wrapper filter.
WRAPPER     = ("73347 1     01:24 /bin/zsh -c source /Users/x/.claude/shell-snapshots/snap.sh "
               "&& eval 'cd /tmp/w && /Users/x/.venv/bin/python -m pytest prototype -q'")
UNRELATED   = "00123 1     10:00 /usr/bin/node /some/server.js"


def run(command, ps_rows, env=None):
    """Run the hook with a faked `ps` on PATH, so no real process is needed."""
    import os, tempfile, textwrap
    d = tempfile.mkdtemp()
    fake = Path(d) / "ps"
    body = "PID  PPID ELAPSED COMMAND\n" + "\n".join(ps_rows) + "\n"
    fake.write_text("#!/bin/sh\ncat <<'EOF'\n%sEOF\n" % body)
    fake.chmod(0o755)
    e = dict(os.environ)
    e["PATH"] = d + ":" + e["PATH"]
    e.update(env or {})
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True, env=e, timeout=30,
    )
    return p.returncode, p.stderr


def test_a_command_that_is_not_a_leg_is_allowed_even_with_peers_running():
    # would catch: a guard so broad it blocks `git status` while a leg runs
    code, _ = run("git status --porcelain", [PEER_SERIAL])
    assert code == 0


def test_a_leg_is_allowed_when_nothing_else_is_running():
    # the control for the block case below: same command, no peers
    code, _ = run(".venv/bin/python -m pytest prototype -q", [UNRELATED])
    assert code == 0


def test_a_leg_is_BLOCKED_when_a_peer_leg_is_running():
    # the whole point. exit 2 is what blocks; 0 or 1 would let it through
    code, err = run(".venv/bin/python -m pytest prototype -q", [PEER_SERIAL, UNRELATED])
    assert code == 2, err
    assert "BLOCKED by leg-guard" in err
    assert "45106" in err


def test_the_override_lets_it_through_and_says_so():
    code, err = run("DR_LEG_FORCE=1 .venv/bin/python -m pytest prototype -q", [PEER_SERIAL])
    assert code == 0
    assert "DR_LEG_FORCE=1 marker present" in err


def test_a_wrapper_shell_is_not_counted_as_a_leg():
    # would catch: the double-count that makes any "under N" threshold
    # unsatisfiable, and would block a session with no real peer running.
    # The fixture deliberately CONTAINS "python -m pytest prototype", so it
    # reaches the wrapper filter instead of being dropped by the peer pattern.
    assert PEER_PATTERN_MATCHES(WRAPPER), "fixture no longer exercises the filter"
    code, err = run(".venv/bin/python -m pytest prototype -q", [WRAPPER, UNRELATED])
    assert code == 0, err


def test_xdist_workers_collapse_to_one_leg():
    # would catch: reporting "5 peer legs" for one four-worker run
    code, err = run(".venv/bin/python -m pytest prototype -q", [PEER_XDIST, WORKER])
    assert code == 2
    assert err.count("55565") == 1, err
    assert "1 peer test leg" in err


def test_the_gate_receipt_runner_counts_as_a_leg():
    code, err = run("python scripts/gate_receipt.py run --out ~/x", [PEER_SERIAL])
    assert code == 2, err


def test_a_capitalised_interpreter_is_still_matched():
    # the same machine reports different counts for [p]ython and [P]ython
    code, _ = run(".venv/bin/python -m pytest server -q",
                  ["9999 1 01:00 /usr/bin/Python -m pytest server -q"])
    assert code == 2


def test_malformed_stdin_fails_OPEN_rather_than_blocking_every_bash_call():
    p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0


def test_no_stdin_at_all_fails_open():
    p = subprocess.run([sys.executable, str(HOOK)], input="",
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0


def test_a_broken_ps_fails_open_rather_than_blocking():
    # would catch: a guard that refuses everything on a machine where `ps`
    # output changed shape -- worse than no guard at all
    import os, tempfile
    d = tempfile.mkdtemp()
    fake = Path(d) / "ps"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    e = dict(os.environ); e["PATH"] = d + ":" + e["PATH"]
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "pytest prototype -q"}}),
        capture_output=True, text=True, env=e, timeout=30)
    assert p.returncode == 0, p.stderr


def test_our_own_process_chain_is_never_counted_as_a_peer(monkeypatch):
    """Would catch: the hook blocking itself.

    If the session that is ASKING is itself inside a shell whose argv carries
    the leg command, that row must not count as a peer -- otherwise the guard
    refuses every leg on a machine where nothing else is running, which is the
    worst failure available to it.
    """
    rows = [
        (4242, 1, "00:05", "/usr/bin/Python -m pytest prototype -q"),   # ours
        (4243, 4242, "00:05", "/usr/bin/Python -m pytest prototype -q"),  # our child
        (9000, 1, "10:00", "/usr/bin/node /some/server.js"),            # unrelated
    ]
    monkeypatch.setattr(_lg, "_ps_lines", lambda: rows)
    assert _lg.peer_legs({4242}) == [], "our own row was counted as a peer"
    # control: the SAME rows with a different ancestry ARE peers
    assert len(_lg.peer_legs({9999})) == 1


def test_a_peer_is_still_found_when_our_ancestry_is_unrelated():
    rows = [(5555, 1, "01:00", "/usr/bin/Python -m pytest server -q")]
    import types
    saved = _lg._ps_lines
    _lg._ps_lines = lambda: rows
    try:
        assert len(_lg.peer_legs({1234})) == 1
    finally:
        _lg._ps_lines = saved


def test_a_command_that_merely_MENTIONS_a_leg_is_not_blocked():
    """The false positive that the first live install produced.

    An edit whose heredoc carried `-m pytest prototype` as TEST DATA was
    refused, because the match was a bare substring. A guard that fires on a
    command talking about a leg -- writing a test for one, echoing it, passing
    it as JSON -- gets switched off, and then guards nothing.
    """
    mentions = [
        """python3 -c 'print("run: python -m pytest prototype -q")'""",
        """echo ".venv/bin/python -m pytest prototype -q" > /tmp/note.txt""",
        """python3 - <<'EOF'\npayload = {"command": "python -m pytest prototype -q"}\nEOF""",
        """grep -n "pytest prototype" docs/runbook.md""",
    ]
    for cmd in mentions:
        code, err = run(cmd, [PEER_SERIAL])
        assert code == 0, "blocked a command that only MENTIONS a leg:\n%s\n%s" % (cmd, err)


def test_the_real_invocation_forms_are_still_caught():
    """The control for the test above: these genuinely start a leg."""
    real = [
        ".venv/bin/python -m pytest prototype -q",
        "cd /tmp/wt && /Users/x/.venv/bin/python -m pytest server -q",
        "PYTHONPATH=. .venv/bin/python -m pytest docs -q -m 'not slow'",
        "pytest tracker -q",
        "cd /tmp/wt && python scripts/gate_receipt.py run --out ~/r",
        "git status && .venv/bin/python -m pytest stravart -q",
    ]
    for cmd in real:
        code, _ = run(cmd, [PEER_SERIAL])
        assert code == 2, "let a real leg through: %s" % cmd


def test_the_marker_works_as_a_trailing_comment_not_only_as_a_prefix():
    """The message tells people to use it as a comment, so that must work.

    The first version of the block message suggested prefixing
    `DR_LEG_FORCE=1 ` to the command, which reads as shell env syntax but is
    really a text marker -- and prefixing it to a `cd x && ...` chain would set
    an env var for `cd` alone. The message now says "anywhere", including as a
    trailing comment, and this pins that.
    """
    code, err = run(".venv/bin/python -m pytest prototype -q   # DR_LEG_FORCE=1", [PEER_SERIAL])
    assert code == 0, err
    code, err = run("cd /tmp/w && DR_LEG_FORCE=1 pytest server -q", [PEER_SERIAL])
    assert code == 0, err
