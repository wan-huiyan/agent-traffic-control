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
