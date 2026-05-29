---
name: multi-worktree-file-url-stale-content
description: |
  When a user opens a `file://` URL bookmark to a file in a repo with multiple git worktrees, the browser shows whatever the targeted worktree's branch contains — NOT main, NOT the latest merge. Use when: (1) user reports "I don't see my change" or "the fix isn't there" right after a PR was merged, (2) you've confirmed via `git show origin/main:<path>` that main has the fix but the user-visible file:// view doesn't, (3) the file path mentioned by the user contains `.claude/worktrees/<name>/`, `worktrees/`, or any other multi-checkout root, (4) `git worktree list` shows 2+ paths and the bookmarked one is on a feature branch. Distinguishes from: `worktree-outer-ls-mistaken-for-main-state` (about `ls` outside any worktree), `flask-debug-cross-worktree-edit-stale` (about Flask debug reload reading wrong worktree). This skill specifically covers the user-bookmarks-a-file-URL variant where neither `ls` nor a server reload is in play — the browser opens whatever exists on disk in that worktree at that path.
author: Claude Code
version: 1.0.0
date: 2026-05-19
---

# Multi-worktree `file://` URL stale content

## Problem

The user opens a `file://` URL pointing to a deliverable / static HTML / docs file in the repo. They see old content. They report "the fix isn't there" or "I still see the thing we removed". They are correct about what they see — but the file IS fixed on `origin/main`. The disconnect is that the `file://` URL doesn't know what git branch is checked out at that path. The browser just reads whatever bytes are on disk.

In a repo with multiple `git worktree` checkouts, each worktree is on a different branch. The primary checkout at the repo root is *also* on a branch — usually the last feature branch someone was working on, NOT main. After a PR merges to main, none of the on-disk paths automatically update. The user's bookmark keeps showing the same stale content.

## Context / Trigger Conditions

All of:

- Repo uses git worktrees (`git worktree list` shows 2+ entries)
- File in question is a deliverable / static asset / docs file that humans open directly (HTML, MD-rendered-to-HTML, JSON viewer, PDF), not a service-rendered URL
- User opens it via `file://` URL bookmark (not via a running web server, not via VSCode preview)
- Recent merge to main updated that file
- User reports the file looks wrong / old / unchanged

Smoking-gun signal: the user-reported file path contains `.claude/worktrees/<name>/`, `worktrees/`, `.git/worktrees/`, or you can see `2+` worktrees via `git worktree list` and the bookmarked path is one of them.

## Solution

### Step 1 — confirm the file is actually fixed on main

```bash
# 1. Fresh fetch (don't trust cached refs)
git fetch origin main --quiet

# 2. Read the file as it exists on origin/main
git show origin/main:<path-relative-to-repo-root> | grep -c "<the-string-the-user-says-is-still-there>"
# Expect 0 if the fix is in
```

If the fix IS on main but the user's view doesn't show it → confirmed stale-worktree problem.

### Step 2 — identify which worktree the user's URL resolves to

The URL contains the on-disk path. Match it against `git worktree list`:

```bash
git worktree list
```

The matching worktree's branch (column 3) is what the user is actually looking at. Frequently NOT main.

### Step 3 — establish a canonical "always main" worktree

Pick ONE worktree to be canonical. The primary repo checkout is the natural choice (no `.claude/worktrees/...` in the path = a friendlier bookmark).

Hazard: if main is currently held by ANOTHER worktree (common — the user may have an old worktree like `chatbox-with-data` or `main-viewer` parked there), git will refuse to check out main in two places. Resolve by either:

(a) Pulling main on whichever worktree currently holds it. If that worktree's only job is being a "main viewer", this is sufficient — just update the user's bookmark to that path.

(b) Removing that worktree if it's stale. **Audit first** to confirm no work is lost:

```bash
# Check clean status + no unpushed commits + identify any uncommitted/tracked content
git -C <worktree-path> status                       # clean?
git -C <worktree-path> log origin/main..HEAD --oneline   # any unpushed commits? expect empty
git -C <worktree-path> stash list                   # stashes are repo-wide; not lost on removal
ls -la <worktree-path>/.claude-memory <worktree-path>/.claude 2>/dev/null  # session metadata?
git -C <worktree-path> ls-files .claude-memory/ | wc -l    # tracked in git? if yes, safe
```

If audit is clean, remove + reclaim main:

```bash
git -C <repo-root> worktree remove .claude/worktrees/<name>
git -C <repo-root> checkout main
git -C <repo-root> pull origin main --ff-only
```

### Step 4 — give the user the bookmark URL

```
file://<absolute-path-to-the-now-main-worktree>/<path-to-file>
```

After every future merge, they (or you) run `git -C <repo-root> pull origin main` and the bookmark stays current.

### Step 5 — preempt the next occurrence

In your end-of-session handoff doc, note "primary checkout is on main as of <session>" so the next session knows the invariant. If the primary checkout drifts (gets parked on a feature branch again), the user's bookmark goes stale again silently.

## Verification

After the switch:

```bash
grep -c "<the-string-the-user-says-is-still-there>" <absolute-path-on-primary-checkout>
# Expect 0
git -C <repo-root> log --oneline -1
# Should show the merge commit that landed the fix
```

The user re-opens their bookmark → sees the corrected content.

## Example

Session 206 of the `the-project-repo` repo (2026-05-19):

PR #911 merged the removal of a `Feature Shifts` card from a PM stakeholder walkthrough HTML deliverable. The user opened a `file://` URL bookmark and saw the card still present:

```
file:///Users/<user>/Documents/the-project-repo/.claude/worktrees/quick-verify/docs/deliverables/2026-05-19_pm_stakeholder_walkthrough.html
```

That path resolved to the `quick-verify` worktree, which was on `docs/s205-pm-walkthrough-review-handoff` — a stale branch from before the removal. Investigation also surfaced that the primary repo checkout was itself on `docs/s204b-shap-waterfall-handoff` (from a session two days earlier, never reset to main). Three local paths to the same logical file all showed different content depending on which branch each worktree happened to be parked on.

Fix:
1. `git fetch origin main` + `git show origin/main:docs/deliverables/2026-05-19_pm_stakeholder_walkthrough.html | grep -c "Feature Shift"` → 0 (confirmed fix is on main)
2. `git worktree list` → main was held by a `chatbox-with-data` worktree, 11 commits behind, clean status
3. Audited `chatbox-with-data` for work-to-lose: clean tree, no unpushed commits, `.claude-memory/` files all tracked, stashes are repo-wide. Safe to remove.
4. `git worktree remove .claude/worktrees/chatbox-with-data` → `git checkout main` → `git pull` (11 commits fast-forwarded)
5. New canonical bookmark: `file:///Users/<user>/Documents/the-project-repo/docs/deliverables/2026-05-19_pm_stakeholder_walkthrough.html`

User confirmed: the Feature Shifts card was gone in the browser.

## Notes

- **Don't assume the primary checkout is on main.** In a multi-worktree workflow, the primary checkout is just another worktree that drifts. The session has to maintain the invariant deliberately.
- **`gh pr merge --delete-branch` from a worktree often throws `fatal: 'main' is already used by worktree at <other-path>`.** Benign — the merge already succeeded remotely; only the local branch-delete failed. See sister skill `gh-pr-merge-worktree-checkout-trap`.
- **An alternative bookmark target is the GitHub raw / blob URL** (`https://github.com/<owner>/<repo>/blob/main/<path>`). Always reflects main, no local sync needed, but loses any local-only styling rendering and is slower to open.
- **For Flask / server-rendered pages this skill does not apply** — see `flask-debug-cross-worktree-edit-stale` for that variant. The diagnostic difference is whether the user is opening a file directly (`file://`) or visiting a service URL (`http://localhost:N/...`).

## See also

- `worktree-outer-ls-mistaken-for-main-state` — variant where the user runs `ls` outside any worktree and thinks they see main state
- `flask-debug-cross-worktree-edit-stale` — variant where a running Flask debug server reads the wrong worktree
- `gh-pr-merge-worktree-checkout-trap` — companion footgun on `gh pr merge --delete-branch` in multi-worktree repos
- `using-git-worktrees` — general worktree hygiene skill
