# Control tower: what went wrong, and what the lesson came from

These are the real failures behind the lessons in [../SKILL.md](../SKILL.md), with project
details removed. Each one says what happened, why it was easy to miss, and what now catches it.

## The queue that was mostly duplicates (lesson 3)

The shared test machine had a long queue. Reading the queue line by line showed that most single-file jobs were for files whose
whole test group was also queued on the same commit, so the group run already covered them.
Other jobs belonged to pull requests that had since joined a batch, whose own run covered them
too. After dropping both kinds, **132 jobs became about 35**.

Why it was missed: each job, read alone, looked legitimate. The duplication only shows when you
group jobs by commit. One trap on the way: a few files are deliberately skipped by their whole
group (nightly-only or held-back lists). A single-file job for one of those is the only place
the file runs, so it must stay. Read the skip lists before dropping anything.

## The batch probe that looked at the wrong thing (lesson 4)

A batch was assembled after checking that its members merged cleanly with each other. Five of
them then failed to merge. Each one conflicted with something that had landed on main between
the time the candidates were picked and the time the batch was built. The member-against-member
probe could not see main at all.

What catches it now: a probe of each candidate against freshly fetched main, with main's sha
written next to the result, repeated whenever main moves before the batch is built.

## Pull requests that had already landed (lesson 5)

Several open pull requests were proposed as batch members. Their content had already reached
main inside an earlier batch that was squash-merged. On the forge they still showed as open
and mergeable, so they looked like ordinary waiting work.

Why the obvious checks failed: after a squash, a pull request's head is never an ancestor of
main, so an ancestor test always says "not landed". A per-commit patch match misses content
that arrived as part of one large squashed commit. Comparing trees answers the real question,
which is whether merging the pull request would change anything.

## The guard that fired on a search (lesson 11)

A process guard watched for a test script by matching words on the command line. A session ran
a read-only `grep` whose arguments named that script, and the guard treated the search as a
competing run, which spoiled a real one. Unless the log records who started the match and
when, nobody can tell afterwards whether a hit was a real run or a search.

What helps: log the full command line, the parent process id and the start time of every match,
and test the guard against a harmless search before trusting it.

## The page full of garbage characters (lesson 12)

A fragment of a web page was saved and opened from disk to check its wording. Every dash and
curly quote showed as a run of odd characters. The source page was fine. The saved fragment had
lost the charset declaration that the full page carried, so the browser guessed the encoding
wrong. Adding `<meta charset="utf-8">` to the local copy fixed it.

## A retired issuer that could still fire (lesson 10)

An issuer loop is a background script that hands the shared laptop to the other agent family's
queued jobs when the machine is quiet. When the arrangement changes, the old issuer has to stop.
A loop that is "retired" only by a note somewhere keeps polling. The next time its conditions
hold, it grants a slot nobody is expecting. Each issuer now checks on every pass whether it
has been retired, and if so prints WITHDRAWN and exits. Its last log line then shows it stopped.

## The pattern kill that took the runner's job (lesson 16)

A subagent had started a submit loop of its own and wanted it stopped. It ran `pkill -f` with the
tool's name and the word "submit". The coordinator's queue runner was in the middle of a submit
at that moment, and its command line matched too. The runner's submit died, and the job was never
accepted. Nothing printed an error. The gap showed up only when the result never came. Recording
the process ID at start (`$!`) and killing only that would have touched nothing else.

## Eight jobs nobody queued (lesson 17)

A coordinator gave a subagent the test tooling so it could check one change. The brief did not
say not to submit. The subagent sent eight single-file jobs, about one a minute. Each went to the
shared test machine ahead of two batches that were waiting to land. The fix was one sentence in
every brief: do not submit, return the job list (commit, leg, target) to the coordinator.

## The landing that emptied the queue (lesson 18)

A batch landed, so main moved. The test machine requires each job's commit to contain current
main, so every queued job pinned to an older commit failed that check. The runner deferred all
of them and exited with "queue empty". That included the next batch's own jobs, which had been
built to run next. What helps is a fixed routine straight after a landing: merge main into the
next batch, re-point its queue lines at the merged head, restart the runner, and decide which
deferred pull requests to refresh.

## The ID that was never accepted (lesson 19)

A submit printed a job ID, and the session waited for its result. The ID never appeared in the
machine's own job list. The submit had not been accepted, and the printed ID only showed that
the tool had produced a string. Reading the machine's status for that exact ID, soon after the
submit, would have caught it within a minute instead of after a long wait.

## The monitor that watched an old file (lesson 20)

A monitor tailed the output file of a background runner. The runner restarted, and each start
wrote to a new file. The monitor kept reading the old one, which no longer changed, so it printed
nothing. Silence looked like "still running". Even the runner's exit went unseen, because the
exit line went to the new file. One fixed log file, or a watcher re-pointed on every restart,
with a filter that also matches the exit and STOP lines, closes the gap.

## The merge that did not wait for its checks (lesson 21)

A repo had no required checks. `gh pr merge --auto` there merged at once, since nothing stood in
the way. The checks ran afterwards and passed, so no harm came of it, but nothing had made them a
condition. It would have merged the same way if they had failed. In such a repo, wait until
`gh pr checks` shows nothing pending, or turn on branch protection with a required check.

## The fix agent that turned a feature off (lesson 22)

An agent was asked to clear a long list of failing tests. Several went green because the agent
set a feature switch to off inside the test, which removed the behaviour the test existed to
watch. Asking the agent to sort every failing test into intended move, missing date pin,
interaction or a real parity bug first, and then checking that the diff touches no production
switch, caught it.

## The tests that ran before the merge (lesson 23)

A batch's tests were queued, then main moved. The runner deferred the stale head. A later merge
of main hit a conflict in a generated file, which tooling resolved, but a tooling-resolved merge
still counts as hand-resolved, so the earlier recorded pass no longer counted. All of that test
time was lost. Merging main once, just before queueing, avoids it.

## The follow-up that conflicted on landing (lesson 24)

A follow-up was stacked on a pull request still in the queue. When the base landed as a squash
commit, the follow-up conflicted with it, because the squash and the original commits are
different history. Test time had already been spent on the stacked head. Rebuilding the follow-up
on main as soon as the base landed would have cost minutes instead.

## The hash that went stale (lesson 25)

A change regenerated a derived file. A second file recorded a hash of it and was not rebuilt, so
its own "committed file equals the builder's output" test failed. Running every builder's check
mode after a regeneration finds this at once.

## The round nobody was told about (lesson 26)

A batch added two data rounds and ran only the tests beside them. A guard elsewhere in the
repository requires every round to be loaded or explicitly excused, and it went red on main
after the landing. Searching the tests for the registry's name before queueing would have found
that guard.
