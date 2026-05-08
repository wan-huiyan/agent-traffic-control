# Agent Squad HR

A coordination toolkit of 24 [Claude Code](https://claude.com/claude-code) skills for **running multiple parallel sessions against the same repo without collisions, stranded work, or rebase loops** — issue-pickup claim protocol, worktree & session-isolation pitfalls, parallel-PR conflict recovery, subagent-integrity edge cases, and the squash/merge mechanics that bite when multiple PRs converge on the same branch.

[![license](https://img.shields.io/github/license/wan-huiyan/agent-squad-hr)](LICENSE)
[![last commit](https://img.shields.io/github/last-commit/wan-huiyan/agent-squad-hr)](https://github.com/wan-huiyan/agent-squad-hr/commits)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-orange)](https://claude.com/claude-code)

## When to reach for this toolkit

- You routinely run **2+ Claude Code sessions in parallel** against the same repo (worktrees, separate terminals, scheduled overnight loops, or sandbox + main).
- You've seen **two sessions independently start work on the same issue**, **PRs collide on rebase**, **subagent reports look complete but the PR never merged**, **a worktree's index goes corrupt right after committing in a sibling**, or **GitHub squash-merge auto-closes only one issue out of three you listed in the PR body**.
- You want **upstream prevention** at the issue-pickup boundary plus **downstream recovery** for the failure modes that still slip through.

## Installation

```bash
# Add the marketplace
/plugin marketplace add wan-huiyan/agent-squad-hr

# Install the plugin — one shot, gets all 24 skills
/plugin install agent-squad-hr@wan-huiyan-agent-squad-hr
```

This is a single multi-skill plugin (modeled on `superpowers`), not a marketplace of individual plugins. One install gets you the full `before / during / after / orchestrator-aware / merge-mechanics` arc; you can't pick-and-choose per-skill via `/plugin install`. If you only want one or two of these skills, copy them directly into `~/.claude/skills/<skill-name>/` instead.

## The five buckets

The 24 skills split into a **before / during / after / orchestrator-aware / merge-mechanics** arc:

### A. Pickup / claim coordination — *prevention*

Before any code is written, claim the issue so sibling sessions detect it and skip.

| Skill | Role |
|---|---|
| [**gh-issue-claim-coordination**](plugins/agent-squad-hr/skills/gh-issue-claim-coordination/) | 60-second protocol: preflight (`gh issue view --json assignees,labels,updatedAt`) + atomic claim (`--add-assignee @me --add-label wip`) + 24h stale-claim sweep + label-drop on PR merge. Self-heals: idempotent `gh label create` runs every pickup. |

See also: `superpowers:dispatching-parallel-agents` — when to fan out vs. not (not bundled here; ships with the official `superpowers` plugin).

### B. Worktree & session isolation pitfalls

The cheap-isolation primitive (`git worktree`) has surprising failure modes when paired with parallel sessions, async post-commit hooks, and sibling subagents.

| Skill | Role |
|---|---|
| [**using-git-worktrees**](plugins/agent-squad-hr/skills/using-git-worktrees/) | Create isolated worktrees with smart directory selection + safety verification — the right starting move for parallel feature work. |
| [**git-worktree**](plugins/agent-squad-hr/skills/git-worktree/) | General git-worktree workflow patterns. |
| [**gh-pr-merge-worktree-checkout-trap**](plugins/agent-squad-hr/skills/gh-pr-merge-worktree-checkout-trap/) | Diagnose `branch is checked out elsewhere` errors when merging a PR while the same branch is checked out in another worktree. |
| [**worktree-index-corrupt-async-post-commit-hook**](plugins/agent-squad-hr/skills/worktree-index-corrupt-async-post-commit-hook/) | Fix `fatal: unable to read <sha>` errors that surface in worktree B after committing in worktree A — when an async post-commit hook (`&` / `nohup`) is in play. |
| [**worktree-historical-test-replay-missing-dirs**](plugins/agent-squad-hr/skills/worktree-historical-test-replay-missing-dirs/) | When a historical test replay fails because directories that exist in HEAD don't exist at the older commit. |
| [**subagent-bash-cd-wrong-worktree**](plugins/agent-squad-hr/skills/subagent-bash-cd-wrong-worktree/) | Subagents inheriting the wrong CWD when dispatched from a worktree. |
| [**flask-debug-cross-worktree-edit-stale**](plugins/agent-squad-hr/skills/flask-debug-cross-worktree-edit-stale/) | Flask debug server reading stale code because the file you edited lives in a sibling worktree. |

### C. Parallel-PR conflict recovery — *after collision*

When two sessions DO collide (or an old PR drifts behind a fast-moving main), these resolve the rebase cleanly.

| Skill | Role |
|---|---|
| [**barryu-pr-conflict-site-regen**](plugins/agent-squad-hr/skills/barryu-pr-conflict-site-regen/) | Generated-site rebase playbook (regenerate-from-source playbook + ID-collision rename + recurring-rebase loop). Pattern generalizes to any `generator.py` + generated-HTML setup. (Skill slug retains the historical `barryu-` prefix from where it was extracted; methodology is now generic.) |
| [**parallel-pr-template-fork-duplicates-moved-section**](plugins/agent-squad-hr/skills/parallel-pr-template-fork-duplicates-moved-section/) | Two PRs both move a template section — merge produces duplicates. Detect + dedupe. |
| [**parallel-pr-scope-overlap-tiebreaker-delta-check**](plugins/agent-squad-hr/skills/parallel-pr-scope-overlap-tiebreaker-delta-check/) | Two PRs claim overlapping scope — pick the winner via delta-check rather than first-merged. |
| [**pr-conflict-from-mid-flight-merges**](plugins/agent-squad-hr/skills/pr-conflict-from-mid-flight-merges/) | Mid-flight merges of unrelated PRs creating cascading conflicts on your branch. |
| [**synthetic-id-collision-rebase**](plugins/agent-squad-hr/skills/synthetic-id-collision-rebase/) | Two sessions both claimed the same numeric ID (tracker entry, ADR number, fixture row) — rename + propagate during rebase. |
| [**merge-conflict-generated-files**](plugins/agent-squad-hr/skills/merge-conflict-generated-files/) | Generated files (lock files, generated HTML, snapshot JSON) shouldn't be hand-merged — regenerate from the union of inputs. |

### D. Subagent integrity — *orchestrator-aware*

Subagents introduce their own coordination failure modes. These cover misattribution, incomplete reports, takeover during waits, silent phase compression, and credit-stall recovery.

| Skill | Role |
|---|---|
| [**subagent-pre-existing-misattribution**](plugins/agent-squad-hr/skills/subagent-pre-existing-misattribution/) | Subagent claims credit for code that was already there before its dispatch. |
| [**subagent-reports-complete-but-pr-unmerged**](plugins/agent-squad-hr/skills/subagent-reports-complete-but-pr-unmerged/) | Subagent's "✅ done" doesn't mean the PR landed — verify merge state, not report state. |
| [**subagent-external-wait-orchestrator-takeover**](plugins/agent-squad-hr/skills/subagent-external-wait-orchestrator-takeover/) | When a subagent is blocked waiting on external state, the orchestrator can step in safely (or unsafely) — this skill covers the boundary. |
| [**multi-agent-skill-silent-phase-compression**](plugins/agent-squad-hr/skills/multi-agent-skill-silent-phase-compression/) | Multi-phase skills silently collapsing phases when the model decides the work was "small enough" — restoring phase boundaries. |
| [**multi-phase-skill-disk-reading-strategy**](plugins/agent-squad-hr/skills/multi-phase-skill-disk-reading-strategy/) | Late-pipeline subagents should read written files from disk, not pipe everything through the orchestrator's context. |
| [**credit-stall-mid-orchestration-revive-collision**](plugins/agent-squad-hr/skills/credit-stall-mid-orchestration-revive-collision/) | Reviving an orchestration after a credit stall — collision avoidance for in-flight work that may have continued. |

### E. Squash/merge mechanics — *the gotchas at PR-land time*

The squash/merge mechanics that bite when multiple PRs converge on the same branch — added in v1.1.0 (originally shipped as a separate `agent-traffic-control` marketplace, now folded in here for one-shot install).

| Skill | Role |
|---|---|
| [**gh-squash-merge-closes-only-one-issue**](plugins/agent-squad-hr/skills/gh-squash-merge-closes-only-one-issue/) | GitHub squash-merge auto-closes only ONE issue per PR — the rest stay OPEN even with `Closes #X, #Y, #Z`. Path A prevents (one keyword per issue: `Closes #X. Closes #Y.`); Path B recovers (find + close the orphans). |
| [**pr-followup-commit-stranded-after-squash**](plugins/agent-squad-hr/skills/pr-followup-commit-stranded-after-squash/) | Pushing a follow-up commit to a PR branch *after* the squash-merge lands the commit on a closed branch — never reaches main. Verify PR state before pushing; recover via fresh PR. |
| [**git-pull-after-squash-merge**](plugins/agent-squad-hr/skills/git-pull-after-squash-merge/) | After your PR squash-merges, `git pull` on the local feature branch leaves you in a confusing ahead+behind state. Reset to upstream main; don't try to reconcile. |
| [**stacked-pr-base-branch-deletion-auto-closes-dependent**](plugins/agent-squad-hr/skills/stacked-pr-base-branch-deletion-auto-closes-dependent/) | When a stacked PR's base branch is deleted (or auto-deleted by GitHub on merge), the dependent PR auto-closes — even if it had unmerged code. Re-target before the base disappears. |

> **Note:** `gh-squash-merge-closes-only-one-issue` also ships in [dashboard-audit-toolkit](https://github.com/wan-huiyan/dashboard-audit-toolkit) (where it surfaces as the operational gotcha when shipping audit fix-bundles at scale). Both wrap the same canonical skill.

## When NOT to reach for this toolkit

- **Single-session work** with no parallel-agent risk. The protocols are overhead with no benefit.
- **Cross-team coordination across separate repos** (real merge-queue territory) — out of scope.

## Version history

- **v1.1.0** (2026-05-08) — Merged the `agent-traffic-control` content (E. Squash/merge mechanics, 4 skills) into this single bundle. Was originally split as a sister marketplace; one-shot install reads better. The standalone `agent-traffic-control` repo has been retired.
- **v1.0.0** (2026-05-08) — Initial release: 20 skills covering A–D buckets.

## Related

- **[dashboard-audit-toolkit](https://github.com/wan-huiyan/dashboard-audit-toolkit)** — synchronous end-to-end audit for live data dashboards. Pairs naturally with this toolkit when you ship audit fix-bundles via parallel PRs.
- **[overnight-workflows](https://github.com/wan-huiyan/overnight-workflows)** — autonomous overnight loops for review polishing and insight discovery.
- **`superpowers`** (Anthropic) — the `dispatching-parallel-agents` skill there pairs naturally with `gh-issue-claim-coordination` here.

## License

MIT — see [LICENSE](LICENSE).
