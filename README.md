# Agent Squad HR

A coordination toolkit of 20 [Claude Code](https://claude.com/claude-code) skills for **running multiple parallel sessions against the same repo without collisions, stranded work, or rebase loops** — issue-pickup claim protocol, worktree & session-isolation pitfalls, parallel-PR conflict recovery, and subagent-integrity edge cases.

[![license](https://img.shields.io/github/license/wan-huiyan/agent-squad-hr)](LICENSE)
[![last commit](https://img.shields.io/github/last-commit/wan-huiyan/agent-squad-hr)](https://github.com/wan-huiyan/agent-squad-hr/commits)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-orange)](https://claude.com/claude-code)

## When to reach for this toolkit

- You routinely run **2+ Claude Code sessions in parallel** against the same repo (worktrees, separate terminals, scheduled overnight loops, or sandbox + main).
- You've seen **two sessions independently start work on the same issue**, **PRs collide on rebase**, **subagent reports look complete but the PR never merged**, or **a worktree's index goes corrupt right after committing in a sibling**.
- You want **upstream prevention** at the issue-pickup boundary plus **downstream recovery** for the failure modes that still slip through.

If your problem is squash-merge mechanics specifically (auto-close limits, stranded follow-up commits, post-squash sync), see the sister marketplace **[agent-traffic-control](https://github.com/wan-huiyan/agent-traffic-control)**.

## The four buckets

The 20 plugins split into a **before / during / after / orchestrator-aware** arc:

### A. Pickup / claim coordination — *prevention*

Before any code is written, claim the issue so sibling sessions detect it and skip.

| Plugin | Role |
|---|---|
| [**gh-issue-claim-coordination**](plugins/gh-issue-claim-coordination/) | 60-second protocol: preflight (`gh issue view --json assignees,labels,updatedAt`) + atomic claim (`--add-assignee @me --add-label wip`) + 24h stale-claim sweep + label-drop on PR merge. Self-heals: idempotent `gh label create` runs every pickup. |

See also: [`superpowers:dispatching-parallel-agents`](https://github.com/anthropics/skills) — when to fan out vs. not (not bundled here; ships with the official `superpowers` plugin).

### B. Worktree & session isolation pitfalls

The cheap-isolation primitive (`git worktree`) has surprising failure modes when paired with parallel sessions, async post-commit hooks, and sibling subagents.

| Plugin | Role |
|---|---|
| [**using-git-worktrees**](plugins/using-git-worktrees/) | Create isolated worktrees with smart directory selection + safety verification — the right starting move for parallel feature work. |
| [**git-worktree**](plugins/git-worktree/) | General git-worktree workflow patterns. |
| [**gh-pr-merge-worktree-checkout-trap**](plugins/gh-pr-merge-worktree-checkout-trap/) | Diagnose `branch is checked out elsewhere` errors when merging a PR while the same branch is checked out in another worktree. |
| [**worktree-index-corrupt-async-post-commit-hook**](plugins/worktree-index-corrupt-async-post-commit-hook/) | Fix `fatal: unable to read <sha>` errors that surface in worktree B after committing in worktree A — when an async post-commit hook (`&` / `nohup`) is in play. |
| [**worktree-historical-test-replay-missing-dirs**](plugins/worktree-historical-test-replay-missing-dirs/) | When a historical test replay fails because directories that exist in HEAD don't exist at the older commit. |
| [**subagent-bash-cd-wrong-worktree**](plugins/subagent-bash-cd-wrong-worktree/) | Subagents inheriting the wrong CWD when dispatched from a worktree. |
| [**flask-debug-cross-worktree-edit-stale**](plugins/flask-debug-cross-worktree-edit-stale/) | Flask debug server reading stale code because the file you edited lives in a sibling worktree. |

### C. Parallel-PR conflict recovery — *after collision*

When two sessions DO collide (or an old PR drifts behind a fast-moving main), these resolve the rebase cleanly.

| Plugin | Role |
|---|---|
| [**barryu-pr-conflict-site-regen**](plugins/barryu-pr-conflict-site-regen/) | *In-house example* — resolve rebase conflicts limited to a generated dashboard site (regenerate playbook + ID-collision rename + recurring-rebase loop). Pattern generalizes to any `generate_*.py` + generated-HTML setup. |
| [**parallel-pr-template-fork-duplicates-moved-section**](plugins/parallel-pr-template-fork-duplicates-moved-section/) | Two PRs both move a template section — merge produces duplicates. Detect + dedupe. |
| [**parallel-pr-scope-overlap-tiebreaker-delta-check**](plugins/parallel-pr-scope-overlap-tiebreaker-delta-check/) | Two PRs claim overlapping scope — pick the winner via delta-check rather than first-merged. |
| [**pr-conflict-from-mid-flight-merges**](plugins/pr-conflict-from-mid-flight-merges/) | Mid-flight merges of unrelated PRs creating cascading conflicts on your branch. |
| [**synthetic-id-collision-rebase**](plugins/synthetic-id-collision-rebase/) | Two sessions both claimed the same numeric ID (tracker entry, ADR number, fixture row) — rename + propagate during rebase. |
| [**merge-conflict-generated-files**](plugins/merge-conflict-generated-files/) | Generated files (lock files, generated HTML, snapshot JSON) shouldn't be hand-merged — regenerate from the union of inputs. |

### D. Subagent integrity — *orchestrator-aware*

Subagents introduce their own coordination failure modes. These cover misattribution, incomplete reports, takeover during waits, silent phase compression, and credit-stall recovery.

| Plugin | Role |
|---|---|
| [**subagent-pre-existing-misattribution**](plugins/subagent-pre-existing-misattribution/) | Subagent claims credit for code that was already there before its dispatch. |
| [**subagent-reports-complete-but-pr-unmerged**](plugins/subagent-reports-complete-but-pr-unmerged/) | Subagent's "✅ done" doesn't mean the PR landed — verify merge state, not report state. |
| [**subagent-external-wait-orchestrator-takeover**](plugins/subagent-external-wait-orchestrator-takeover/) | When a subagent is blocked waiting on external state, the orchestrator can step in safely (or unsafely) — this skill covers the boundary. |
| [**multi-agent-skill-silent-phase-compression**](plugins/multi-agent-skill-silent-phase-compression/) | Multi-phase skills silently collapsing phases when the model decides the work was "small enough" — restoring phase boundaries. |
| [**multi-phase-skill-disk-reading-strategy**](plugins/multi-phase-skill-disk-reading-strategy/) | Late-pipeline subagents should read written files from disk, not pipe everything through the orchestrator's context. |
| [**credit-stall-mid-orchestration-revive-collision**](plugins/credit-stall-mid-orchestration-revive-collision/) | Reviving an orchestration after a credit stall — collision avoidance for in-flight work that may have continued. |

## When NOT to reach for this toolkit

- **Single-session work** with no parallel-agent risk. The protocols are overhead with no benefit.
- **Cross-team coordination across separate repos** (real merge-queue territory) — out of scope.
- **Squash-merge mechanics specifically** — see [agent-traffic-control](https://github.com/wan-huiyan/agent-traffic-control).

## Installation

```bash
# Add the marketplace
/plugin marketplace add wan-huiyan/agent-squad-hr

# Install the plugin — one shot, gets all 20 skills
/plugin install agent-squad-hr@wan-huiyan-agent-squad-hr
```

This is a single multi-skill plugin (modeled on `superpowers`), not a marketplace of individual plugins. One install gets you the full `before / during / after / orchestrator-aware` arc; you can't pick-and-choose per-skill via `/plugin install`. If you only want one or two of these skills, copy them directly into `~/.claude/skills/<skill-name>/` instead.

The marketplace name is `wan-huiyan-agent-squad-hr` (with the username prefix). The repo on GitHub is just `agent-squad-hr`.

## Related

- **[agent-traffic-control](https://github.com/wan-huiyan/agent-traffic-control)** — sister toolkit covering squash/merge mechanics in parallel-PR contexts (auto-close, stranded follow-ups, stacked-PR cascades, post-squash sync).
- **[dashboard-audit-toolkit](https://github.com/wan-huiyan/dashboard-audit-toolkit)** — synchronous end-to-end audit for live data dashboards.
- **[overnight-workflows](https://github.com/wan-huiyan/overnight-workflows)** — autonomous overnight loops for review polishing and insight discovery.
- **[superpowers](https://github.com/anthropics/skills)** (Anthropic) — the `dispatching-parallel-agents` skill there pairs naturally with `gh-issue-claim-coordination` here.

## License

MIT — see [LICENSE](LICENSE).
