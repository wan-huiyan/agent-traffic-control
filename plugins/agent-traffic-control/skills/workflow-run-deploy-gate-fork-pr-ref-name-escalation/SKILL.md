---
name: workflow-run-deploy-gate-fork-pr-ref-name-escalation
description: |
  Security trap when authoring/reviewing a GitHub Actions deploy (or any privileged job)
  triggered by `on: workflow_run` and gated on the triggering run's BRANCH NAME. Use when:
  (1) a `workflow_run` job gates on `github.event.workflow_run.head_branch == 'main'`
  (or conclusion == 'success') to decide a privileged deploy / publish / OIDC-cloud action,
  (2) you are wiring CI-gated auto-deploy-on-merge ("deploy after the CI workflow passes on main"),
  (3) reviewing a workflow that mints cloud creds (WIF/OIDC, `id-token: write`) off a `workflow_run`
  event. The trap: `head_branch` is the UNQUALIFIED ref name, and a FORK's default branch is also
  named `main`. A fork-PR's CI run (event `pull_request`) can complete `success` with
  `head_branch=='main'`; the upstream `workflow_run` deploy then runs in the PRIVILEGED upstream
  context and ships the fork's `head_sha` to prod. The "fork CI can't read secrets/OIDC" intuition
  is a trap — that's the CI job; the deploy is a SEPARATE privileged job. Fix: also gate on the
  triggering run's ORIGIN — `workflow_run.event == 'push'` AND
  `workflow_run.head_repository.full_name == github.repository`. Unreachable on a private repo today,
  but one-line fix + future-proofs a visibility flip.
author: Claude Code
version: 1.0.0
date: 2026-06-09
disable-model-invocation: true
---

# `workflow_run` deploy gate: don't trust the ref *name* (fork-PR escalation)

## Problem

You want **auto-deploy after CI passes on main** without a plain `push` trigger (e.g. so a red-CI
merge can't ship, while the required-CI *merge* gate is deferred). The idiomatic shape is:

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
jobs:
  deploy:
    if: >-
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_branch == 'main'      # ⚠️ ref NAME only
    permissions: { contents: read, id-token: write }       # WIF / OIDC → prod
```

This is exploitable. `workflow_run.head_branch` is the **unqualified ref name**, and **a fork's
default branch is also `main`**. A `workflow_run`-triggered job runs in the **privileged upstream
context** (upstream secrets / OIDC), *regardless of where the triggering run came from* — that is
the inherent `workflow_run` hazard.

**Attack path (public repo):** fork → open PR from `attacker-fork:main` → `upstream:main`. The
fork's CI (`on: pull_request`) runs in the fork's *unprivileged* context, completes `success`, with
`head_branch == 'main'`. The upstream deploy `workflow_run` job then fires privileged, checks out the
attacker's `head_sha`, and builds+deploys attacker code to prod via the WIF/deploy SA.

**The intuition that bites you:** "fork CI can't access OIDC/secrets, so this is safe." True of the
**CI** job. The **deploy** is a *separate* `workflow_run` job that runs privileged no matter the
trigger's origin. Conclusion + branch-name are necessary but **not sufficient**.

## Context / Trigger conditions

- A workflow with `on: workflow_run` whose job `if:` gates a **privileged** action (deploy, publish,
  release, `gcloud`/`aws`/`az` with WIF/OIDC, `npm publish`, image push) on
  `workflow_run.conclusion`/`head_branch` only.
- The triggering CI workflow also runs on `pull_request` (so fork PRs produce CI runs).
- Reviewing/authoring "deploy after CI succeeds on main" / "CI-gated auto-deploy-on-merge".

## Solution

Gate on the triggering run's **origin**, not just its name/conclusion. Add BOTH:

```yaml
    if: >-
      github.event_name == 'workflow_dispatch' ||
      (github.event.workflow_run.conclusion == 'success' &&
       github.event.workflow_run.head_branch == 'main' &&
       github.event.workflow_run.event == 'push' &&                               # (A)
       github.event.workflow_run.head_repository.full_name == github.repository)  # (B)
```

- **(A) `event == 'push'`** — a fork-PR CI run is `event == 'pull_request'`; only a *write-access*
  push to `main` (a merge or a direct push) is `event == 'push'`. This alone closes the fork path.
- **(B) `head_repository.full_name == github.repository`** — belt-and-suspenders: the CI run was on
  *our* repo, not a fork. (For a `push` event this is already true; keep it for defence-in-depth.)

Neither guard blocks a legitimate deploy: the only legit path is a push-to-main CI run on your own
repo. Deploy the **exact tested commit** (`workflow_run.head_sha`), not the branch tip.

**Note on scope:** the `workflow_run` *workflow file itself* is always taken from the **default
branch** (tamper-safe — a feature branch can't change the gate logic). But its *trigger* is not, so
you must gate the trigger's origin in the `if:`.

## Verification

- A fork PR (or any `pull_request` CI run) must NOT produce a deploy: the `workflow_run` run shows
  the gate job **skipped** (the `if:` is false). A non-success CI must also skip.
- A real merge to main → CI `success` (event `push`) → the `workflow_run` run is **created, not
  skipped** → gate + deploy jobs run. (A run that is "pending"/"in_progress" rather than immediately
  "skipped" means the `if:` passed.)
- Confirm origin filtering in the run's event payload, or by attempting a same-name branch on a fork
  in a test repo. Don't conflate a `workflow_dispatch` or cancelled-CI run succeeding/ skipping with
  proof the gated push path works — see `deploy-gate-success-report-doesnt-prove-the-gated-path`.

## Example

Real incident (2026-06-09): a review panel flagged a CI-gated auto-deploy whose gate was
`conclusion=='success' && head_branch=='main'`. Repo was *private* (forks can't run CI without write
access → unreachable today), so one reviewer rated it P3; the security reviewer rated it a P1
ship-blocker on don't-trust-ref-name grounds. Fixed with guards (A)+(B) before merge — one-line `if:`
diff, future-proofs a private→public flip.

## Notes

- Also applies to **any** `workflow_run`-triggered privileged job, not just deploys (publish,
  release, signing, infra apply).
- Distinct from `pull_request_target` foot-guns (untrusted-code-with-secrets) — same threat *class*
  (privileged context + attacker-influenced ref), different trigger.
- See also: `label-gated-deploy-pull-request-closed-needs-branches-filter` (the sibling trigger-trap
  on `pull_request: closed` — a label-gated deploy needs a `branches:[main]` filter); 
  `deploy-gate-success-report-doesnt-prove-the-gated-path` (verify the *gated* path actually ran,
  not a happy-path/dispatch success); `gha-auto-deploy-never-ran-skipped-mask` (a gated workflow
  showing "skipped" can mask a deploy that never successfully ran).

## References

- GitHub Actions — `workflow_run` event runs from the default branch with read/write `GITHUB_TOKEN`
  by default; the triggering run's `head_branch`/`head_repository`/`event` are in
  `github.event.workflow_run.*`. (GitHub Actions docs: "Events that trigger workflows → workflow_run";
  "Security hardening for GitHub Actions".)
