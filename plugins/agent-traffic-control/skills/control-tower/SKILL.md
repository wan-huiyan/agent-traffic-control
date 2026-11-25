---
name: control-tower
listing_tier: short
description: Use when a session is told it is the coordinator of a pull request queue, a shared test machine, a shared laptop and peer agent sessions. Covers batching, duplicate test jobs, the census before a ready flip, turn-taking.
author: Claude Code
version: 1.1.0
date: 2026-11-25
---
# Control tower: running the queue as the coordinator

## When to use

You have been told that you are the coordinator. That usually means you own some or all of:

- the queue of open pull requests, and the order and batches they land in;
- a shared test machine that runs jobs one at a time;
- a laptop that you share with other sessions, possibly from another agent family (for example a Codex coordinator);
- a set of peer sessions that do the hands-on work and report back to you.

Your job is to keep all of that moving without wasting test time, without landing something nobody checked, and without leaving the owner guessing what state things are in. You dispatch the hands-on work; you spend your own effort on the queue.

Related skills, linked rather than repeated here:

- `research-lane-coordinator` splits the work between a research lead and a separate queue coordinator. This skill is the queue coordinator's side.
- `gh-issue-claim-coordination` for claiming work so two peers do not pick up the same thing.
- `git-worktree` for giving each peer its own checkout.
- `pr-conflict-from-mid-flight-merges` for a pull request that went stale while it sat open.
- `stacked-pr-review-per-base-diff-and-attach` for reviewing a stack of dependent pull requests.
- `merge-queue-thrash-stop-inflow-and-open-prs-as-drafts` for a queue where nothing lands and nothing is red.

Each lesson below is the rule, then why, then how to check it. The war stories behind them are in [references/pitfalls.md](references/pitfalls.md).

## The shared test machine

### 1. The serial test machine is the bottleneck, and batching is the lever

**Rule.** If the shared test machine runs one job at a time, the time to empty the queue is the number of jobs queued times the minutes each job takes. Cut the number of jobs, mostly by batching many small pull requests into one run. A faster laptop does not help.

**Why.** Every other step waits on the test result, so the queue drains no faster than the machine does.

**How to check.** Count what is queued and multiply by the median job time. Then compare how many pull requests are opened per day with how many merge per day:

```bash
since=$(date -u -v-7d +%F 2>/dev/null || date -u -d '7 days ago' +%F)
gh pr list --state all    --search "created:>=$since" --limit 500 --json number --jq length
gh pr list --state merged --search "merged:>=$since"  --limit 500 --json number --jq length
```

If more open than merge, the queue grows no matter how hard anyone works. Say so to the owner with both numbers.

### 2. One queue file, one lock, one runner process

**Rule.** The shared test machine is fed from one queue file, guarded by one lock, by one runner process. Peers never submit jobs themselves; they ask the coordinator. Moving a pull request to a new head commit is one tool call that rewrites all of that pull request's queue lines at once.

**Why.** Two submitters race each other, double-book the machine and leave jobs pinned to commits that no longer exist.

**How to check.** Exactly one runner process is alive (search for it carefully: see `waiter-pgrep-matches-its-own-command-line`). Every write to the queue file takes the lock (`flock` or the platform equivalent). Rewriting a pull request's lines leaves no line naming its old head:

```bash
grep -c "<old head sha>" <queue file>   # expect 0 after the rewrite
```

A loop that opened the queue file once may never see an in-place edit. Read `running-job-queue-ignores-in-place-edits` before you edit a live queue. For a shared list that several writers append to, `shared-mutable-index-rmw-race-use-marker-blob-per-item` shows why one marker per item beats one list that everybody rewrites.

### 3. Drop duplicate jobs before they run

**Rule.** A single-file test job is redundant when the whole test group it belongs to runs on the same commit. Drop it, unless the file is one the whole group deliberately skips (a nightly-only list, a held-back list). Also park the per-pull-request jobs of any pull request that has joined a batch: the batch's own run covers them.

**Why.** Duplicates cost the same machine time as real work and push everything behind them later. In one real queue this cut 132 jobs to about 35.

**How to check.** For each single-file job, ask two questions. Is there a whole-group job queued on the same commit? Is the file absent from every skip list that group reads? Drop the job only when the answers are yes and yes. Count the queue before and after and keep both numbers.

### 19. A job ID is not proof the job was accepted

**Rule.** After a submit, read the machine's own status for that ID. Treat "the tool printed an ID" as unknown until the machine lists it.

**Why.** One submit printed an ID that never appeared in the machine's job list. Everyone waited for a result that could never arrive.

**How to check.** Ask the machine about that exact ID (use your tool's status or list command) and look for the ID in its output. If it is not there within a minute, resubmit once and say so.

## Building a batch

### 4. Probe each candidate against current main, not only against the other members

**Rule.** Before a pull request joins a batch, fetch, then check that it merges cleanly into the current main:

```bash
git fetch origin
git merge-tree --write-tree --name-only origin/main <candidate head>
echo "exit=$?"   # 0 = merges cleanly; 1 = conflicts, and the file names are listed
```

**Why.** A probe of members against each other cannot see something that landed on main a minute ago. One member-against-member probe missed five pull requests that each conflicted with work that had just landed.

**How to check.** Every member has a clean probe against the main commit you are about to build on. Write that commit's sha next to the result: the result goes stale when main moves. A conflicted pull request starts no test run at all (`conflicted-pr-starts-no-ci-run-push-resolution-first`).

### 5. Check whether a pull request's content already landed

**Rule.** Before batching a pull request, check whether its content already reached main inside an earlier batch. If it did, close it with a comment that names where the content landed. Do not batch it.

**Why.** Such pull requests stay open on the forge and look exactly like batchable work. Asking "is the head an ancestor of main?" fails after a squash merge. A squash rewrites every commit, so that answer is always no. `git cherry` matches one commit at a time, so it misses content that landed inside a squashed batch.

**How to check.** Compare trees, not commit history:

```bash
merged=$(git merge-tree --write-tree origin/main <head> | head -1)
[ "$merged" = "$(git rev-parse 'origin/main^{tree}')" ] && echo "adds nothing: already landed"
```

If merging the pull request into main gives main's own tree, it adds nothing. A batch commit's subject naming a member is not evidence that the member landed (`batch-merge-subject-is-not-evidence-a-member-landed`).

### 6. Stack batches only one deep

**Rule.** Build batch N+1 on top of batch N's head. Test it while N is in its final run. When N lands as a squash commit, merge main into N+1 with a tool that keeps N+1's side of any conflict. Use that tool only after proving the result is byte-identical to N+1's tree. A test receipt (the saved record that a given tree passed) names a tree, not a commit. So the receipt still counts and nothing runs again.

**Why.** Stacking lets the next batch be tested while the front one finishes. Going deeper than one multiplies the rework when the front batch changes.

**How to check.** Both of these must hold before you take N+1's side:

```bash
# 1. main moved by exactly batch N: main's tree is N's final tree
[ "$(git rev-parse 'origin/main^{tree}')" = "$(git rev-parse '<N final head>^{tree}')" ] && echo "main is exactly N"
# 2. after the merge, the tree is unchanged
[ "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse '<N+1 head before the merge>^{tree}')" ] && echo "tree unchanged"
```

If the first check fails, something else landed too. Keeping N+1's side could silently drop it, so do a normal merge and test again. Deleting N's branch can auto-close N+1's pull request if N+1 was opened against N's branch: see `stacked-pr-base-branch-deletion-auto-closes-dependent`.

## Landing

### 7. Take a census before every ready flip

**Rule.** Before you mark anything ready to land, list every open pull request. Record each one as "member" or "out: <reason>". "It conflicts" is not a reason. Name who resolves the conflict, where, and by when.

**Why.** Without a written census, pull requests quietly fall out of every batch and sit for days. A reason with no owner is a reason nobody acts on.

**How to check.** The census has one line per open pull request:

```bash
gh pr list --state open --limit 500 --json number --jq length   # must equal the census line count
```

Every "out" line names a person or session, a place (branch or worktree) and a time.

### 8. A front-of-queue review by a fresh agent, on the tree that would land

**Rule.** Once a pull request or batch is next to land, send a fresh agent to review it on the merged tree that would actually land. Give it the diff and the brief, not the author's conclusions.

**Why.** An agent given the author's conclusions tends to agree with them. A review of an earlier tree does not cover what main has added since.

**How to check.** Give the reviewer the merged commit's sha and confirm its report names that sha. Ask it to check whether the change ships a fresh instance of the defect it repairs. If its fixes touch only the pull request body, the tree is unchanged and so is the receipt. Confirm it:

```bash
git rev-parse 'HEAD^{tree}'   # same value before and after the review's fixes
```

### 18. Landing a batch moves main, and that can empty the queue

**Rule.** Straight after each landing, do four things for the next batch. Merge main into it with the tree-preserving merge from lesson 6. Re-point its queue lines at the merged head. Restart the queue runner. Then decide which deferred pull requests to refresh.

**Why.** The test machine requires every job's commit to contain current main. After a landing, each queued job pinned to an older commit fails that check. The runner defers them all and exits with "queue empty", and that includes the next batch's own jobs.

**How to check.** After the landing, read the runner's last lines. If it says "queue empty", count the deferred jobs. Then confirm no queue line still names a commit that lacks main:

```bash
git merge-base --is-ancestor origin/main <job commit> || echo "stale: <job commit>"
```

### 21. A repo with no required checks merges before its checks finish

**Rule.** Before you merge in a repo that has no required checks, wait until `gh pr checks <n>` shows nothing pending. Or turn on branch protection with a required check, so the wait is enforced.

**Why.** `gh pr merge --auto` on such a repo merges at once, because nothing is required. The checks ran and passed afterwards, but nothing had made them a condition of the merge.

**How to check.**

```bash
gh pr checks <n>   # no line may say pending, and none may say fail
gh api repos/<owner>/<repo>/branches/main/protection --jq '.required_status_checks.contexts'   # empty or an error means nothing is required
```

## The shared laptop

### 9. Take turns on the laptop, in writing

**Rule.** On a laptop shared with another agent family, keep hold files that say who has the slot now. Keep a written, ordered list of who goes next. When a session finishes, send a "SLOT OPEN" message to the next one on the list. Before starting anything heavy, check free memory and load, both of them. Never kill another session's run to make room.

**Why.** Load can look fine while memory runs out, and a run killed for memory often leaves no error at all (`parallel-gate-legs-killed-for-memory-count-cannot-see-ram`). Without a written order, two sessions both believe it is their turn.

**How to check.**

```bash
uptime                                   # load
memory_pressure | tail -1                # macOS: free memory percentage
free -m                                  # Linux equivalent
ls -l <hold file directory>              # who holds the slot, and since when
```

When you lend the machine to a peer through a hold file and a text grant, read `peer-window-grant-copy-the-parser-and-stay-quiet-while-live`.

### 10. Issuer loops grant only on stated conditions, and say WITHDRAWN when retired

**Rule.** A background loop that grants the other family's queued jobs a turn should grant only when stated conditions hold: idle seconds, free memory percentage, free disk. Each issuer checks on every pass whether it has been retired. If it has, it prints WITHDRAWN and exits.

**Why.** A retired issuer that keeps running can grant a slot late, to a session that no longer expects one, while someone else is using the machine.

**How to check.** Retire one issuer on purpose and watch its log. It must print WITHDRAWN and stop within one pass. A loop that keeps polling after retirement is a defect. Also check that the conditions are printed with every grant, so a grant can be explained afterwards.

### 11. Process guards must not catch read-only commands

**Rule.** A guard that matches words on a process's command line will also catch read-only commands, such as a `grep` that names the watched script, and that spoils a run. Guards should log the command line, the parent process id and the start time of every match.

**Why.** Without those three fields you cannot tell whether a hit was a real run or a search that happened to mention it.

**How to check.** Run a harmless `grep <watched script name> /dev/null` while the guard is active. If the guard fires, it needs a narrower match. Read the guard's log for the parent process id and start time of the hit. See `waiter-pgrep-matches-its-own-command-line` for the same trap in wait loops.

### 16. Never kill processes by a name pattern

**Rule.** On a shared machine, stop only the process IDs you started. Record the ID when you start something (`$!` in a shell, or the ID your tool prints) and kill that. Never run `pkill -f` or `killall` with a name or a phrase from a command line.

**Why.** A name pattern matches every process that looks alike, including other sessions' work. A subagent stopped its own submit loop with a pattern that also matched the queue runner's submit that was in flight. That job was silently never accepted.

**How to check.** Before any kill, list what the pattern would hit, and compare it with the IDs you recorded:

```bash
pgrep -fl "<pattern>"    # every hit that is not in your recorded list is someone else's
kill <pid you recorded>
```

### 20. A watcher goes quiet when the process it watches restarts

**Rule.** Have a long-running tool log to one fixed file. If it must log to a new file on each start, re-point the watcher on every restart. Make the watcher's filter match the exit and STOP lines as well as the progress lines.

**Why.** A monitor tailed a background runner's output file. Each restart wrote to a new file, so the monitor saw nothing, and silence looked like "still running".

**How to check.** Restart the runner on purpose and confirm the watcher still reports. Then stop it and confirm the watcher reports the stop:

```bash
ls -lt <log directory> | head -3   # the newest file should be the one the watcher reads
```

### 12. Local copies of web-page fragments need a charset line

**Rule.** When you save a fragment of a web page and open it locally (`file://`), add `<meta charset="utf-8">` near the top of the copy.

**Why.** Without it the browser may guess the wrong encoding. Dashes and curly quotes then show as garbage characters (mojibake), and the reader thinks the page is broken.

**How to check.**

```bash
head -c 1024 <page.html> | grep -i 'charset="\?utf-8'
```

A `file://` link can also show another worktree's copy rather than main's: see `multi-worktree-file-url-stale-content`.

## Agents and their reports

### 13. Say the model tier and the agent count before any fan-out

**Rule.** Before launching several agents, say in one line the model tier, the effort, how many agents (or the ceiling) and what they are for. Write `model:` into every agent call. Use the cheap tier for anything with a right answer in the tree.

**Why.** An omitted `model:` silently inherits the launching session's tier, which is usually the most expensive one.

**How to check.** Every agent call in the launch has a `model:` field. The announced count matches what was launched. See `fan-out-cost-control`. Isolation is set by a parameter, not by asking in the prompt: see `pre-dispatch-agent-isolation-parameter-not-prompt`.

### 14. End every coordinator turn with a status tally

**Rule.** End each turn with a short tally: one line per workstream (what it is, where it stands, what is next). Add a "Waiting on you" list of the things only the owner can do.

**Why.** The owner reads the tally to decide what to do next. Without it they have to piece the state together from the scrollback.

**How to check.** Every workstream started this session has a line, including finished and parked ones. Every item waiting on the owner says what they need to do in a few plain words.

### 15. A peer's report is a claim; ask for the tool's own output

**Rule.** Before you tell the owner something is done, check the diff, the merge state or the queue result yourself. A check is worthless when skipping the work prints the same thing as doing it. So ask peers for the tool's own output (a count, a sha, a pasted line), not a verdict.

**Why.** "Done" and "green" are easy to say and cannot be checked. A test count or a commit sha cannot be invented without doing the work.

**How to check.** For each "done" you relay, you have looked at one of: the merged commit on main, the queue's result line, or the pasted tool output. See `subagent-reports-complete-but-pr-unmerged` for reports that say complete while the pull request is still open.

### 17. A subagent with test tooling will submit jobs unless its brief forbids it

**Rule.** Every brief that involves tests says: "Do not submit to the shared test machine. Return the job list (commit, leg, target) to the coordinator."

**Why.** A subagent that can see the submit tool will use it. One coordinator's own subagent sent eight single-file jobs, about one a minute. They jumped ahead of two landing batches.

**How to check.** Read the brief before you send it and look for that sentence. After a subagent finishes, compare the machine's job list with the jobs you queued. Any job you did not queue came from somewhere else.
