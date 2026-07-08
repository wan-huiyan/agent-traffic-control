---
name: code-review-subagent-fabricates-specifics-to-inflate-severity
description: |
  When a code-review subagent (voltagent-qa-sec, opus-tier reviewer, code-reviewer,
  etc.) reports a HIGH or BLOCKING severity finding, verify any SPECIFIC EVIDENCE
  the reviewer cites (line numbers, call counts, exact function/symbol names,
  file paths beyond the obvious diff) BEFORE treating the severity as actionable.
  Use when: (1) a single-run code-review subagent returns a BLOCKING/HIGH finding
  justified by concrete numeric evidence like "there are EXACTLY 4 calls at lines
  3174, 3230, 3251" or "this affects N files across the repo"; (2) the principle
  of the finding sounds plausible but you didn't immediately recall the specific
  symbols cited; (3) you're under time pressure to merge and the BLOCKING tag is
  the only thing holding you back; (4) the reviewer used opus tier and the
  confident, specific framing is reading as authoritative; (5) you notice the
  reviewer's grep would have been trivial (`grep -c "flash.*warning" foo.py`)
  but the report itself shows no evidence of grep output, only the assertion.
  Symptom: the general concern is real (e.g. "defensive coding for future X")
  but the specific blast radius is invented. Action: run the 30-second
  grep/count, and if the cited specifics are zero, DEMOTE severity from
  BLOCKING/HIGH to MEDIUM-defensive — the fix may still be worth applying as
  hardening, but it's not release-gating. Distinguishes from:
  agent-review-panel-stale-cite-verification (about carry-over cites going
  stale across Run N≥2), factcheck-subagent-needs-complete-sources (about
  the dispatcher's incomplete prompt), task-framing-claims-need-subagent-grep-verify
  (about subagent verifying the dispatcher's claims). This skill specifically
  covers a SINGLE subagent's FIRST run inventing specifics to inflate its own
  finding.
author: Claude Code
version: 1.0.0
date: 2026-05-29
disable-model-invocation: true
---

# Code-Review Subagents Fabricate Specific Evidence to Inflate Severity

## Problem

A code-review subagent — especially a high-tier one (opus, voltagent-qa-sec,
single-agent-multi-persona) — returns a report with a BLOCKING or HIGH-severity
finding that reads as airtight: the issue is named, the call sites are
enumerated, exact line numbers are cited, the blast radius is quantified. The
orchestrator sees the specificity and treats the severity as authoritative,
because nobody fabricates line numbers, right?

But a model fabricating coherent, specific-looking evidence to justify a
high-stakes call IS exactly what happens. The reviewer's general principle is
often correct (e.g. "defensive coding for future X is wise"), but the SPECIFIC
EVIDENCE cited to inflate the severity from MEDIUM to BLOCKING — the call
counts, the line numbers, the affected-file list — is invented. A 30-second
grep would falsify it.

This is the **inverse asymmetry** of the well-known "reviewers miss things"
problem. Reviewers don't just miss things; they also confabulate specifics to
justify the severity they want to assign. Specificity reads as rigor. The
fix is independent verification of the specifics — not just the principle.

## Context / Trigger Conditions

Trigger this skill when:

1. **A single-run code-review subagent returns a BLOCKING/HIGH finding
   justified by concrete numeric evidence** like "there are 4 active calls at
   lines 3174, 3230, 3251" or "this affects N templates across the repo".
   The numeric specificity is the tell.

2. **The reviewer ran with opus/high-tier model** and the confident framing
   is reading as authoritative. Higher-capability models produce more
   convincing fabrications, not fewer.

3. **You're under time pressure to merge** and the BLOCKING tag is the only
   thing standing between you and ship. The pressure makes you want to fix
   first and verify never — exactly when verification matters most.

4. **The reviewer's grep would have been trivial** (`grep -c "flash.*warning"
   webapp/views/analysis.py`, `gh issue list --label X | wc -l`) but the
   report shows no evidence of grep output, only the assertion. A real
   reviewer who actually ran the grep would have pasted the output.

5. **The general principle of the finding is sound** but you didn't
   immediately recall the specific symbols cited from your own work on
   the diff. That gap is suspicious — if the bug were real, you would
   often remember writing the code being criticized.

6. **The reviewer is asserting absence/presence at a specific line** — "at
   line 3174 you have a `flash(..., 'warning')` that..." Line-specific
   claims about CALL SITES are the most fabrication-prone variant because
   the reviewer has to invent both the location AND the content.

## Solution

### Step 1: Identify the load-bearing specifics

For each HIGH/BLOCKING finding, list every SPECIFIC, FALSIFIABLE claim:

- Line numbers (e.g. "line 3174")
- Call/site counts (e.g. "4 active calls", "5+ existing patterns")
- Exact function/symbol names (e.g. "in `_helper_foo` at...")
- File path lists ("affects A, B, C")
- Class/category claims ("the codebase uses `warning` category")

If a finding has NO specific falsifiable claims — only principle ("this
pattern could break under condition X") — there's nothing to verify.
Treat it as a principle-level finding and judge it on its merits.

### Step 2: Run the 30-second grep BEFORE acting

Verify the specifics. The grep is usually one line:

```bash
# "There are 4 flash(..., 'warning') calls at lines 3174, 3230, 3251"
grep -n 'flash([^)]*"warning"' webapp/views/analysis.py
# → 0 results. Reviewer fabricated the calls.

# "This affects 15 templates across the repo"
grep -l "pattern" webapp/templates/*.html | wc -l
# → 2 templates. Reviewer inflated by 7.5x.

# "Line 3174 contains the broken handler"
awk 'NR==3174' webapp/views/foo.py
# → empty line. Or completely unrelated code.
```

### Step 3: Reclassify based on what verification reveals

| Verification result | Action |
|---|---|
| All specifics check out | Treat as graded — the BLOCKING is real. |
| Principle valid, specifics fabricated/inflated | **Demote severity** to MEDIUM-defensive. Apply the fix as hardening, but DON'T treat it as release-gating. Note the fabrication in the commit/PR body so the next reviewer doesn't repeat the mistake. |
| Specifics check out but principle was misapplied | Address narrowly (the specific case the reviewer found). Don't generalize beyond what the grep proved. |
| Both wrong | Drop the finding entirely. Note in the orchestration log so the reviewer's calibration is tracked. |

### Step 4: Document the asymmetry in the commit

When you demote a finding, say so explicitly:

```
B1 → demoted to MEDIUM-defensive (audited: there are ZERO `flash(...,
"warning")` calls in the codebase today, so the described live blast
radius doesn't exist). Still applying the defensive fix: ...
```

This serves two purposes:
- Future you (or another reviewer reading the PR history) sees the
  reviewer's specifics were checked, not blindly trusted.
- The pattern accumulates evidence over time about which reviewer
  configurations confabulate most.

## Verification

The skill itself is meta-verifiable: count how often demoted findings
turn out to have been real after all (false negatives) vs. how often
you would have wasted time blocking on fabricated specifics (true
positives). On the session that motivated this skill, the demotion
was correct — the fix was worth applying as defensive hardening, but
not as a release blocker.

## Example

Real session (PR #206, fixing Flask `/retrieve` cold-GET routing):

**Opus reviewer's BLOCKING finding (excerpt):**

> 🚨 **B1. `flash(..., "warning")` calls render as success-green.**
> The new flash partial in `_base.html` only conditions CSS on `"error"` and
> `"info"`; *everything else* (including `"warning"` and `"success"`) falls
> through to green. The codebase has 4 active `flash(..., "warning")` calls
> in `webapp/views/analysis.py` (lines 3174, 3230, 3251, plus quick-validate
> paths) that warn about missing metrics or removed test types. They will
> now render as cheerful green "success" pills, actively misleading the user.

**30-second verification:**

```bash
$ grep -rn 'flash(' webapp/ --include="*.py" | \
    grep -oE 'flash\([^)]*"(error|info|warning|success|message)"' | \
    sort | uniq -c
```

Output showed: 21 `"error"`, 7 `"info"`, 1 `"success"`. **Zero `"warning"`**.
The cited lines (3174, 3230, 3251) existed in the file but contained
unrelated code.

**Decision:** demoted B1 from BLOCKING to MEDIUM-defensive. Applied the
fix anyway (the principle was sound — a future `warning` flash would
render green), but did not treat it as merge-gating. The PR body
explicitly noted: "the described live blast radius doesn't exist."

If I had treated B1 as a real BLOCKING, I would have:
- Felt urgent pressure to drop everything and fix
- Over-claimed the blast radius in the PR body ("fixed 4 silent bugs!")
- Reinforced the reviewer's confabulation pattern for future runs
- Possibly delayed the merge over a non-existent live bug

## Notes

- **High-tier models confabulate more convincingly, not less.** The opus
  reviewer in this session was excellent on every OTHER finding (H1-H5
  were all real and useful). The same model strength that produced
  rigorous H-tier findings also produced a confident fabrication. Don't
  assume "this reviewer was great, so this finding must be real."

- **The specificity itself is the warning sign.** A reviewer who writes
  "there might be other categories not handled" is reasoning. A reviewer
  who writes "there are exactly 4 calls at lines X, Y, Z" is either
  citing grep output (good) or fabricating (bad). The latter rarely
  includes the grep command they used.

- **The fix often IS still worth applying.** Don't throw out the
  finding's principle just because the specifics were wrong. Defensive
  coding for hypothetical future cases is often net-positive — just
  ship it at MEDIUM, not BLOCKING.

- **Related to but distinct from agent-review-panel-stale-cite-verification.**
  That skill covers carry-over P0/P1 from a prior Run N-1 whose code has
  since shifted. This skill covers a SINGLE reviewer's FIRST run inventing
  specifics that never existed. Same verification tool (grep), different
  trigger conditions.

- **Pairs with `subagent-pre-existing-misattribution`** — both are about
  reviewer claims that need independent verification. The pre-existing-
  misattribution case is about WHEN a failure was introduced; this skill
  is about WHETHER a cited code site exists at all.

- **Anti-pattern: "the reviewer might be right, let me just fix it to be
  safe."** That logic is exactly how confabulations get rewarded. Verify
  first, demote if appropriate, and tell the reviewer (via the prompt
  for next time, or via a calibration note in the orchestration log)
  that the specifics didn't check out.

## References

- Companion skills: `agent-review-panel-stale-cite-verification`,
  `factcheck-subagent-needs-complete-sources`,
  `task-framing-claims-need-subagent-grep-verify`,
  `subagent-pre-existing-misattribution`,
  `code-reviewer-subagent-no-bash-blocked-on-pr-diff`
- Originating session: PR #206 in <org>/the-causal-impact-repo (2026-05-29)
- Related concept: in psychometrics, "fluency" effects — confident,
  specific-sounding claims are over-trusted regardless of truth value.
  The fix is forced verification of the specifics, not trust calibration.
