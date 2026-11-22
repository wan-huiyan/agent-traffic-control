---
name: recover-from-an-async-post-commit-hook
description: |
  The repo's post-commit hook keeps working in the background after `git commit` returns
  (it prints "running ... in background", or makes its own `[auto-docs]` commit). Use when,
  soon after a commit, a sibling worktree says `fatal: unable to read <sha>`, an amend
  shows thousands of deletions or lands on the hook's commit, a rebase prints "It has been
  rescheduled", a merged branch is `[ahead 1]`, or checkout says the branch is used by an
  `autodocs-*` worktree. Not for real CONFLICT lines or pre-commit failures.
disable-model-invocation: true
version: 1.0.0
date: 2026-11-22
author: wan-huiyan
---
# Recover From an Async Post-Commit Hook

Merged from: worktree-index-corrupt-async-post-commit-hook,
git-add-u-after-async-post-commit-hook, git-amend-hits-async-post-commit-hook-commit,
git-rebase-stalls-async-post-commit-hook, async-post-commit-hook-commit-orphaned-by-squash-merge,
async-doc-hook-autodocs-worktree-locks-branch-checkout.

## Problem

Some repos have a `post-commit` hook that starts work in the background and returns at once.
Typical log line at commit time:

```
[post-commit] Python files changed — running doc update in background...
```

Typical hook bodies:

```sh
# Anti-pattern A: Claude headless mode in the background
( claude -p "..." --allowedTools "Read,Edit,Write,Bash,Grep,Glob" \
    > /tmp/claude.log 2>&1
  ... rest of background work
) &

# Anti-pattern B: nohup spawn
nohup ./regen-site.sh > /tmp/regen.log 2>&1 &

# Anti-pattern C: heavy work in git's process group
python3 regen.py > /dev/null 2>&1 &
```

`git commit` gives you the prompt back while that process is still reading and writing files,
objects, the index, refs, worktrees and sometimes making **its own commit**. Whatever git command
you run next races it. Nothing in git warns you; each symptom below looks like an unrelated
problem. All six variants share one cause and one prevention (see Solution, part 1).

### Variant 1 — a sibling worktree's index is corrupt

You commit in worktree A. Within seconds you run `git status`, `git rebase origin/main` or
`git fetch && git rebase` in worktree B and get:

```
fatal: unable to read cd2a732cd2d5ad030414b953e21b9e403ab88699
```

or

```
error: cd2a732c...: invalid sha1 pointer in cache-tree of
       .../.git/worktrees/<name>/index
error: missing blob b007cf60...
error: missing blob d4077a21...
```

Worktree B was clean and untouched, yet `git status` itself fails and `git rebase` aborts
before doing anything (it may first say `error: cannot rebase: You have unstaged changes.`).

Why: linked worktrees share `.git/objects/` but each has its own index at
`.git/worktrees/<name>/index`, whose cache-tree caches `(path → tree-sha)`. The hook in A is
mid-way through writing objects when B reads its cache-tree, which now points at SHAs that are
not flushed yet, or were briefly visible and then replaced. Every command in B that consults
the index fails before it even reads HEAD.

The fingerprint is that `git fsck` reports **several** worktrees' indexes broken at once:

```
error: <sha>: invalid sha1 pointer in cache-tree of .../.git/worktrees/<worktree-A>/index
error: <sha>: invalid sha1 pointer in cache-tree of .../.git/worktrees/<worktree-B>/index
error: <sha>: invalid sha1 pointer in cache-tree of .../.git/worktrees/<worktree-C>/index
```

The error message names the worktree where you ran the command, not the one whose hook caused
it; `git fsck` is what reveals the cross-cut.

### Variant 2 — `git add -u` before an amend stages thousands of deletions

You make a small commit, the hook starts, and you amend (typo, wrong issue reference) with the
muscle-memory sequence:

```sh
git add -u && git commit --amend -m "..."   # ← TRAP
```

The amend reports:

```
[your-branch 480e2226] fix(...): your message
 1493 files changed, 4 insertions(+), 368977 deletions(-)
 delete mode 100644 .claude-memory/MEMORY.md
 delete mode 100644 scripts/...
```

If you then ran `git push --force-with-lease`, the remote PR now shows thousands of unrelated
deletions mixed with your intended 6-file fix. `git status` shows files that **were tracked**
before the amend as **Untracked** (`.claude-memory/`, `.cursor/`, `.github/`, `MEMORY.md`,
`scripts/`, ...).

Why: the background process reads tracked files (`MEMORY.md`, `docs/site/*.html`), regenerates,
renames, moves or deletes them, and may run `git rm` or otherwise change the index. `git add -u`
stages every change to tracked files, including the hook's. `git add .` from the repo root and
`git commit -a` have the same trap. A hook that only prints logs, without touching tracked files,
is inert; this variant needs both async execution and tracked-file mutation.

### Variant 3 — `git commit --amend` rewrites the hook's commit, not yours

The hook makes its own follow-up commit (`[auto-docs] ...`, a site regen, a changelog or
plan-checkbox tick). A later `git commit --amend` rewrites **the hook's commit**: your change is
folded into a commit titled `[auto-docs] ...`, and your real `feat(...)` commit is untouched. The
amend succeeds with no error. Content is not lost, only the commit structure is wrong, which is
harmless under squash-merge but corrupts a rebase-merge workflow and confuses `git log`.

Very common in subagent-driven development: a fix subagent is told to `--amend`, but the hook
committed between the implementer subagent's commit and the fix subagent's run. Example: a
code-quality fix subagent ran `git commit --amend --no-edit` to fold a fix into
`feat(library): ...`; the `[auto-docs]` hook had already committed on top, so the amend rewrote
that commit instead. Caught only because HEAD's message did not match the work.

### Variant 4 — a multi-commit rebase stalls with "rescheduled"

Every commit a rebase replays fires the hook. Partway through:

```
Rebasing (1/10)Rebasing (2/10)...Rebasing (5/10)
[post-commit] Python files changed — running doc update in background...
hint:
hint:     pick 8b625b6b8b... fix(runbook): split verification probe ...
hint:
hint: It has been rescheduled; To edit the command before continuing, please
hint: edit the todo list first:
hint:
hint:     git rebase --edit-todo
hint:     git rebase --continue
```

No `CONFLICT (content):` line. `git status` reports `## HEAD (no branch)`. `git rebase --abort`
returns silently but does **not** clear `.git/worktrees/<name>/rebase-merge/` (or
`.git/rebase-merge/` outside worktrees), so the next rebase says:

```
fatal: It seems that there is already a rebase-merge directory, and
I wonder if you are in the middle of another rebase.
```

Why: even with `&` or a `( ... )` subshell and redirects, the spawned process inherits git's
process group and holds file descriptors and locks. Git's atomic steps (write index, advance HEAD,
apply the next patch) collide with them, and git reads the failure as "could not apply, try
again later". It is most reproducible on early commits in the sequence, before earlier spawns are
reaped, and on a loaded machine. The abort path can also hang, leaving the stuck directory. For a
non-interactive `git rebase origin/main`, "rescheduled" without a conflict is the signature; the
only other source is a todo edit in `git rebase -i`.

**Lock signature of the same race.** The rebase can instead stop with:

```
Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. ... remove the file manually to continue.
```

The hook held `.git/.../index.lock`. Two things look alarming and are fine: the working tree
shows your changes "reverted" because the rebase had checked out an **intermediate** replayed
commit (editors report the files as modified), and your branch ref still points at the original
tip (`git rev-parse <branch>` and `git log --oneline <branch>` show every commit intact).

### Variant 5 — the hook's commit is orphaned by a squash-merge

1. You commit your fix.
2. `git push -u origin <branch>` **finishes before the hook commits**, so the remote has only
   your commit.
3. You open the PR and squash-merge it; the squash is built from the pushed state.
4. Then the hook's `[auto-docs]` commit lands, **local only**, on top of your branch.

Your branch is now `[ahead 1]` of `origin/<branch>`, holding real content (for example a design
doc corrected to match your change, or a regenerated site asset) that is not on main. Delete the
merged branch and it is silently gone, and because keeping the doc in sync was the hook's job,
nobody regenerates it. Whether the hook commit makes the push is a pure race; for a fast push it
almost never does.

The tell is `[ahead 1]` after a "complete" squash-merge. A squash-merge normally leaves the local
branch behind or diverged, not **ahead** of its own origin ref.

Example: a copy fix was committed as `7c14b4e0`, pushed, PR #1283, squash-merged to `d47349e6`.
At handoff, `git status -sb` showed the branch `[ahead 1]`. The extra commit `c5de20d3` was
`[auto-docs] monitor-redesign design: correct SprWin empty-card framing to data gap`: the hook had
rewritten the canonical design doc so a future session would not follow a now-falsified
recommendation. It was never in #1283. Rescued by branching off `origin/main` (12 commits ahead
by then), `git cherry-pick c5de20d3` (applied clean), and shipping it in the handoff PR #1299.

### Variant 6 — the hook's own worktree locks your branch

The doc-update hook creates its own worktree (for example `.claude/worktrees/autodocs-<topic>`)
on the branch you just committed to. Git allows a branch in only one worktree, so a later checkout
fails:

```
fatal: '<branch>' is already used by worktree at
'/…/.claude/worktrees/autodocs-<topic>'
```

It also surfaces indirectly: a code-review subagent pointed at your PR reports paths under
`.../worktrees/autodocs-<topic>/...`, a worktree you never created. The same hook can also leave
an `index.lock` behind (`Unable to create '.git/worktrees/<name>/index.lock'`), cleared with
`rm -f`.

Example: committed `23f36f6d` on a feature branch, switched to a sibling branch to build the next
part, then needed to return for a reviewer's fix. Checkout was refused because
`autodocs-<topic>` held the branch, and the review subagent had been citing paths under it.
Confirmed local == origin == `23f36f6d`, force-removed the autodocs worktree, checkout succeeded.

## Context / Trigger Conditions

- The commit output contains `[post-commit] ... running ... in background`, or `.git/hooks/post-commit`
  (or the vendored `.githooks/post-commit`, see `git config core.hooksPath`) contains `&`,
  `nohup`, `( ... ) &`, or spawns `claude -p`, `npm run`, `bundle exec` non-interactively.
- Commits you did not author appear (`[auto-docs]`, `chore: regenerate ...`).
- One of the six symptoms above appears within seconds to minutes of a commit, an amend, a
  rebase, a push or a branch switch.
- Not this skill: a plain stale `.git/index.lock` with no hook involved (just remove the lock),
  `error: cannot lock ref` (a concurrent ref-update race), corruption in a single worktree with no
  hook (different cause), a branch held by an ordinary sibling worktree
  (`gh-pr-merge-worktree-checkout-trap`), real merge conflicts (`CONFLICT (content):` lines),
  pre-commit failures, or a genuine commit-message prompt (which opens `$EDITOR`).

## Solution

### Part 1 — the shared prevention

1. **Read the hook once per repo or worktree.**

   ```sh
   cat .git/hooks/post-commit 2>/dev/null | head -30
   cat .githooks/post-commit 2>/dev/null; git config core.hooksPath
   # pre-flight before a long rebase:
   cat .git/hooks/post-commit 2>/dev/null | grep -E '&\s*$|nohup|running.*background' >/dev/null && \
     echo "WARNING: post-commit hook spawns background work; consider running with hooks disabled"
   ```

   If it backgrounds work, treat the whole repo as racy across worktrees for every commit. A
   pre-commit hook that prints "running ... in background" carries the same mechanism between
   successive `git add` calls within one commit.

2. **Wait for the hook, or switch hooks off for the one risky command.** Waiting 5-10 seconds
   usually ends the race; check with `git status` (clean if the hook regenerates idempotently) and
   `ps -ef | grep -i "<project>\|generate_website\|generate_roadmap"`. If files keep changing,
   wait longer. For a rebase or any multi-commit operation:

   ```sh
   git -c core.hooksPath=/dev/null rebase origin/main
   ```

   This is scoped to the one invocation: it does not touch `.git/config`, other people, or later
   commits. Git finds no hook at `/dev/null` and forks nothing. It is safer than `chmod -x` (which
   persists) or moving the file aside (easy to forget to restore).

3. **Read `git log` and `git status` yourself after every commit.** Do not trust an
   agent-reported SHA: the hook can move HEAD after the agent reports. Pick BASE and HEAD for the
   next step from `git log --oneline`.

4. **Never `git commit --amend` in such a repo, and never tell a subagent to.** Make a fresh
   commit; a clean extra commit squash-merges away, a misplaced amend is silent structural damage.
   If you must amend, confirm HEAD is yours first (`git log -1 --format='%s'`), ideally with the
   hook off.

5. **Stage explicit paths, never `git add -u`, `git add .` or `git commit -a` right after a
   commit**, and check before amending:

   ```sh
   git add path/to/file1 path/to/file2
   git diff --staged --stat
   # → 6 files changed, 211 insertions(+), 21 deletions(-)    matches: proceed
   # → 1493 files changed, 4 insertions(+), 368977 deletions(-)  STOP, do not amend
   ```

   If the count is far larger than your change, unstage (`git restore --staged .` or
   `git reset HEAD path/...`) and stage explicitly.

6. **Before deleting a merged branch, look for commits ahead of its origin ref**
   (`git status -sb`). Never blind-delete a branch that is `[ahead]`.

7. **In scripts that walk many worktrees** (sequential squash-merges, rebases), rebuild the next
   worktree's index before touching it, unconditionally. It is cheap (~50 ms) and idempotent:

   ```sh
   rm .git/worktrees/<name>/index 2>/dev/null
   git reset --mixed HEAD
   ```

### Part 2 — recovery, by symptom

| Symptom | Recovery |
|---|---|
| `fatal: unable to read <sha>` / `invalid sha1 pointer in cache-tree` in a sibling worktree (V1) | In each broken worktree: `rm <main-repo>/.git/worktrees/<name>/index && git reset --mixed HEAD` |
| Amend shows 1000+ files and deletions; tracked files now untracked (V2) | Reset to the good commit from the reflog, force-push with lease, redo the amend with explicit paths |
| HEAD's message is the hook's after an amend (V3) | Nothing is lost; next time make a fresh commit. Re-split only if the workflow needs commit structure |
| Rebase "rescheduled", detached HEAD, stuck `rebase-merge` (V4) | Remove the stuck directory, check out the branch, rebase with `-c core.hooksPath=/dev/null` |
| Rebase stops with "Another git process seems to be running" (V4, lock form) | `git rebase --abort`, confirm the branch tip, retry; if it stalls again, hooks off |
| Merged branch is `[ahead 1]` of origin with a hook commit (V5) | Inspect it; if worth keeping, cherry-pick onto a fresh branch off `origin/main` |
| `'<branch>' is already used by worktree at .../autodocs-<topic>` (V6) | Confirm the hook committed nothing, then `git worktree remove --force` it |

**V1 — rebuild the index.** The index is a derived cache; deleting it makes git rebuild from the
files on disk and HEAD. The working tree is untouched; staged changes are lost, but you were not
mid-edit if you got here.

```sh
cat .git                       # gitdir: /path/to/main/repo/.git/worktrees/<NAME>
rm /path/to/main/repo/.git/worktrees/<NAME>/index
git reset --mixed HEAD         # or the slightly more surgical: git read-tree HEAD
```

If `fsck` still names other worktrees' indexes, repeat in each. If the hook also writes under
`.git/info/` or `.git/refs/`, stranger symptoms appear with the same cause and the same fix.

Example: five parallel feature worktrees were squash-merged one after another with `gh pr merge`.
Right after merging PR #244 in worktree A, `git fetch && git rebase origin/main` in worktree B
failed; `git fsck --no-dangling` showed four worktree indexes broken at once. Rebuilding B's index
fixed it, and rebuilding each next worktree's index **before** its rebase stopped the race for the
rest of the sequence.

**V2 — undo the bad amend.** `reset --hard` is safe here because the "deleted" files are still on
disk as untracked; the hook removed them from the index, it did not unlink them.

```sh
git reflog | head -5
#  → c77e6365 HEAD@{2}: commit: fix(insights): ...your good commit
#  → 480e2226 HEAD@{1}: commit (amend): ...same message, but bad index
git reset --hard c77e6365                    # destructive: confirm the SHA first
git push --force-with-lease origin your-branch
git add path/to/file1 path/to/file2          # redo the amend with EXPLICIT paths
git commit --amend -m "corrected message"
git push --force-with-lease origin your-branch
```

If anyone else has pulled the bad commit, prefer `git revert <bad-sha>`: same end state on main
after a squash-merge, no history rewrite. `--force-with-lease` protects against overwriting other
people's pushes; it does not detect that your own push is bad.

**V4 — unstick the rebase.**

```sh
ls -la .git/worktrees/<your-worktree>/rebase-merge/ 2>/dev/null   # or .git/rebase-merge/
rm -rf .git/worktrees/<your-worktree>/rebase-merge                 # or .git/rebase-merge
git checkout <your-branch>
git -c core.hooksPath=/dev/null rebase origin/main
# → Successfully rebased and updated refs/heads/<your-branch>.
```

Before forcing the `rm -rf`, check no other rebase is genuinely running in another shell or
worktree. Hooks fire again normally on the next command; nothing to re-enable.

Example: a PR with 10 commits ahead of `origin/main` had rebased cleanly twice; the third rebase
(after a reviewer flagged a tracker-ID collision from a parallel PR) hung at commit 4 with the
"rescheduled" hint, `--abort` returned silently, and the next rebase hit the stuck directory.
`rm -rf .git/worktrees/<name>/rebase-merge`, checkout, then the hooks-off rebase succeeded.
About ten minutes were lost to retries with different environment variables first. In another
session the lock form appeared when a background `gh`/test process and the doc hook coincided
with a rebase; abort and retry recovered with all commits intact.

**V5 — rescue the orphan before deleting the branch.**

```sh
git status -sb            # "[ahead 1]" of origin = unpushed local commit(s)
git log --oneline -3      # is the top one the [auto-docs]/hook commit?
git show <sha> --stat     # what did the hook generate?
git cat-file -e origin/main:<path-the-hook-edited> && echo EXISTS   # main may have moved
git fetch origin
git checkout -b <handoff-branch> origin/main   # NOT onto the stale merged branch
git cherry-pick <sha>
```

If the commit is noise (a no-op regen, already correct), discard it. Otherwise fold it into your
next PR; a session-handoff PR is the natural home.

**V6 — free the branch.** Confirm the hook added nothing first:

```bash
git rev-parse <branch>                   # local tip
git rev-parse origin/<branch>            # remote tip, if pushed
git log --oneline <your-sha>..<branch>   # empty = no extra commits
git worktree remove --force .claude/worktrees/autodocs-<topic>
git worktree list | grep autodocs        # gone
rm -f .git/worktrees/<your-worktree>/index.lock   # if a leftover lock is present
git checkout <branch>
```

If the autodocs worktree did commit (rare), cherry-pick that first. Never `git branch -D` the
branch to unstick it; that destroys your work. Remove the worktree instead.

### Part 3 — fixing the hook itself (if you maintain the repo)

1. **Skip the hook during a rebase.** The hook's intent ("react to a new commit") is wrong during
   replay anyway; you do not want N background jobs in ten seconds.

   ```sh
   # in .git/hooks/post-commit
   if [ -d "$(git rev-parse --git-dir)/rebase-merge" ] || \
      [ -d "$(git rev-parse --git-dir)/rebase-apply" ]; then
       exit 0
   fi
   ```

2. **Detach it properly**, so it leaves git's process group:

   ```sh
   setsid bash -c "<background-work>" </dev/null >/tmp/log 2>&1 &
   disown
   ```

3. **Move it to `post-rewrite`** if it only needs to run after human commits: that fires once at
   the end of a rebase, not per commit.
4. **Make it synchronous** (`wait` at the end, or drop `&`/`nohup`): slower commits, no race.

The `claude -p` headless-spawn pattern (auto-docs, auto-tracker updates, auto-skill-extraction) is
increasingly common; prefer these mitigations by default in such projects.

## Verification

- V1: `git status` reports the branch state without error; `git fsck --no-dangling` reports no
  error for this worktree's index (repeat for any other worktree it names).
- V2: `git log --oneline -2`; `git diff HEAD~1 --stat` matches your intended change (for example
  6 files, 211+, 21-); `git status` is clean; the remote PR diff shows only your files.
- V3: `git log --oneline -3` right after committing shows your message on the commit you mean,
  and names any hook commit on top.
- V4: `git rev-list --left-right --count <branch>...origin/main` gives `N 0`;
  `git status -sb` shows `## <branch>...origin/<branch> [ahead N]`, not `## HEAD (no branch)`;
  `git log --oneline origin/main..HEAD` lists exactly your N commits, in order, with new SHAs.
- V5: `git show <new-sha> --stat` on the cherry-pick shows the orphan's files; after the next PR
  merges, `git show origin/main:<path>` contains the hook's correction. The original SHA does not
  need to be on main; its content does.
- V6: `git worktree list` has no `autodocs-*` entry; `git checkout <branch>` succeeds and
  `git rev-parse --short HEAD` is your commit.

## Notes

- Six symptoms, one mechanism: the hook is still working when your next git command starts. If
  you diagnose one of these in a repo, check for the others.
- A hook commit in `git log` that you did not author is the earliest detection signal for V3 and
  V5.
- If the stranded content is your own work rather than the hook's, see
  `reland-work-that-missed-a-squash-merge`.

## See also

- `gh-pr-merge-worktree-checkout-trap`: `gh` cannot delete or check out a branch held by an
  ordinary sibling worktree.
- `concurrent-session-checkout-clobbers-shared-worktree`: two sessions in one worktree.
- `reland-work-that-missed-a-squash-merge`: edits or commits of yours that missed the squash.
- `git-worktree`: general worktree workflow.

## References

- Git hooks, including `post-commit`, `post-rewrite` and `core.hooksPath`:
  https://git-scm.com/docs/githooks
- `git push --force-with-lease`: https://git-scm.com/docs/git-push
- `git rebase` behaviour: https://git-scm.com/docs/git-rebase
- `setsid`: https://man7.org/linux/man-pages/man1/setsid.1.html
