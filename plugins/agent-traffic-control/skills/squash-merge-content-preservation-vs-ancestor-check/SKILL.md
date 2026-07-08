---
name: squash-merge-content-preservation-vs-ancestor-check
description: |
  Use when verifying that an upstream commit (e.g., a colleague's work, a
  feature-branch commit) is preserved in a target branch after a propagation
  PR has merged — and the verification script uses
  `git merge-base --is-ancestor <upstream-sha> <target-branch>`. If the merge
  mode was **squash**, that ancestor check ALWAYS returns non-zero even when
  content is preserved verbatim, because squash collapses every commit into a
  single new SHA on the target. Apply this skill when: (1) preservation audit
  for a recently-merged propagation PR returns "MISSING" or non-zero exit on
  `git merge-base --is-ancestor`, (2) handoff prompt mixes `is-ancestor` AND
  content checks without specifying merge mode, (3) you need to gate a merge
  on "did colleague's signature work survive". The correct probe depends on
  merge mode — fast-forward / no-ff preserves lineage; squash does not.
version: 1.0.0
date: 2026-05-27
author: Huiyan / Claude Opus 4.7
disable-model-invocation: true
---

# Squash Merge Content Preservation vs Ancestor Check

## Problem

Your verification script says:

```bash
git merge-base --is-ancestor 0b6303e76 origin/main && echo "OK" || echo "MISSING"
# Prints: MISSING
```

… but `wc -l <signature-file>` returns the expected line counts and `grep -c
<signature-string>` returns ≥ the expected ref count. The exit code from
`is-ancestor` is non-zero **even though every byte of the upstream work is
preserved on the target branch**. The "MISSING" verdict is wrong.

Root cause: a squash merge collapses every commit on the source branch into a
**single new commit** on the target. The original SHAs (including the upstream
commit you're checking) never appear in the target's history. `is-ancestor`
returns "false" because the SHA truly isn't an ancestor of the merge commit —
but the SHA's *content* is preserved verbatim inside the squash commit.

This trap fires whenever:

- A handoff prompt or skill mixes ancestor-based checks with content-based
  checks for the same preservation claim
- The handoff was written before the merge mode was decided
- The verification template assumed fast-forward / no-ff (which preserves
  lineage) but the actual merge used squash

## Context / Trigger Conditions

You're in the right place if **all** of these are true:

- A propagation-style PR (`branch-A → branch-B`, often 20+ commits ahead) has
  recently merged
- The verification step instructs you to check `git merge-base --is-ancestor
  <upstream-sha> <target-branch>` AND content-level probes (line counts, grep
  ref counts, file existence)
- The ancestor probe returns non-zero / "MISSING" / exit 1
- The content probes all PASS (line counts match, ref counts ≥ expected,
  signature files exist)
- The PR's merge method was **squash** (check via `gh pr view <N> --json
  mergeCommit,mergedBy` — the merge commit's parent commits are NOT the source
  branch's tip)

The trap also applies in reverse direction: any check that asks "is this old
commit in our new history?" will fail for squash workflows.

## Solution

### Step 1 — Confirm the merge was a squash

```bash
gh pr view <PR-N> -R <owner>/<repo> --json mergeCommit
# Inspect: the merge commit has ONE parent (the previous target HEAD),
# NOT two parents (target HEAD + source branch tip). One-parent = squash;
# two-parents = no-ff merge.
```

Or in git:

```bash
git log -1 --format='%P' <merge-sha>
# One SHA printed = squash or fast-forward
# Two SHAs printed = no-ff or merge commit
```

If two-parent (no-ff/merge), `is-ancestor` SHOULD work — diagnose further
(maybe the SHA is wrong, or the target branch is stale).

### Step 2 — Replace ancestor checks with content-level checks

For the same preservation claim, swap to content probes:

```bash
# File existence + line count
for f in path/to/sig1.py path/to/sig2.py; do
  echo -n "$f: "
  git show origin/main:$f 2>/dev/null | wc -l
done
# Expect known line counts from the upstream work

# Grep ref count
git show origin/main:path/to/consumer.py | grep -c "<upstream-symbol>"
# Expect >= N from the upstream registration

# Byte-identical SHA on a known block (strongest proof — see
# `byte-identical-sha-gate-as-refactor-safety-net`)
for branch in origin/main <source-branch-pre-merge>; do
  git show $branch:path/to/registry.py | sed -n '<start>,<end>p' | sha256sum
done
# Two matching SHAs = block-level byte preservation proven
```

### Step 3 — Update the verification template

If a handoff prompt, runbook, or skill recommended the ancestor check
unconditionally, fork the recommendation on merge mode:

```markdown
**Verification depends on merge mode:**
- Fast-forward or no-ff merge → `git merge-base --is-ancestor <sha> <target>`
- **Squash merge** → ancestor check ALWAYS fails by design. Use content
  probes: file existence, line counts, grep ref counts, byte-identical SHA
  on signature blocks.
- Rebase merge → ancestor fails on original SHA but rebased equivalent may
  exist; use `git log --cherry-mark <target>...<source>` for definitive
  answer.
```

### Step 4 — When squash is the team default, default to content checks

If your team uses squash merge as the policy default (GitHub's "Squash and
merge" button), pre-write preservation audits using content checks only.
Don't write `is-ancestor` into the audit at all — it'll be wrong every time.

## Verification

A correct audit after squash propagation produces:

```
=== Katie preservation check ===
(a) ancestor check: SKIP (squash merge — see L-256)
(b) signature file line counts on origin/main:
google_trends_covariates.py: 703  ← matches expected
weather_covariates.py: 271         ← matches expected
validation_tests.py: 303           ← matches expected
(c) brand-share daily ref count on origin/main: 9  ← ≥ 5 expected
=== Verdict: content preserved ===
```

If `is-ancestor` is still in the script, mark it as expected-to-fail with a
comment, or delete it.

## Example

Session 72 (2026-05-27) propagated `chore/promote-release-uk-to-main → main`
via squash-merge (PR #146 → commit `abe1cad7`). The S72 prompt included this
verification block:

```bash
git merge-base --is-ancestor 0b6303e76 HEAD && echo "OK" || echo "MISSING"
wc -l webapp/google_trends_covariates.py  # expect 703
wc -l webapp/weather_covariates.py        # expect 271
wc -l webapp/validation_tests.py          # expect ~303
grep -c "google_trends_brand" webapp/research_utils.py  # expect >= 5
```

Post-merge result:

- Ancestor check: **MISSING** (0b6303e76 not in origin/main's history)
- Line counts: 703 / 271 / 303 ✓
- grep ref count: 9 ≥ 5 ✓

Initial reaction was confusion — was Katie's work clobbered? No. The squash
merge collapsed all 35 source-branch commits into the single new SHA
`abe1cad7`. Content preserved; lineage rewritten. The ancestor probe was the
wrong tool. Recovery: trust the content checks, update the verification
template (this skill + L-256 in lessons.md).

## Notes

- **Sister skill**: `byte-identical-sha-gate-as-refactor-safety-net` — when
  you want a stronger proof than line counts (block-level SHA equality
  between source and target).
- **Related**: `pre-merge-client-variant-regression-audit` Step 5 already
  uses byte-identical SHA for the right reason (regression detection on
  enrichment registration blocks). Apply the same content-only discipline
  to post-merge preservation audits.
- **Related**: `gh-squash-merge-closes-only-one-issue` — another
  squash-merge surprise (closes only one `Closes #N` issue per PR body).
- The bug isn't `is-ancestor` — it's mixing it with content checks under a
  single preservation claim without specifying merge mode. Either probe is
  fine when scoped to its merge-mode assumption.
- Some teams use `gh api PUT` with `merge_method=squash` to merge from
  worktree contexts (per `gh-pr-merge-worktree-checkout-trap`); when that's
  your default merge call, your verification templates MUST assume squash.

## References

- Git docs: [`git merge-base`](https://git-scm.com/docs/git-merge-base) —
  documents that `--is-ancestor` returns 0/1 based on commit-DAG reachability,
  not content equivalence.
- GitHub docs: [About merge methods](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-merge-methods-on-github)
  — squash merge collapses commits into one; "the commits on the head branch
  are not preserved in the history."
- Project memory: `~/.claude/projects/-Users-<user>-Documents-the-causal-impact-repo/memory/lessons.md` L-256.
