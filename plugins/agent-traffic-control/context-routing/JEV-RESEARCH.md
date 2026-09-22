# The Jev research strand: what is established, what is open, who owns it

**Owner: the repository owner, with Claude Code as the working session.** This strand was
opened by ChatGPT, which built the adapter, the shared engine and the evaluation design in
this pull request and its companion. Everything below that is marked ESTABLISHED was
re-derived here against the live service or the vendor's own pages, not carried over from the
pull request bodies. Everything marked OPEN is work nobody has done yet.

Read this before running anything against the provider. `context-routing/README.md` covers the
adapter; `docs/context-routing-evaluation.md` in the companion repository covers the frozen
A/B/C design this ledger tracks.

## What Jev is

`jev-1.13.0` is a third-party classification model from TypeSafe, called over HTTPS at
`POST https://api.typesafe.ai/v1/systemone` with a Bearer key in `TYPESAFE_API_KEY`. It answers
typed questions rather than generating text; the type used here is `noul`, a calibrated
probability in `[0, 1]`. The engine uses it for one job only — asking, per candidate record,
whether that record is needed for the task — and never for validity, supersession, permission
or ordering, which stay in deterministic code.

It is optional. The default route is local-only and shadow. Nothing in this plugin calls it
unless an operator passes `--jev` **and** has marked records `egress_approved` with a reviewed
`public_summary`.

## The ledger

| # | Question | Status | Evidence, or what blocks it | First executable step |
|---|---|---|---|---|
| 1 | Does the live API match `jev_provider.py`'s wire contract? | **ESTABLISHED** | Real call 2026-09-21: request `{model, state, questions}` → response `{model, answers.q0.{type,noul}, usage.{input_tokens,output_tokens}}`, exactly as the file expects. | — |
| 2 | Is a **pinned** version accepted as a request `model`? | **ESTABLISHED** | `jev-1.13.0` → HTTP 200, echoed back unchanged, so the file's strict `response["model"] == self.model` check passes. `jev-latest` also resolves to it. The Models page says versioned ids are accepted. This was the one question the pull request left genuinely open. | — |
| 3 | Does a dead pin fail loudly? | **ESTABLISHED** | `jev-9.9.9` → HTTP 400 `{"detail":{"error_type":"api_usage_error","message":"Unknown model: jev-9.9.9"}}`. No silent slide to a newer model. But see defect 1 below: the operator does not get to read that message. | — |
| 4 | What does a call cost? | **ESTABLISHED** | $42 per billion input tokens, $0.042 per million; **output tokens are free**. A routing call over 20 candidates measured 2,840–2,905 input tokens, so **about $0.00012 per call**. All live experimentation for this ledger cost about **$0.0025**. Cost is not a constraint on this research at any plausible size. | — |
| 5 | What are the service limits? | **ESTABLISHED** | 250,000 tokens/second and 1,200 requests/minute, which the vendor says can change without notice. 64k tokens per request; 32k for `state` plus the longest question. `MAX_REQUEST_BYTES = 48000` in `jev_provider.py` is **not** that boundary — it is a self-imposed byte cap, comfortably inside it. The companion has since documented which constants come from the vendor and which the file invented, which closes the half of this that was a documentation gap. | Replace the byte cap with a check against the documented token split, or add a comment saying it is deliberately conservative. |
| 6 | Latency | **ESTABLISHED** | 597–762 ms per routing call over 20 candidates, five samples. Add that to every turn the advisory runs on. | — |
| 7 | Does the adapter work on this repository at all? | **ESTABLISHED** | `index` produced 123 records (122 skills at the pull request's base plus the injected safeguard policy), 24 automatic / 99 manual-only, matching this repo's own tier gate. No manual-only skill was promoted. | — |
| 8 | Does the shipping safeguard fire on real input? | **ESTABLISHED, after a fix** | `next_action: merge` with no host observations → `status: preflight_required`, `authorizes_execution: false`, empty context, both expected findings, exit 2. It did **not** fire on `Merge`, `MERGE` or `merge ` — see defect 4 — which is fixed and regression-tested in this commit. | — |
| 9 | Can a privacy fallback be mistaken for a real Jev call? | **ESTABLISHED — no** | Three distinguishable states in `provider.status`: `not_requested`, `local_privacy_fallback` (`attempted: false`), `live` (with usage and latency). The output reports the effect, not the request. | — |
| 10 | **B-local arm** | **OPEN — first data exists** | A five-query smoke probe ran end to end. It is not a benchmark: the queries are not owner-reviewed frozen cases. Result in `JEV-FIRST-RUN.md`. | Freeze a real corpus (row 13), then `context_router_eval.py replay`. |
| 11 | **C-Jev arm** | **OPEN — first data exists** | Same probe, `--jev`, `provider.status: live` on every call. B and C selected the same set on 1 of 5 queries at the default budget. | Same corpus, `replay --jev`. |
| 12 | **A-native arm** | **BLOCKED on a human** | Nothing captured. This is the hard one: it needs real selections from a real Claude Code session on the same tasks, captured rather than authored. The evaluation doc is explicit that substituting "all installed skills" for the native selection is not allowed. | Decide the capture mechanism before the corpus is frozen — transcript inspection is the obvious candidate and nobody has confirmed it records what is needed. |
| 13 | A frozen, owner-reviewed corpus | **BLOCKED on a human** | Cannot be automated. Needs de-identified real cases, labelled required and forbidden ids, split by incident family, stored privately. | Pick ten real sessions and label them. Nothing downstream of this can start first. |
| 14 | Is the ranking method sound for this use? | **OPEN, with a vendor caveat against it** | The vendor states noul values **"aren't directly comparable across questions"**, and `rank()` builds its ranking key from exactly that — one separate question per candidate. Not fatal; it means a threshold tuned on one corpus must not be assumed to transfer. | Add an arm that asks one `choice` question over all candidates instead of N `noul` questions, and compare. |
| 15 | Does candidate count degrade accuracy? | **OPEN** | The vendor states unrelated detail acts as a distractor as `state` grows, and `rank()` puts up to 32 candidates in one `state`, so every per-candidate question sees all 32. The cap of 32 has no basis in the vendor's pages. | Run the same corpus at 8, 16 and 32 candidates per call. |
| 16 | Egress review | **BLOCKED on a human** | The guard is real: the engine refuses `egress_approved` without `reviewed: true`. Nobody has yet reviewed a real `public_summary` set. The 23 summaries used for the probe were this public repository's own skill descriptions, which is safe here and says nothing about private memories. | Review summaries per record before the combined private registry is ever used with `--jev`. |
| 17 | Measured main-model token and cache effect | **OPEN** | The whole justification for routing. Byte counts are exact bytes; no billed-token or cache claim has been measured, and the pull requests correctly make none. | Needs the host adapter named in the evaluation doc. Nothing exists for it yet. |
| 18 | macOS installed-host integration | **OPEN** | Everything so far ran from a checkout, not an installed plugin. | Install the plugin, point the adapter at the installed path, re-run rows 7–9. |

## Defects found while establishing the above

Each was reproduced before it was written down. **Defects 4, 5, 6, 8 and 9 are fixed and
regression-tested here.** Reverting any one of the six guards they add turns the suite red,
which was checked by reverting each in turn on a throwaway copy — 6 of 6 mutants killed, control
green. Defects 1, 2, 3 and 7 live in the companion repository and are recorded rather than
fixed, because changing a pinned file forces a re-pin and a separate review.

Severities were set by reviewers reading the code and then re-rated by a second pass that tried
to refute each one. **None is a blocker.** The adapter defaults to shadow, `--jev` and
`--mode active` are explicit opt-ins, and nothing here registers a hook — every defect below
needs an operator to switch something on first.

**In this repository — fixed here**

4. **The shipping preflight was skipped by a capital letter.** `SHIP_ACTIONS` was an
   exact-string membership test in `adapter.py:prepare_state`. Measured over fifteen values
   against the real 123-record registry: `push`, `merge`, `deploy`, `create-pr` produced
   `preflight_required` with two findings, and `Push`, `push ` (trailing space), `create_pr`,
   `squash-merge`, `force-push`, `commit` and `git push` each produced **`status: ok` with zero
   findings**. Be precise about what that cost: `authorizes_execution` stayed `false` on all
   fifteen and no hook output ever carried a permission decision, so **nothing was approved that
   would otherwise have been refused** — what was lost is the preflight warning, on a spelling of
   an action the README does name. Now normalised for comparison only; the engine still sees the
   caller's original string, because it reads `next_action` as free text for term matching and
   nothing else. An unrecognised action is still accepted silently rather than rejected, which
   is the residue and is recorded as open.
5. **A refused route had already called the provider and been billed for it.** `run()` called
   `core.route(..., provider=provider)` and only afterwards downgraded the result to
   `preflight_required`. Measured: `--jev` on a shipping action with unverified observations
   returned `status: preflight_required` **and** `provider.status: live` with 2,899 input tokens
   and 689 ms. What left the machine was the public task capsule and the approved candidate
   summaries and nothing else — no ids, paths, hashes or file bodies — so this is an unexpected
   billed call on a route the adapter itself declines, not a disclosure of unapproved material.
   It still has to stop: the refusal belongs before the egress, not after it. The provider is
   now dropped before the call when there are findings. Reaching it needed four opt-ins at once
   (`--jev`, per-record `egress_approved` with a reviewed `public_summary`, a `public_task` in
   state, and the API key), which is why it is here rather than at the top of the list.
6. **Unknown was treated as False on the isolation gate.** `state.get("writes_code") is True`
   skipped the dispatch isolation requirement whenever `writes_code` was absent or not a
   boolean — measured: `1`, `"true"` and `"yes"` all produced zero findings. The adapter's own
   README says host-observed fields are "not values to infer from the user's prompt", so absent
   has to mean unknown, and unknown has to fail closed. Now `is not False`, and `writes_code` is
   discarded on the prompt-hook path alongside the other saved observations, where a stale
   `false` would otherwise have skipped the gate on every later prompt. **The two halves only
   work together** — dropping the flag under the old identity test would have disabled the gate
   permanently instead of tightening it, which was checked by doing it.

8. **The hook's session binding was satisfied by two absences.** `payload.get("session_id") !=
   state.get("session_id") or payload.get("cwd") != state.get("worktree")` compares `None` with
   `None` when both sides omit a field, so a state file with no `worktree` key bound to any
   working directory. Both sides must now carry a non-empty string for both fields before the
   comparison is reached.

9. **The workflow's checkout ref is a second copy of `engine-lock.json`'s `companion_commit`,
   and nothing compared them.** Re-pinning one without the other is a silent split: the
   workflow would check out one revision and `load_engine` would refuse it with
   `shared_engine_digest_mismatch`. A test now asserts the two agree, and that the value is a
   full 40-character SHA. This was found the hard way — the re-pin in this commit had to change
   both by hand.

**In the companion repository — recorded, not fixed**

1. **A dead pin reports as a network problem, and it is two layers.** `jev_provider.py:_post`
   lets `urllib` raise `HTTPError` on a 4xx and `_evaluate` wraps every non-`ProviderError` as
   `transport_failure`, so a retired `jev-1.13.0` surfaces as an outage rather than the server's
   own `Unknown model`. Fixing only that is not enough: one layer up,
   `context_router.py` catches the `ProviderError` and reports
   `error_type: type(exc).__name__`, which is the literal string `"ProviderError"` for all seven
   distinct codes. `attempted` still separates the three pre-call causes from the four post-call
   ones, and `provider.status` is `fallback` rather than `live`, so a run that never reached the
   provider cannot be mistaken for one that did — what is lost is WHICH cause fired inside each
   bucket. Fix both layers or neither is visible — catch `urllib.error.HTTPError` and raise
   `ProviderError("api_error_" + str(code))` keeping the server's `error_type` (not its
   `message`, which could echo payload content), and carry the `ProviderError`'s own code
   through instead of its class name.
2. **`MAX_REQUEST_BYTES = 48000` is an invented number** presented like a contract limit. The
   documented boundary is a token split, not a byte count. See row 5.
3. **The 32-candidate cap is unexplained** and, past it, the candidates dropped from judging are
   chosen by id string rather than by relevance. See row 15.
7. **The audit path hardcodes `cost_unknown: true`**, so `audit --jev` with no API key reports
   spend that provably never happened.

## The one result that changes the evaluation design

At the adapter's **default `--budget-bytes 16000`, both arms miss most of the time, and the
cause is not ranking.** On a query whose answer is a live skill named for it, the engine ranked
that skill first and then dropped it, recording `optional_bundle_over_budget`, because its whole
bundle did not fit; it spent the budget on a lower-ranked one that did. Raising the budget to
48,000 took both arms from 3 of 10 arm-query pairs to 10 of 10.

Three consequences, and they are the reason to read `JEV-FIRST-RUN.md` before designing a run:

- Comparing B against C at the default budget measures the **budget**, not the ranker. Any A/B/C
  table has to fix the byte budget, report it, and sweep it as a first-class variable.
- The metric that separates the arms is **bytes-to-coverage**, not coverage alone. At 120,000
  bytes both arms find everything, but the Jev arm returns four to five records where the local
  arm returns ten to eleven. Same answer, less context. Score required coverage **at a matched
  byte budget**, and bytes needed to reach a fixed coverage.
- Choose the default budget from this repository's real bundle sizes before any arm is scored.
  It is a one-line change with more effect on the outcome than the choice of provider.

## Standing rules for this strand

- **Do not quote a figure from a pull request body.** Both bodies were written by a session that
  could not clone the full repositories and said so. Re-derive, or cite the run that produced it.
- **A fake transport proves the author agrees with themselves.** The companion's provider tests
  all use an injected fake shaped to pass its own validator. One recorded real response is worth
  more than ninety-three synthetic ones; rows 1 to 3 above are that recording.
- **Report what reached the provider, never what was requested.** `--jev` is a request;
  `provider.status: live` with a usage block is the effect. The engine already gets this right —
  keep it that way.
- **No token-savings claim without a measured main-model number.** Bytes are bytes.
