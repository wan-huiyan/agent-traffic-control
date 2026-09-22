# First live run: the default byte budget dominates the arm difference

Run 2026-09-21 against this plugin's tree (122 skills at the pull request's base) and the
pinned companion engine `bf32ef4`. Real key, real Jev calls. Ledger and standing rules in
[`JEV-RESEARCH.md`](JEV-RESEARCH.md).

**This is a smoke probe, not a benchmark.** The five queries are the session's own, not
owner-reviewed frozen cases, and they were written by someone who knew the catalogue. The
evaluation document's freeze-first rule still applies in full. What follows is strong enough to
change what the real evaluation should measure, and not strong enough to say anything about
Jev's quality.

## What was run

```sh
ENGINE=<memory-hygiene@bf32ef4>/plugins/memory-hygiene/scripts
ATC=<checkout>/plugins/agent-traffic-control
# Egress overlay: the 23 live skills only. public_summary is each skill's own public
# frontmatter description. The engine REFUSES egress_approved without reviewed: true
# ("egress_requires_reviewed_summary"), which is the right guard and was hit first try.
python "$ATC/context-routing/adapter.py" --engine "$ENGINE" --root "$ATC" \
  index --metadata egress-meta.json > registry.json
python "$ATC/context-routing/adapter.py" --engine "$ENGINE" --root "$ATC" \
  route --registry registry.json --state state.json --budget-bytes 48000 --jev
```

Provider block on every live call:

```json
"provider": {"status":"live","attempted":true,"resolved_model":"jev-1.13.0",
             "usage":{"input_tokens":2856,"output_tokens":354},
             "cost_unknown":false,"latency_ms":597.115}
```

2,840–2,905 input tokens and 597–762 ms per routing call over 20 candidates. At the published
price that is about $0.00012 a call.

## The result

A hit means the arm selected the skill that is plainly the right answer for the query. One
query (a commit stranded by a squash-merge) has no exact skill, so
`pr-conflict-from-mid-flight-merges` is scored as its hit.

| `--budget-bytes` | B-local hits | C-Jev hits | typical selection size |
|---|---|---|---|
| **16,000 — the adapter's default** | **2 / 5** | **1 / 5** | 1–2 records |
| 48,000 | 5 / 5 | 5 / 5 | 3–4 records |
| 120,000 | 5 / 5 | 5 / 5 | B 10–11, **C 4–5** |

## Why the default misses, in the engine's own words

On the query *"my pull request was clean this morning and now GitHub says it has conflicts;
other PRs landed on main while it was open"*, the `reasons` map reads:

```
".../pr-conflict-from-mid-flight-merges/SKILL.md": "optional_bundle_over_budget"
".../gh-pr-pickup-designated-branch-supersede/SKILL.md": "local_match_complete_bundle"
```

`pr-conflict-from-mid-flight-merges` — the skill written for exactly that question — was the
**first-ranked candidate**. It was dropped because its whole bundle did not fit, and a
lower-ranked one that did fit was taken instead: `proposed_context_bytes: 15615` against
`budget_bytes: 16000`. The router found the right answer and spent its budget on a worse one.

The instrumentation is honest — the reason is recorded, and the evaluation document already
says to report candidate recall separately from final coverage. But a caller that reads
`selected_ids` and nothing else gets a confident wrong answer with no sign that the best match
was dropped for size.

**This repository's skill bodies are long.** Measured through the engine's own renderer: the
mandatory safeguard record is 1,848 bytes, the **median skill 10,156**, the largest 22,940, and
**11 skills exceed the whole 16,000-byte budget on their own**. So a typical route gets the
guard plus one skill — not always: 595 of the 7,381 possible skill pairs do fit alongside the
guard, and 16 triples do. The point stands in the weaker and true form: at this default the
20-candidate ranking must not be read as 20 selectable records, and the default is a
memory-store default applied to a skill store.

One thing this is **not**: a bug in the packing. When a *required* bundle overflows, the engine
returns `blocked` with `protected_overflow` and exit 2, which `safeguards.md` asks for in
writing — "a protected bundle that exceeds the budget needs explicit resolution, not silent
truncation". The behaviour above is the *optional* path, where dropping over-budget candidates
is correct and the only thing missing is that `selected_ids` alone does not say it happened.

## Verified clean, so nobody redoes it

- `index` on the real tree: 123 records (122 skills plus the injected safeguard policy),
  24 automatic / 99 manual-only, matching this repo's own tier gate. No manual-only skill
  promoted.
- The shipping safeguard fires on real input: `next_action: merge` with no host observations
  returns `preflight_required`, `authorizes_execution: false`, empty context, exit 2. It did
  **not** fire on `Merge`, `MERGE` or `merge ` — the action list was an exact-string membership
  test — and it did not stop `--jev` from completing its outbound call first. Both are fixed
  and regression-tested in the same commit as this file; see the defects section of
  [`JEV-RESEARCH.md`](JEV-RESEARCH.md).
- `--jev` reports the effect, not the request: `not_requested` / `local_privacy_fallback`
  (`attempted: false`) / `live` with usage and latency are three distinguishable states.
- On a complete checkout the suite is **24 of 24 passing**. The pull request body's
  "23 passed, 1 explicitly skipped" was a property of the environment it was written in, not
  of the tests.
