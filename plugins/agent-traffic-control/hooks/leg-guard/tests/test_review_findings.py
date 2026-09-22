"""Findings from the three-reviewer pass of 2026-09-22, each pinned by a test.

Every test here failed against fb7b7f7 (the first version of the shell reader)
before the fix it names.
"""
import json
import os
import subprocess
import tempfile
import time

from test_leg_guard import PEER_SERIAL, PY, HOOK, run, _lg

LEG = ".venv/bin/python -m pytest prototype -q"


def _eval_nest(inner, k):
    """The reviewer's exact shape: S(k+1) = eval $(eval S(k)). Unquoted, two
    evals per level -- the text of each level is read once per enclosing level,
    so the work TRIPLED per level: k=13 (182 chars) took 21.6 s and 776 MB."""
    s = inner
    for _ in range(k):
        s = "eval $(eval " + s + ")"
    return s


def _here_nest(inner, k):
    """A heredoc fed to bash whose body holds $( another heredoc fed to bash ).
    Doubled per level: 427 characters took 6.5 s."""
    s = inner
    for j in range(k, 0, -1):
        s = "bash <<E%d\necho $(%s\n)\nE%d" % (j, s, j)
    return s


def test_nested_eval_substitutions_stay_fast_and_still_find_the_leg():
    for inner, expect in [("true # pytest", False), (LEG, True)]:
        cmd = _eval_nest(inner, 12)
        t = time.monotonic()
        assert _lg.starts_a_leg(cmd) is expect, cmd
        took = time.monotonic() - t
        assert took < 1.0, "%.2fs for %d chars" % (took, len(cmd))


def test_nested_heredocs_fed_to_a_shell_stay_fast_and_still_find_the_leg():
    for inner, expect in [("true # pytest", False), (LEG, True)]:
        cmd = _here_nest(inner, 18)
        t = time.monotonic()
        assert _lg.starts_a_leg(cmd) is expect, cmd
        took = time.monotonic() - t
        assert took < 1.0, "%.2fs for %d chars" % (took, len(cmd))


def test_a_command_over_the_size_cap_is_answered_without_being_read():
    """A multi-megabyte command took 4-9 s and 600+ MB to read. Past the cap it
    starts nothing: the guard errs quiet rather than stall every such call."""
    cmd = "cat > big.md <<'EOF'\n" + ("x" * 2000000) + "\nEOF\n" + LEG
    t = time.monotonic()
    assert not _lg.starts_a_leg(cmd)
    assert time.monotonic() - t < 0.5


def test_the_py_test_spelling_is_seen():
    """`_is_leg` accepted `py.test` but the fast path, which looked only for the
    word `pytest`, never let such a command reach it."""
    for cmd in ["py.test prototype -q", "caffeinate -i py.test server -q",
                "time py.test docs -q"]:
        assert _lg.starts_a_leg(cmd), cmd
    assert not _lg.starts_a_leg("py.test tests/test_one.py -q")


def test_sh_dash_s_reads_its_heredoc_even_with_positional_arguments():
    assert _lg.starts_a_leg("sh -s -- arg1 arg2 <<'EOF'\n%s\nEOF" % LEG)
    assert _lg.starts_a_leg("bash -s <<'EOF'\n%s\nEOF" % LEG)
    assert not _lg.starts_a_leg("bash script.sh <<'EOF'\n%s\nEOF" % LEG)   # a script file reads its own


def test_crlf_line_endings_are_read_correctly_not_by_two_bugs_cancelling():
    assert not _lg.starts_a_leg("cat <<'EOF'\r\n%s\r\nEOF\r\necho done\r\n" % LEG)
    assert _lg.starts_a_leg("cat <<'EOF'\r\ndata\r\nEOF\r\n%s\r\n" % LEG)
    assert _lg.command_argvs("echo hi\r\n") == [["echo", "hi"]]    # no stray \r in a word


def test_payloads_that_are_not_the_expected_shape_are_allowed_quietly():
    """These went through the top-level 'internal error' handler: allowed, but
    printing an error on stderr. They are not errors in the hook."""
    for payload in [None, 5, [1, 2], "str",
                    {"tool_input": [1]},
                    {"tool_input": {"command": 5}},
                    {"tool_input": {"command": ["pytest", "prototype"]}},
                    {"tool_input": {"command": {"pytest": 1}}}]:
        p = subprocess.run([PY, str(HOOK)], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, (payload, p.stderr)
        assert "internal error" not in p.stderr, (payload, p.stderr)


def test_a_ps_line_with_non_utf8_bytes_does_not_switch_the_guard_off():
    """One undecodable byte anywhere in `ps` output raised UnicodeDecodeError,
    the top-level handler allowed the command, and the guard was silently off."""
    d = tempfile.mkdtemp()
    fake = os.path.join(d, "ps")
    with open(fake, "wb") as f:
        f.write(b"#!/bin/sh\nprintf 'PID  PPID ELAPSED COMMAND\\n'\n"
                b"printf '00999 1     01:00 /usr/bin/odd \\377\\376name\\n'\n"
                b"printf '%s\\n'\n" % PEER_SERIAL.encode())
    os.chmod(fake, 0o755)
    env = dict(os.environ)
    env["PATH"] = d + ":" + env["PATH"]
    p = subprocess.run([PY, str(HOOK)],
                       input=json.dumps({"tool_name": "Bash", "tool_input": {"command": LEG}}),
                       capture_output=True, text=True, env=env, timeout=30)
    assert p.returncode == 2, p.stderr
