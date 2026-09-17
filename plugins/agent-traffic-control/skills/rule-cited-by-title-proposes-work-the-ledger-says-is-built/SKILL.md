---
name: rule-cited-by-title-proposes-work-the-ledger-says-is-built
description: |
  A standing rule ("no change to X until the owner has reviewed Y") cited from its TITLE,
  its id, or a peer's paraphrase instead of its recorded body — so a session proposes
  building Y when the shared ledger already carries Y as built and waiting on a human. The
  second half is a vocabulary trap: a status word that means "built, unreviewed" is usually
  spelled `open` or `pending`, which in issue vocabulary means "not started", so the row
  that proves the work exists reads as proof it does not. Use when: (1) you are about to
  propose, plan, or dispatch work because a rule, decision, ruling or policy requires it;
  (2) you are writing a question, option or recommendation for the owner that offers to
  build something; (3) you learned the rule from its id, a title, a memory, or a relayed
  brief rather than by reading its own record; (4) a rule names a deliverable and you have
  not queried the ledger for it; (5) a ledger row's status is a bare word like `open` whose
  meaning you have not read from the ledger's own schema. Symptoms: an option card offering
  to produce an artifact that exists on disk; two artifacts answering one question; the
  owner replying "you already sent me this". The checks are cheap and exact — read the
  rule's body off the default branch, then query the ledger by the deliverable's id, topic
  and date, then `ls` the output path. NOT for a brief that was executed and never retired
  (that is executed-prompt-not-retired-sibling-redoes-it), NOT for a fix a sibling already
  shipped to production (verify-live-prod-before-shipping-superseded-fix), and NOT for an
  unexecuted brief whose premise drifted (handoff-prompt-stale-user-hint-newer-state).
version: 1.0.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---

# A rule cited by title proposes work the ledger says is already built

## Problem

A repo keeps its standing decisions and its deliverables in one **hand-edited,
machine-parseable ledger** — a tracker `data.js`, a registry, a manifest, a decisions
table. Decisions have ids. Artifacts have rows with a `status`. Both are read by every
session, which is the point of keeping them there.

A session reads a rule by its **id**:

```
d-the-threshold-is-charted-before-it-moves
```

That id is a complete sentence and it sounds like the whole rule. The session concludes:
any change to the threshold needs a chart of the outputs at each candidate value, and
nobody has charted them — so it writes the owner an option card offering to build exactly
that.

Two things were never read.

**The rule's own body**, which said the charts are required *and already commissioned*:

```
"ruling": "A change to the threshold ships with the outputs charted at each candidate
           value, reviewed by me before the value moves. Commissioned 2026-08-30."
```

**The artifact rows**, which carried the deliverable twice:

```json
{"id": "a-threshold-chart-2026-08-30", "path": "docs/deliverables/threshold_chart_2026-08-30.html",
 "status": "open"}
{"id": "a-threshold-chart-2026-09-05",  "path": "docs/deliverables/threshold_chart_2026-09-05.html",
 "status": "open"}
```

Both files exist. Both are built. `"status": "open"` in **that** ledger means *built and
not yet reviewed* — the ledger's own header says so. Read as issue vocabulary it means the
opposite: *nothing has happened yet*. So the one row that proves the work is done is the
row that reads as proof it is not.

The cost is not a wasted hour. It is **an option card asking the owner to authorise work
they already paid for**, which spends the scarcest thing in the loop — their attention —
and invites a second artifact answering a question that already has one. A human who
answers that card has been misled by you, persuasively, because you quoted a real rule.

## Context / Trigger Conditions

Any of:

1. You are about to propose, plan, dispatch, or cost work **because a rule requires it**.
2. You are writing a question, an option, or a recommendation that offers to **build**
   something for the owner.
3. What you know about the rule came from its **id or title**, a memory note, a summary, or
   a peer's relay — not from its recorded body.
4. The rule **names a deliverable** and you have not yet queried the ledger for it.
5. A ledger row's status is a bare word (`open`, `pending`, `active`, `awaiting-owner`) and
   you have not read what that word means **in this ledger**.

Environmental smell: a ledger whose decision rows and artifact rows live in one file;
statuses that are single words; ids written as full sentences; parallel sessions that learn
the state by relay. None of this is covered by CI — **no gate reads a status word's
meaning**, and every check stays green while the card goes out.

## Solution

### 1. Read the rule's own record, off the default branch

Your checkout's copy is a copy; so is the memory that named the rule. Read the field.

```bash
LEDGER=docs/site/assets/data.js        # whatever your ledger is
git fetch origin --quiet
git show "origin/$(git symbolic-ref --short refs/remotes/origin/HEAD | cut -d/ -f2):$LEDGER" \
  > /tmp/ledger.live
python3 - <<'PY'
import json, re
raw = open("/tmp/ledger.live", encoding="utf-8").read()
data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])   # pure JSON after the assignment
for d in data.get("decisions", []):
    if "threshold" in d["id"]:                                    # your topic
        print(d["id"], "|", d.get("status"), "|", d.get("ruling", "")[:400])
PY
```

An id is a label someone chose; the body is the rule. They diverge most where it matters —
the body is where "and it is already commissioned" lives.

### 2. Separate what must be BUILT from what must be REVIEWED

Write the rule out as two obligations, because they have different owners:

| The rule requires | Who owes it | Your move if it is outstanding |
|---|---|---|
| the artifact exists | a session | build it |
| the artifact is reviewed | **the owner** | a review nudge — never a rebuild |

A session cannot discharge the second one, and building a second artifact does not help
the owner review the first.

### 3. Query the ledger for the deliverable — by id, topic AND date

Three queries, because a deliverable is named inconsistently by the sessions that filed it.

```bash
# artifacts whose id or path mentions the topic
python3 - <<'PY'
import json
raw = open("/tmp/ledger.live", encoding="utf-8").read()
data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
for a in data.get("artifacts", []):
    if "threshold" in a["id"] or "threshold" in a.get("path", ""):
        print(f'{a["status"]:16} {a["id"]:40} {a.get("path","")}')
PY

# and on disk, because a row and a file can exist without each other
ls -la docs/deliverables/ | grep -i threshold
```

### 4. Read what the status word MEANS in this ledger — do not infer it

The ledger tells you, and it is the step everyone skips:

```bash
# the ledger's own header/schema comment, and its validator
sed -n '1,60p' "$LEDGER" | grep -in "status\|open\|awaiting\|reviewed"
grep -rn "awaiting\|'open'\|\"open\"" tools/validate_data.mjs scripts/ 2>/dev/null | head
```

`open` is the dangerous spelling: in issue vocabulary it means *not started*, and a
ledger commonly uses it for *delivered, not yet signed off*. If the ledger does not define
its vocabulary, the validator does — it is the only reader whose interpretation is
enforced.

### 5. Pick the next step from who is blocked

- **No artifact, no row** → the work is genuinely outstanding. Propose it.
- **Artifact built, unreviewed** → the next step is a **review nudge**: one line naming
  the file, its path, its date, and the one question the review answers. Not a rebuild, not
  an option card offering to build it.
- **Reviewed already** → the rule is discharged; the next step is whatever the review
  implies, which the review's own record will say.

### 6. If you still propose the work, say what already exists

Sometimes a second artifact is right — the first was built at the wrong values, or against
a superseded input. Then the proposal must carry the existing one by path and date and say
why it does not answer the question. An option the owner can only evaluate by remembering
what they were sent three weeks ago is not an option.

## Verification

```bash
# 1. Every artifact row's file exists, and every deliverable file has a row.
python3 - <<'PY'
import json, os
raw = open("/tmp/ledger.live", encoding="utf-8").read()
data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
rows = {a.get("path") for a in data.get("artifacts", []) if a.get("path")}
for p in sorted(rows):
    if not os.path.exists(p):
        print("row with no file:", p)
disk = {os.path.join("docs/deliverables", f) for f in os.listdir("docs/deliverables")} \
       if os.path.isdir("docs/deliverables") else set()
for p in sorted(disk - rows):
    print("file with no row:", p)
PY

# 2. No text you are about to send offers to build a path that already exists.
grep -oE '[a-z0-9_/.-]+\.(html|md|json|csv)' OUTGOING.md | sort -u | while read -r p; do
  [ -e "$p" ] && echo "already exists, yet named as future work: $p"
done

# 3. Every rule you cited, you cited from its body — one line per id, printed.
#    If you cannot print the body you read, you read the title.
```

The third check is the one that catches this class. A citation you cannot print is a
citation you did not read.

## Example

| # | What happened |
|---|---|
| 1 | Session drafts an option card: *"shall I build the renders the rule requires?"* |
| 2 | The rule was read from its id, which is a full sentence and reads complete |
| 3 | Its body, on the default branch, said the renders were commissioned three weeks earlier |
| 4 | The ledger held **two** artifact rows for them, both `status: open`, both files on disk |
| 5 | `open` in that ledger means *built, awaiting the owner* — its header says so |
| 6 | Caught before sending, by one query of the artifact rows for the rule's topic |
| 7 | Card rewritten: option A became *"review the one that is already built, first"*, citing its path and date |

The rewritten card is shorter than the original and asks for something the owner can do in
ten minutes instead of something that costs a session.

## Notes

- **The id being a whole sentence is what makes this bite.** A ledger whose decision ids are
  written as full sentences — *d-the-threshold-is-charted-before-it-moves* — is easier to talk
  about and *harder to read correctly*: the id satisfies the reader's sense of having read the
  rule. An opaque id (*d-0421*) forces the lookup this skill is asking for.
- **A status word is domain vocabulary, not English.** The same word means "not started" in
  one register and "delivered, unreviewed" in another. Read it from the ledger's schema or
  its validator; treat any single-word status you have not looked up as unknown.
- **The deliverable can exist without the row and the row without the file.** Check both —
  Verification step 1 — and file the missing half rather than concluding from either alone.
- **Not a retired-brief problem.** `executed-prompt-not-retired-sibling-redoes-it` is a
  brief that was executed and never marked done, on both its surfaces. Here nothing was
  mis-marked: the ledger was correct and complete, and was not consulted.
- **Not a shipped-fix problem.** `verify-live-prod-before-shipping-superseded-fix` is a
  sibling having already shipped the change. Here the artifact is deliberately **not**
  shipped — it is waiting on a human, which is a state a session must not try to clear.
- **Same family as the copy-versus-thing skills**, one layer up:
  [`injected-claude-md-is-the-worktrees-copy-not-mains`](../injected-claude-md-is-the-worktrees-copy-not-mains/SKILL.md)
  and [`inherited-scope-doc-names-may-not-exist`](../inherited-scope-doc-names-may-not-exist/SKILL.md)
  are the injected rulebook and the inherited plan; this is a rule you quoted from its
  label while its record, and its deliverable, sat in a file you can read.
- **Write the ledger read into the wrap-up, not just the pickup.** The moment this fires is
  whenever you address the owner, and that is usually at wrap-up — after the checklist that
  would have caught it has already run.

## References

- Git docs: [`git show`](https://git-scm.com/docs/git-show) — `<rev>:<path>` reads a file
  out of a commit without checking it out, which is what makes step 1 free.
- Git docs: [`git symbolic-ref`](https://git-scm.com/docs/git-symbolic-ref) — resolves the
  remote's default branch, so step 1 does not hard-code `main`.
- `stale-base-drops-rows-from-a-shared-ledger` — the same ledger, the write side: a stale
  base silently drops other sessions' rows. Read it before editing the rows you just read.
