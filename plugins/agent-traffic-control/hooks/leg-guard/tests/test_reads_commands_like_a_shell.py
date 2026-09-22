"""leg-guard must read a command the way a shell does, not as flat text.

Four false blocks on 2026-09-22, all in one session, all the same defect: the
first version split the command on `|`, `;`, `&&` and newlines WITHOUT knowing
where quotes, heredocs and comments begin and end, then asked whether any piece
began with a leg invocation. So a heredoc writing a document that QUOTES the
gate commands, and a `grep` whose quoted pattern held a `|`, both read as
starting a leg. Every handoff in the repo that motivated this hook quotes the
gate commands verbatim, because its house rules tell sessions to -- so the
guard fired on exactly the documents it was installed to protect.

Every allow-case here is paired with a block-case differing in one thing, so a
guard that simply stops blocking cannot pass this file.
"""
import os
import time

from test_leg_guard import PEER_SERIAL, run, _lg

LEG = ".venv/bin/python -m pytest prototype -q"
RECEIPT = ".venv/bin/python scripts/gate_receipt.py run --out ~/.receipts/x --fresh"


def blocks(cmd):
    return _lg.starts_a_leg(cmd)


# ---------------------------------------------------------------------------
# The four real misfires, run through the hook exactly as Claude Code runs it
# ---------------------------------------------------------------------------

def test_incident_1_a_heredoc_writing_a_prompt_that_quotes_the_gates():
    cmd = (
        'W=/Users/x/board; cat > "$W/docs/handoffs/prompt.md" <<\'MARKDOWN\'\n'
        "# Register her grades\n"
        "Run the gates:\n"
        "```sh\n"
        ".venv/bin/python -m pytest prototype -q\n"
        '.venv/bin/python -m pytest docs -q -m "not slow"\n'
        "```\n"
        "MARKDOWN\n"
        'echo "written: $(wc -c < "$W/docs/handoffs/prompt.md") bytes"'
    )
    code, err = run(cmd, [PEER_SERIAL])
    assert code == 0, "blocked a heredoc that only WRITES the gate commands:\n" + err


def test_incident_2_a_pr_body_heredoc_quoting_the_receipt_runner():
    cmd = (
        "cat >> /tmp/body.md <<'EOF'\n"
        + RECEIPT + "\n"
        ".venv/bin/python scripts/gate_receipt.py publish ~/.receipts/x\n"
        "EOF\n"
        "gh pr edit 3131 --body-file /tmp/body.md > /dev/null 2>&1"
    )
    code, err = run(cmd, [PEER_SERIAL])
    assert code == 0, "blocked a pull-request body edit:\n" + err


def test_incident_3_a_quoted_pipe_inside_a_grep_pattern():
    cmd = ("ps -axo etime,command | grep -E 'Python -m pytest|gate_receipt.py run' "
           "| grep -v grep | sort | uniq -c")
    code, err = run(cmd, [PEER_SERIAL])
    assert code == 0, "blocked a read-only process listing:\n" + err


def test_incident_4_a_memory_note_describing_incident_3():
    cmd = (
        "cat >> ~/.claude/memory/running-the-legs.md <<'NOTE'\n"
        "**leg-guard does not respect quoting.** It split\n"
        "`ps | grep -E 'Python -m pytest|gate_receipt.py run'` on the quoted `|`.\n"
        "gate_receipt.py run --out ~/r\n"
        "NOTE"
    )
    code, err = run(cmd, [PEER_SERIAL])
    assert code == 0, "blocked the note describing the last false block:\n" + err


def test_the_paired_control_a_real_leg_after_the_same_heredoc_is_still_blocked():
    """Incident 1's shape with ONE change: a real leg after the heredoc ends."""
    cmd = ("cat > /tmp/prompt.md <<'MARKDOWN'\n" + LEG + "\nMARKDOWN\n" + LEG)
    code, _ = run(cmd, [PEER_SERIAL])
    assert code == 2, "a leg AFTER a heredoc closes is a real leg and must block"


# ---------------------------------------------------------------------------
# Text that only MENTIONS a leg: quotes, heredocs, comments, here-strings
# ---------------------------------------------------------------------------

def test_separators_inside_quotes_do_not_start_a_command():
    for cmd in [
        'git commit -m "tried %s; then docs"' % LEG,
        "echo 'x && %s'" % LEG,
        "jq -r '.[] | \"%s\"' data.json" % LEG,
        'echo "a || %s" > note.txt' % LEG,
        "printf '%%s\\n' 'first;%s'" % LEG,
    ]:
        assert not blocks(cmd), cmd


def test_heredoc_bodies_are_data_in_every_delimiter_form():
    for cmd in [
        "cat <<EOF\n%s\nEOF" % LEG,                   # unquoted delimiter
        "cat <<'EOF'\n%s\nEOF" % LEG,                 # single-quoted
        'cat <<"EOF"\n%s\nEOF' % LEG,                 # double-quoted
        "cat <<-EOF\n\t%s\n\tEOF" % LEG,              # tab-stripped
        "cat <<EOF > out.md\n%s\nEOF\necho done" % LEG,
        "python3 - <<'PY'\nimport os\nos.system('echo %s')\nPY" % LEG,
    ]:
        assert not blocks(cmd), cmd


def test_the_git_commit_idiom_with_an_unbalanced_paren_in_the_heredoc():
    """The commit-message shape Claude Code uses on every commit.

    The heredoc sits inside `$( … )` inside double quotes, and its body has a
    `)` of its own ("1) first"). A paren counter ends the substitution there
    and turns the rest of the message into commands.
    """
    cmd = (
        'git commit -m "$(cat <<\'EOF\'\n'
        "Fix the guard\n\n"
        "Run: %s (then docs)\n"
        "1) first\n"
        "EOF\n"
        ')"' % LEG
    )
    assert not blocks(cmd)


def test_comments_and_here_strings_are_not_commands():
    for cmd in [
        "ls\n# %s\necho done" % LEG,
        "echo hi   # %s" % LEG,
        'grep -c pytest <<< "%s"' % LEG,
    ]:
        assert not blocks(cmd), cmd


# ---------------------------------------------------------------------------
# The real invocation forms, including ones a flat text match cannot see
# ---------------------------------------------------------------------------

def test_real_legs_on_their_own_lines_and_after_separators():
    for cmd in [
        "cd /tmp/w\n%s" % LEG,
        "echo \"a && b\" && %s" % LEG,
        "git status; %s" % LEG,
        "true || %s" % LEG,
        ".venv/bin/python -m pytest \\\n  prototype -q",       # line continuation
        "%s > /tmp/log 2>&1" % LEG,
        "2>/dev/null %s" % LEG,
        "if %s; then echo ok; fi" % LEG,
        "for i in 1; do %s; done" % LEG,
    ]:
        assert blocks(cmd), cmd


def test_legs_inside_substitutions_subshells_and_groups():
    for cmd in [
        "out=$(%s 2>&1)" % LEG,
        "out=`pytest tracker -q`",
        'echo "result: $(%s)"' % LEG,
        "( cd /tmp/w && %s )" % LEG,
        "{ %s; }" % LEG,
        "diff <(%s) expected.txt" % LEG,
    ]:
        assert blocks(cmd), cmd


def test_legs_behind_wrapper_commands():
    """How sessions actually start legs: timed, kept awake, niced, bounded."""
    for cmd in [
        "time %s" % LEG,
        "caffeinate -i %s" % LEG,
        "nice -n 10 pytest server -q",
        "timeout 600 %s" % LEG,
        "env PYTHONHASHSEED=0 %s" % LEG,
        "nohup %s > log 2>&1 &" % LEG,
        ".venv/bin/python -u -X importtime -m pytest prototype -q",
    ]:
        assert blocks(cmd), cmd


def test_strings_a_shell_will_execute_are_read_as_commands():
    for cmd in [
        'bash -c "%s"' % LEG,
        "zsh -lc 'cd /tmp/w && pytest server -q'",
        'eval "%s"' % LEG,
        "bash <<'EOF'\n%s\nEOF" % LEG,                    # heredoc fed to a shell
        "cat <<EOF\n$(%s)\nEOF" % LEG,                    # unquoted heredoc expands $( )
    ]:
        assert blocks(cmd), cmd


def test_the_receipt_runner_every_way_it_is_started():
    for cmd in [
        RECEIPT,
        "cd /tmp/w && python scripts/gate_receipt.py run --out ~/r",
        "scripts/gate_receipt.py run --out ~/r",
    ]:
        assert blocks(cmd), cmd
    for cmd in [
        ".venv/bin/python scripts/gate_receipt.py publish ~/r",
        ".venv/bin/python scripts/gate_receipt.py check ~/r",
        "grep -n 'gate_receipt.py run' CLAUDE.md",
    ]:
        assert not blocks(cmd), cmd


def test_a_pytest_run_naming_no_heavy_suite_is_not_a_leg():
    """Unchanged from the first version: only the five heavy suites count."""
    for cmd in [
        "python3 -m pytest plugins/x/hooks/leg-guard/tests -q",
        "pytest tests/test_one.py -q",
    ]:
        assert not blocks(cmd), cmd


# ---------------------------------------------------------------------------
# It runs on every Bash call: it must never crash, hang or refuse wrongly
# ---------------------------------------------------------------------------

def test_an_unterminated_quote_starts_nothing():
    """A shell refuses to run this at all, so there is no leg to block."""
    assert not blocks("echo 'unterminated %s" % LEG)
    assert not blocks('echo "unterminated $(%s' % LEG)


def test_an_unterminated_heredoc_still_reads_the_command_before_it():
    assert not blocks("cat <<EOF\n%s" % LEG)
    assert blocks("%s; cat <<EOF\nno end" % LEG)


def test_a_huge_heredoc_is_read_quickly():
    body = "\n".join([LEG] * 40000)                       # about 1.6 MB
    cmd = "cat > big.md <<'EOF'\n%s\nEOF" % body
    t = time.monotonic()
    assert not blocks(cmd)
    assert time.monotonic() - t < 3.0


def test_pathological_nesting_fails_open_rather_than_crashing_the_hook():
    cmd = "$(" * 3000 + LEG + ")" * 3000
    t = time.monotonic()
    code, err = run(cmd, [PEER_SERIAL])
    assert code == 0, err                                 # fail OPEN, never 1 or a hang
    # ...and by a deliberate answer, not by crashing into the top-level catch,
    # which also exits 0 and would otherwise look identical to this test.
    assert "internal error" not in err, err
    assert time.monotonic() - t < 10.0


def test_a_command_that_mentions_neither_word_skips_the_parser_entirely(monkeypatch):
    """The fast path: most Bash calls must cost nothing."""
    def boom(*a, **k):
        raise AssertionError("the parser ran on a command that cannot be a leg")
    monkeypatch.setattr(_lg, "command_argvs", boom)
    assert not blocks("git status && ls -la | wc -l")


def test_the_hook_is_tested_on_the_interpreter_the_installer_writes():
    """The end-to-end tests must run the hook where settings.json runs it.

    On this laptop pytest runs on 3.14 and the installed hook on 3.9. A hook that
    only works on the newer one would pass every test and crash live -- and a
    crash fails OPEN, so the guard would switch itself off unnoticed.
    """
    import test_leg_guard as h
    if os.path.exists(h._install.INTERPRETER):
        assert h.PY == h._install.INTERPRETER
