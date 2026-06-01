# Agent Traffic Control

A coordination toolkit of 61 [Claude Code](https://claude.com/claude-code) skills for **running multiple parallel sessions against the same repo without collisions, stranded work, or rebase loops** — issue-pickup claim protocol, worktree & session-isolation pitfalls, parallel-PR conflict recovery, subagent-integrity edge cases, and the squash/merge mechanics that bite when multiple PRs converge on the same branch.

[![license](https://img.shields.io/github/license/wan-huiyan/agent-traffic-control)](LICENSE)
[![last commit](https://img.shields.io/github/last-commit/wan-huiyan/agent-traffic-control)](https://github.com/wan-huiyan/agent-traffic-control/commits)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-orange)](https://claude.com/claude-code)

## When to reach for this toolkit

- You routinely run **2+ Claude Code sessions in parallel** against the same repo (worktrees, separate terminals, scheduled overnight loops, or sandbox + main).
- You've seen **two sessions independently start work on the same issue**, **PRs collide on rebase**, **subagent reports look complete but the PR never merged**, **a worktree's index goes corrupt right after committing in a sibling**, or **GitHub squash-merge auto-closes only one issue out of three you listed in the PR body**.
- You want **upstream prevention** at the issue-pickup boundary plus **downstream recovery** for the failure modes that still slip through.

## Installation

```bash
# Add the marketplace
/plugin marketplace add wan-huiyan/agent-traffic-control

# Install the plugin — one shot, gets all 61 skills
/plugin install agent-traffic-control@wan-huiyan-agent-traffic-control
```

This is a single multi-skill plugin (modeled on `superpowers`), not a marketplace of individual plugins. One install gets you the full `before / during / after / orchestrator-aware / merge-mechanics` arc; you can't pick-and-choose per-skill via `/plugin install`. If you only want one or two of these skills, copy them directly into `~/.claude/skills/<skill-name>/` instead.

## The five buckets

The 61 skills split into a **before / during / after / orchestrator-aware / merge-mechanics** arc:

### A. Pickup / claim coordination — *prevention*

Before any code is written, claim the issue so sibling sessions detect it and skip.

| Skill | Role |
|---|---|
| [**gh-issue-claim-coordination**](plugins/agent-traffic-control/skills/gh-issue-claim-coordination/) | 60-second protocol: preflight (`gh issue view --json assignees,labels,updatedAt`) + atomic claim (`--add-assignee @me --add-label wip`) + 24h stale-claim sweep + label-drop on PR merge. Self-heals: idempotent `gh label create` runs every pickup. |
| [**session-handoff-number-collision-with-unmerged-sibling**](plugins/agent-traffic-control/skills/session-handoff-number-collision-with-unmerged-sibling/) | Two sibling sessions both pick the same next handoff number from `docs/handoffs/` because each only sees what's merged on its branch — detect and renumber before push. |
| [**session-handoff-detect-prior-orphan-pr**](plugins/agent-traffic-control/skills/session-handoff-detect-prior-orphan-pr/) | Pre-flight detect a prior incomplete handoff run's branch/PR/worktree before starting, so you don't open a duplicate PR for work already in flight. |

See also: `superpowers:dispatching-parallel-agents` — when to fan out vs. not (not bundled here; ships with the official `superpowers` plugin).

### B. Worktree & session isolation pitfalls

The cheap-isolation primitive (`git worktree`) has surprising failure modes when paired with parallel sessions, async post-commit hooks, and sibling subagents.

| Skill | Role |
|---|---|
| [**using-git-worktrees**](plugins/agent-traffic-control/skills/using-git-worktrees/) | Create isolated worktrees with smart directory selection + safety verification — the right starting move for parallel feature work. |
| [**git-worktree**](plugins/agent-traffic-control/skills/git-worktree/) | General git-worktree workflow patterns. |
| [**gh-pr-merge-worktree-checkout-trap**](plugins/agent-traffic-control/skills/gh-pr-merge-worktree-checkout-trap/) | Diagnose `branch is checked out elsewhere` errors when merging a PR while the same branch is checked out in another worktree. |
| [**worktree-index-corrupt-async-post-commit-hook**](plugins/agent-traffic-control/skills/worktree-index-corrupt-async-post-commit-hook/) | Fix `fatal: unable to read <sha>` errors that surface in worktree B after committing in worktree A — when an async post-commit hook (`&` / `nohup`) is in play. |
| [**worktree-historical-test-replay-missing-dirs**](plugins/agent-traffic-control/skills/worktree-historical-test-replay-missing-dirs/) | When a historical test replay fails because directories that exist in HEAD don't exist at the older commit. |
| [**worktree-outer-ls-mistaken-for-main-state**](plugins/agent-traffic-control/skills/worktree-outer-ls-mistaken-for-main-state/) | Confusing `.claude/worktrees/<name>` directory listing for the main checkout's state and acting on stale assumptions. |
| [**pr-hijack-via-stale-worktree-branch-ref**](plugins/agent-traffic-control/skills/pr-hijack-via-stale-worktree-branch-ref/) | A stale local worktree's branch ref overwrites a teammate's pushed commits when force-push or auto-update kicks in — verify upstream before pushing. |
| [**subagent-bash-cd-wrong-worktree**](plugins/agent-traffic-control/skills/subagent-bash-cd-wrong-worktree/) | Subagents inheriting the wrong CWD when dispatched from a worktree. |
| [**flask-debug-cross-worktree-edit-stale**](plugins/agent-traffic-control/skills/flask-debug-cross-worktree-edit-stale/) | Flask debug server reading stale code because the file you edited lives in a sibling worktree. |
| [**git-add-u-after-async-post-commit-hook**](plugins/agent-traffic-control/skills/git-add-u-after-async-post-commit-hook/) | `git add -u` racing with an async post-commit hook's writes — partial stages and surprising diffs. |
| [**git-rebase-stalls-async-post-commit-hook**](plugins/agent-traffic-control/skills/git-rebase-stalls-async-post-commit-hook/) | `git rebase` stalls or fails mid-replay because an async post-commit hook is holding a lock or writing to the index. |
| [**git-amend-hits-async-post-commit-hook-commit**](plugins/agent-traffic-control/skills/git-amend-hits-async-post-commit-hook-commit/) | `git commit --amend` folds your change into a background post-commit-hook commit instead of your own feature commit. |
| [**concurrent-session-checkout-clobbers-shared-worktree**](plugins/agent-traffic-control/skills/concurrent-session-checkout-clobbers-shared-worktree/) | A second session's `git checkout` flips the branch under your shared working tree, clobbering uncommitted work — detect and recover via an isolated worktree. |
| [**cross-worktree-spec-handoff-via-checkout-paths**](plugins/agent-traffic-control/skills/cross-worktree-spec-handoff-via-checkout-paths/) | Pass specs/handoff prompts between two parallel sessions on different worktree branches without round-tripping through main. |
| [**main-bash-cwd-persists-nested-worktree**](plugins/agent-traffic-control/skills/main-bash-cwd-persists-nested-worktree/) | The main agent's Bash cwd persists across calls, so orchestrated worktree creation lands at the wrong (nested) path. |
| [**multi-worktree-file-url-stale-content**](plugins/agent-traffic-control/skills/multi-worktree-file-url-stale-content/) | A `file://` bookmark serves the targeted worktree branch's content, not main, after a merge — stale-content confusion across checkouts. |
| [**git-stash-pop-pulls-unrelated-stash**](plugins/agent-traffic-control/skills/git-stash-pop-pulls-unrelated-stash/) | The stash stack is global across branches and worktrees; a reflexive `stash pop` can pull a sibling worktree's stash. |
| [**claude-code-projects-jsonl-worktree-fanout**](plugins/agent-traffic-control/skills/claude-code-projects-jsonl-worktree-fanout/) | Session JSONLs fan out into worktree-namespaced project dirs — grepping only the canonical dir misses worktree-run sessions. |
| [**deploy-from-stale-worktree-silent-rollback**](plugins/agent-traffic-control/skills/deploy-from-stale-worktree-silent-rollback/) | Deploying from a worktree whose HEAD predates merged PRs silently rolls back prod — build context is the filesystem, not the git ref. |

### C. Parallel-PR conflict recovery — *after collision*

When two sessions DO collide (or an old PR drifts behind a fast-moving main), these resolve the rebase cleanly.

| Skill | Role |
|---|---|
| [**parallel-pr-template-fork-duplicates-moved-section**](plugins/agent-traffic-control/skills/parallel-pr-template-fork-duplicates-moved-section/) | Two PRs both move a template section — merge produces duplicates. Detect + dedupe. |
| [**parallel-pr-scope-overlap-tiebreaker-delta-check**](plugins/agent-traffic-control/skills/parallel-pr-scope-overlap-tiebreaker-delta-check/) | Two PRs claim overlapping scope — pick the winner via delta-check rather than first-merged. |
| [**pr-conflict-from-mid-flight-merges**](plugins/agent-traffic-control/skills/pr-conflict-from-mid-flight-merges/) | Mid-flight merges of unrelated PRs creating cascading conflicts on your branch. |
| [**stale-base-pr-silently-reverts-upstream-content**](plugins/agent-traffic-control/skills/stale-base-pr-silently-reverts-upstream-content/) | An old PR with a stale base silently reverts upstream content when merged — detect via base-vs-main diff before approving. |
| [**gha-pr-merge-ref-shows-upstream-changes**](plugins/agent-traffic-control/skills/gha-pr-merge-ref-shows-upstream-changes/) | The PR's merge ref shows upstream changes you didn't make — explain why and avoid panic-reverting. |
| [**synthetic-id-collision-rebase**](plugins/agent-traffic-control/skills/synthetic-id-collision-rebase/) | Two sessions both claimed the same numeric ID (tracker entry, ADR number, fixture row) — rename + propagate during rebase. |
| [**merge-conflict-generated-files**](plugins/agent-traffic-control/skills/merge-conflict-generated-files/) | Generated files (lock files, generated HTML, snapshot JSON) shouldn't be hand-merged — regenerate from the union of inputs. |
| [**gh-pr-create-orchestration-cwd-wrong-head**](plugins/agent-traffic-control/skills/gh-pr-create-orchestration-cwd-wrong-head/) | `gh pr create` opens the PR against the orchestration worktree's branch instead of the feature branch, spawning duplicate PRs. |
| [**gh-pr-merge-unstable-state-needs-auto-and-watch-branch-deletes**](plugins/agent-traffic-control/skills/gh-pr-merge-unstable-state-needs-auto-and-watch-branch-deletes/) | `MERGEABLE`+`UNSTABLE` failures masquerade as conflicts (pending CI); deleting the branch after a false conflict flips the PR to CLOSED. |
| [**git-diff-2dot-vs-3dot-merge-safety**](plugins/agent-traffic-control/skills/git-diff-2dot-vs-3dot-merge-safety/) | A 2-dot diff false-alarms "this PR deletes files on main" for a PR branched off an older commit — use 3-dot to check merge safety. |
| [**docs-branch-off-feature-branch-smuggles-code**](plugins/agent-traffic-control/skills/docs-branch-off-feature-branch-smuggles-code/) | A `docs(...)` PR branched off a feature branch (not main) silently ships the parent branch's code. |
| [**stacked-pr-review-per-base-diff-and-attach**](plugins/agent-traffic-control/skills/stacked-pr-review-per-base-diff-and-attach/) | Review a stack by diffing each PR against its own base (not all-vs-main) and attach reviews to the stack's base branch. |

### D. Subagent integrity — *orchestrator-aware*

Subagents introduce their own coordination failure modes. These cover misattribution, incomplete reports, takeover during waits, silent phase compression, credit-stall recovery, stranded branch refs, watchdog stalls, source-completeness for verification subagents, and grep-verifying the dispatcher's own claims.

| Skill | Role |
|---|---|
| [**subagent-pre-existing-misattribution**](plugins/agent-traffic-control/skills/subagent-pre-existing-misattribution/) | Subagent claims credit for code that was already there before its dispatch. |
| [**subagent-reports-complete-but-pr-unmerged**](plugins/agent-traffic-control/skills/subagent-reports-complete-but-pr-unmerged/) | Subagent's "✅ done" doesn't mean the PR landed — verify merge state, not report state. |
| [**subagent-external-wait-orchestrator-takeover**](plugins/agent-traffic-control/skills/subagent-external-wait-orchestrator-takeover/) | When a subagent is blocked waiting on external state, the orchestrator can step in safely (or unsafely) — this skill covers the boundary. |
| [**multi-agent-skill-silent-phase-compression**](plugins/agent-traffic-control/skills/multi-agent-skill-silent-phase-compression/) | Multi-phase skills silently collapsing phases when the model decides the work was "small enough" — restoring phase boundaries. |
| [**multi-phase-skill-disk-reading-strategy**](plugins/agent-traffic-control/skills/multi-phase-skill-disk-reading-strategy/) | Late-pipeline subagents should read written files from disk, not pipe everything through the orchestrator's context. |
| [**credit-stall-mid-orchestration-revive-collision**](plugins/agent-traffic-control/skills/credit-stall-mid-orchestration-revive-collision/) | Reviving an orchestration after a credit stall — collision avoidance for in-flight work that may have continued. |
| [**handoff-prompt-stale-user-hint-newer-state**](plugins/agent-traffic-control/skills/handoff-prompt-stale-user-hint-newer-state/) | A handoff prompt carries a user hint that no longer matches current state — detect and re-confirm before acting. |
| [**subagent-driven-branch-ref-froze-stranded-commits**](plugins/agent-traffic-control/skills/subagent-driven-branch-ref-froze-stranded-commits/) | In subagent-per-task runs, committed work survives in the worktree HEAD but never reaches the pushed branch ref — the PR ships partial. |
| [**subagent-watchdog-stall-on-ui-template-track**](plugins/agent-traffic-control/skills/subagent-watchdog-stall-on-ui-template-track/) | A UI/template subagent is killed by the no-output watchdog (~600s silence); recover the uncommitted worktree changes and run inline rather than re-dispatching. |
| [**code-reviewer-subagent-no-bash-blocked-on-pr-diff**](plugins/agent-traffic-control/skills/code-reviewer-subagent-no-bash-blocked-on-pr-diff/) | Review subagents lacking Bash can't fetch PR diffs and return BLOCKED — pre-materialize the diff to a file before dispatch. |
| [**factcheck-subagent-needs-complete-sources**](plugins/agent-traffic-control/skills/factcheck-subagent-needs-complete-sources/) | Feeding a verification subagent an abridged source yields false-positive "unsupported" verdicts on the trimmed regions. |
| [**task-framing-claims-need-subagent-grep-verify**](plugins/agent-traffic-control/skills/task-framing-claims-need-subagent-grep-verify/) | Grant and require a dispatched subagent to grep-verify the dispatcher's task-framing claims about the codebase before acting. |
| [**pr-plan-bucket-triage-before-sizing**](plugins/agent-traffic-control/skills/pr-plan-bucket-triage-before-sizing/) | Run a subagent-per-bucket Phase-0 triage before writing detailed parallel-PR plans on an actively-shipped repo. |
| [**wip-branch-linter-revert-system-reminder-trap**](plugins/agent-traffic-control/skills/wip-branch-linter-revert-system-reminder-trap/) | A linter/automation system-reminder silently reverts deliberate WIP-branch constants during parallel work — don't accept the revert. |
| [**code-review-subagent-fabricates-specifics-to-inflate-severity**](plugins/agent-traffic-control/skills/code-review-subagent-fabricates-specifics-to-inflate-severity/) | A review subagent reports a HIGH/BLOCKING finding citing specific evidence (line numbers, call counts) that doesn't exist — verify the cited specifics before gating a merge; demote on fabrication. |
| [**db-access-review-subagent-needs-explicit-probe-budget**](plugins/agent-traffic-control/skills/db-access-review-subagent-needs-explicit-probe-budget/) | A review/verification subagent with live DB/cloud access needs an explicit tool-call + wall-time budget and a return-partial-on-exhaustion instruction, or it runs 20–40min and can lose its whole output. |

### E. Squash/merge mechanics — *the gotchas at PR-land time*

The squash/merge mechanics that bite when multiple PRs converge on the same branch.

| Skill | Role |
|---|---|
| [**gh-squash-merge-closes-only-one-issue**](plugins/agent-traffic-control/skills/gh-squash-merge-closes-only-one-issue/) | GitHub squash-merge auto-closes only ONE issue per PR — the rest stay OPEN even with `Closes #X, #Y, #Z`. Path A prevents (one keyword per issue: `Closes #X. Closes #Y.`); Path B recovers (find + close the orphans). |
| [**prep-pr-close-keyword-auto-closes-issue**](plugins/agent-traffic-control/skills/prep-pr-close-keyword-auto-closes-issue/) | A prep/scaffolding PR with a `Closes #X` keyword auto-closes the issue on merge — even though the feature isn't done. Use `Refs #X` for prep PRs; reserve `Closes` for the PR that actually ships the feature. |
| [**pr-followup-commit-stranded-after-squash**](plugins/agent-traffic-control/skills/pr-followup-commit-stranded-after-squash/) | Pushing a follow-up commit to a PR branch *after* the squash-merge lands the commit on a closed branch — never reaches main. Verify PR state before pushing; recover via fresh PR. |
| [**git-pull-after-squash-merge**](plugins/agent-traffic-control/skills/git-pull-after-squash-merge/) | After your PR squash-merges, `git pull` on the local feature branch leaves you in a confusing ahead+behind state. Reset to upstream main; don't try to reconcile. |
| [**stacked-pr-base-branch-deletion-auto-closes-dependent**](plugins/agent-traffic-control/skills/stacked-pr-base-branch-deletion-auto-closes-dependent/) | When a stacked PR's base branch is deleted (or auto-deleted by GitHub on merge), the dependent PR auto-closes — even if it had unmerged code. Re-target before the base disappears. |
| [**merged-pr-not-deployed-gate-label-missing**](plugins/agent-traffic-control/skills/merged-pr-not-deployed-gate-label-missing/) | A merged PR doesn't ship because a deploy-gate label is missing — verify gate labels on merge, not just merge status. |
| [**squash-merge-content-preservation-vs-ancestor-check**](plugins/agent-traffic-control/skills/squash-merge-content-preservation-vs-ancestor-check/) | `git merge-base --is-ancestor` always fails after a squash even when content is preserved verbatim — verify by content, not ancestry. |
| [**working-tree-edits-stranded-on-squash-merge**](plugins/agent-traffic-control/skills/working-tree-edits-stranded-on-squash-merge/) | Edit/Write don't stage; an unstaged fix is lost on squash-merge ("fix not on main") — stage before the squash lands. |
| [**safe-bulk-worktree-branch-cleanup**](plugins/agent-traffic-control/skills/safe-bulk-worktree-branch-cleanup/) | Bulk-clean stale worktrees/branches gating deletion on PR state, not ancestry (`git branch --merged` lies after a squash). |
| [**gh-pr-merge-squash-stdout-shows-sibling-files-as-created**](plugins/agent-traffic-control/skills/gh-pr-merge-squash-stdout-shows-sibling-files-as-created/) | `gh pr merge --squash` prints an alarming diffstat with `create mode` lines for sibling-PR files merged to main after your branch point — verify against the squash commit, don't panic-revert. |
| [**solo-repo-branch-protection-stable-gate-and-self-merge**](plugins/agent-traffic-control/skills/solo-repo-branch-protection-stable-gate-and-self-merge/) | Configure branch protection on a solo-maintained repo so red changes can't reach main, without locking yourself out — stable aggregation gate vs matrix check names, require-PR, self-merge with zero reviewers. |

> **Note:** `gh-squash-merge-closes-only-one-issue` also ships in [dashboard-audit-toolkit](https://github.com/wan-huiyan/dashboard-audit-toolkit) (where it surfaces as the operational gotcha when shipping audit fix-bundles at scale). Both wrap the same canonical skill.

## When NOT to reach for this toolkit

- **Single-session work** with no parallel-agent risk. The protocols are overhead with no benefit.
- **Cross-team coordination across separate repos** (real merge-queue territory) — out of scope.

## Version history

- **v1.4.0** (2026-06-01) — Added 4 skills (2 to D. Subagent integrity: `code-review-subagent-fabricates-specifics-to-inflate-severity`, `db-access-review-subagent-needs-explicit-probe-budget`; 2 to E. Squash/merge mechanics: `gh-pr-merge-squash-stdout-shows-sibling-files-as-created`, `solo-repo-branch-protection-stable-gate-and-self-merge`) and expanded `multi-agent-skill-silent-phase-compression` with section 7 (forcing-function terminal-output row for droppable late steps in single-agent long skills). Total: 61 skills.
- **v1.3.0** (2026-05-29) — Added 24 skills (1 to A, 8 to B, 5 to C, 7 to D, 3 to E) drawn from the parallel-session / worktree / subagent-orchestration lesson backlog, and refreshed 6 existing skills with expanded content (`gh-pr-merge-worktree-checkout-trap`, `stacked-pr-base-branch-deletion-auto-closes-dependent`, `stale-base-pr-silently-reverts-upstream-content`, `subagent-pre-existing-misattribution`, `synthetic-id-collision-rebase`, `pr-followup-commit-stranded-after-squash`). Total: 57 skills.
- **v1.2.0** (2026-05-13) — Renamed repo `agent-squad-hr` → `agent-traffic-control`. Added 10 new skills (2 to A, 4 to B, 2 to C, 1 to D, 1 to E). Dropped `barryu-pr-conflict-site-regen` as too project-specific (the reusable kernel is already covered by `merge-conflict-generated-files`). Refreshed 3 existing skills with latest content. Total: 33 skills.
- **v1.1.0** (2026-05-08) — Merged the original `agent-traffic-control` content (E. Squash/merge mechanics, 4 skills) into this single bundle. One-shot install reads better than two sister marketplaces.
- **v1.0.0** (2026-05-08) — Initial release: 20 skills covering A–D buckets.

## Related

- **[dashboard-audit-toolkit](https://github.com/wan-huiyan/dashboard-audit-toolkit)** — synchronous end-to-end audit for live data dashboards. Pairs naturally with this toolkit when you ship audit fix-bundles via parallel PRs.
- **[overnight-workflows](https://github.com/wan-huiyan/overnight-workflows)** — autonomous overnight loops for review polishing and insight discovery.
- **`superpowers`** (Anthropic) — the `dispatching-parallel-agents` skill there pairs naturally with `gh-issue-claim-coordination` here.

## License

MIT — see [LICENSE](LICENSE).
