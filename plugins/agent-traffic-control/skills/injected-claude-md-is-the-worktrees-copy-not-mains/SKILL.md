---
name: injected-claude-md-is-the-worktrees-copy-not-mains
description: |
  The CLAUDE.md (or AGENTS.md / GEMINI.md) your session quotes is the copy in the
  checkout the session STARTED in, not the one on the default branch — and a
  long-lived worktree's copy can be weeks behind, so every house rule in context
  may be retired. Use when: (1) you are about to write or say "CLAUDE.md says X",
  "the house rule is X", or "the project file is stale about X"; (2) your session
  runs in a worktree that was created days or weeks ago; (3) a SessionStart hook
  or banner mentions the instruction file differing from the default branch;
  (4) you are about to file an issue, correct a document, or tell a peer that a
  shared instruction file contradicts the code. The failure inverts: the file on
  the default branch is usually RIGHT and your injected copy is the stale thing,
  so the bug report points at the wrong artefact. A retired copy is often LONGER
  than the current file — superseded correction notes accumulate until a rewrite
  deletes them — so the stale version reads as the more complete one. The copy
  carries no date and no banner, and compaction RE-READS it from disk, so the
  bytes can change mid-session in either direction. A session's age is therefore
  not evidence about which copy it holds: only a marker sentence present in one
  version and absent in the other settles it.
  Settle it with `git show <remote>/<default-branch>:CLAUDE.md` and cite that,
  never the text in context.
version: 1.1.0
date: 2026-09-17
author: wan-huiyan
disable-model-invocation: true
---
# The Injected CLAUDE.md Is Your Worktree's Copy, Not the Default Branch's

## Problem

Claude Code reads the project instruction file — `CLAUDE.md`, and the equivalent
for other harnesses — from the checkout the session started in, and injects it
into context at session start. In a worktree that was created three weeks ago and
never merged since, that is a three-week-old file.

**Nothing about it looks old.** It arrives in the same position, with the same
heading, as the current file would. It has no commit stamp, no date, no "you are
reading a snapshot" banner. Every rule in it reads as the house rule in force.

Two properties make it worse than an ordinary stale read:

1. **The retired copy is frequently LONGER than the live one.** An instruction
   file accumulates correction notes — "this said X until <date>, and X was
   wrong" — and periodically someone rewrites it down to the rules as they now
   stand, deleting the archaeology. A session holding the pre-rewrite copy holds
   more text, more caveats and more history than the current file, so on any
   "which of these looks more complete?" instinct the stale one wins.
2. **Compaction re-reads the file FROM DISK, which cuts both ways.** A long
   session that compacts is re-served the instruction files from its checkout as
   they are at that moment. If nothing changed, the stale copy is refreshed from
   a stale source and looks re-verified — the usual case. But if someone moved
   that checkout meanwhile, the session is silently handed the CURRENT file, and
   a second copy now sits in its context governing over the first.
   **Amended 2026-09-17, measured in the same repository the day this skill
   landed:** a session that started in a checkout detached two weeks back was
   compacted after a peer brought that checkout up to the default branch, and the
   re-read injected the 81,929-byte current file with a harness note saying it
   replaced the earlier copy. So "this session started before the rewrite,
   therefore it holds the retired text" does not follow, and neither does the
   reverse — a session started after a rewrite can be pinned to an old checkout.

The damage is not that you follow an out-of-date rule — that is usually benign,
because retired rules are mostly stricter than current ones. The damage is when
you make a CLAIM about the file: you report that the shared instruction file is
stale, contradicts the code, or needs an issue. **The direction inverts.** The
file on the default branch is correct and already says the thing you are about to
"discover"; the stale artefact is the copy in your own context. The issue, the
correction and the peer message all point at the wrong artefact, and they are
persuasive because you quoted the file.

## Context / Trigger Conditions

You are in the right place if any of these hold:

- You are about to write "CLAUDE.md says", "the house rules say", "the project
  file is stale about", or "the repo contradicts itself" — in an issue, a pull
  request body, a memory note, or a message to another session.
- Your session is running in a worktree, and you did not create that worktree in
  this session.
- A SessionStart hook, banner or system message mentions the instruction file
  being behind, or prints two byte counts.
- You are reconciling a document against code and the document is an instruction
  file rather than ordinary prose.
- A peer session quotes the house rules at you from ITS context. Same trap, one
  hop away: that quote is a quote of that session's checkout.

**Two things that look like corroboration and are not:**

1. **The file is present, complete and internally consistent.** A retired version
   is a real file that was correct on its own commit. Reading it more carefully
   cannot reveal its age.
2. **The rule you are reading is very specific and clearly deliberate.** Retired
   rules are specific and deliberate too — that is why they were written down and
   why their deletion needed a rewrite rather than an edit.

## Solution

**One command settles it, and the claim must cite that command rather than the
text in your context.**

### Step 1 — Fetch, then read the file from the default branch

```bash
git fetch -q origin main
git show origin/main:CLAUDE.md | wc -c
git log -1 --format='%h %ci %s' origin/main -- CLAUDE.md
```

The third line is the one that tells you whether a rewrite happened and when.

### Step 2 — Compare against what you were injected

```bash
wc -c CLAUDE.md                         # your checkout's copy
git show origin/main:CLAUDE.md | wc -c  # the live one
```

A large size difference in EITHER direction means your copy is not the live file.
Do not reason about which is "more complete" — see Problem, property 1.

### Step 3 — Search the live file before claiming anything about it

```bash
git show origin/main:CLAUDE.md | grep -n "<the subject of your claim>"
```

If the live file already states the thing correctly, there is no defect and no
issue to file. If it genuinely disagrees with the code, you now have a real
finding, sourced from the live file.

### Step 4 — Fix the source of the staleness, once

The stale copy will keep being injected into every future session started in that
worktree, including other people's. Merge the default branch into the worktree's
branch (never a hard reset of somebody else's work), or, if the worktree is
finished, remove it after the usual clean check:

```bash
git -C <worktree> status --porcelain    # must be empty before removing
```

### Step 5 — Phrase the claim so it carries its own provenance

> My copy of CLAUDE.md (worktree `<path>`, from `<sha>`) says A; `origin/main`'s
> CLAUDE.md (read just now, last changed in `<sha>` on `<date>`) says B.

"The file is stale" is a conclusion you may only write AFTER Step 1, and it names
which copy.

## Verification

The check must be able to return "current", or it is not a check.

Run Steps 1-2 in a **fresh worktree of the default branch** and confirm they
report identical bytes and the same last-changed commit:

```bash
git worktree add /tmp/control-check origin/main
cd /tmp/control-check
[ "$(wc -c < CLAUDE.md)" = "$(git show origin/main:CLAUDE.md | wc -c)" ] \
  && echo "CURRENT" || echo "STALE"
```

A control that says STALE on a fresh checkout of the default branch is measuring
something else — most likely you compared against a local `main` ref that is
itself behind, rather than `origin/main` after a fetch.

**To settle which copy YOUR CONTEXT holds — which is a different object from any
file on disk — use a marker sentence rather than a byte count.** Pick a sentence
that exists in the retired version and not in the current one (a superseded
correction note is ideal, since a rewrite deletes those), and check both sides:

```bash
git show origin/main:CLAUDE.md | grep -c "THE CENSUS THAT USED TO BE HERE IS GONE"
# 0 on the current file; the retired copy contains it. Then look for the same
# sentence in the text you were injected, and for the current file's own opening
# line. Whichever you find is the copy you are reasoning from.
```

A byte count cannot do this: you cannot `wc -c` your own context, and the file on
disk may have moved since it was injected.

## Example

*Worked example from a route-generation repository where several sessions run in
parallel worktrees. Paths and SHAs are that repository's; the mechanism is not.*

A session running in a worktree created weeks earlier was asked to save its
lessons. Reconciling one of them against the code, it measured that the house
file's passages about which drawing the search actually uses were contradicted by
the code, and drafted both a memory note and a message to the coordinating
session saying so.

Measured before sending:

```
checkout's CLAUDE.md ....... 238,232 bytes
origin/main's CLAUDE.md .....  81,929 bytes
origin/main last change ..... d23357470  2026-09-15  "CLAUDE.md carries only the
                              house rules as they stand today"
```

**The live file was right.** It stated the code's behaviour correctly and had done
since the rewrite two days earlier. What the session held was the 238 KB
pre-rewrite copy — nearly three times the size, carrying months of correction
notes the rewrite had deleted. The "defect" was entirely inside its own context.

Two details worth carrying:

- **A SessionStart hook had printed the warning, with both byte counts, at the
  top of the session.** It was skimmed, and the session then reasoned from the
  stale rules for hours. Detection existing is not detection working; the hook
  output has to be treated as a blocker on claims about the file, not as a
  banner.
- **The bigger file felt like the more authoritative one.** Every instinct about
  completeness pointed the wrong way.

**The same class, same day, one layer up.** The same session checked a plugin's
skills for duplicate coverage by reading the installed copy under
`~/.claude/plugins/cache/...`, which held **99 skills at v1.29.0**, while the
source repository on disk held **111 at v1.36.1** — twelve skills newer,
committed by peers twenty minutes earlier. The duplicate check was re-run against
the source and one of the two candidate lessons turned out to be already covered.
A cache directory named for a version is a label, not an identity.

## Notes

- **This is not the same as a peer editing the file under you.**
  [`isolate-subagent-verification-from-live-worktree`](../isolate-subagent-verification-from-live-worktree/SKILL.md)
  covers a live worktree changing DURING a run. Here nothing changes: the file is
  quietly a different, older file for the whole session.
- **Sister skill**: [`inherited-scope-doc-names-may-not-exist`](../inherited-scope-doc-names-may-not-exist/SKILL.md)
  is the same principle for a plan or scope document from a previous session —
  verify what an inherited artefact asserts before you dispatch on it. This skill
  is the case where the inherited artefact is the RULES themselves, injected
  automatically, with no moment at which you chose to trust it.
- **It reaches every automatically-injected file**, not just `CLAUDE.md`:
  `AGENTS.md`, `GEMINI.md`, nested per-directory instruction files, and a
  plugin's or skill's installed copy under a cache directory.
- **Length is not recency and neither is specificity.** Both heuristics point at
  the retired copy, which is why this needs a command rather than judgement.
- **A worktree that outlives a few days is the risk surface.** If your workflow
  keeps long-lived worktrees, merging the default branch into them is cheap
  insurance; the alternative is that every session started there inherits the
  same retired rulebook.

## Notes — amendment, 2026-09-17

- **A sweep of instruction files on disk does not measure what any session
  holds.** A coordinator measured `CLAUDE.md` in 255 worktrees and told several
  peers they were "holding stale rules". Those are two different objects, and the
  second was never read. Its own withdrawal names the gap: the sendable sentence
  is *"worktree X on disk carries N bytes; what YOUR session holds I have not
  read — a marker sentence settles it"*. A verdict about a peer's context needs
  the peer to check a marker sentence, which costs them one command.
- **Check WHICH tree the stale file is in before accepting a claim about yours.**
  In the same exchange the stale copy was in a worktree named after the session
  but last committed a fortnight earlier and not in use; both worktrees that
  session was actually working in already carried the current file, because they
  were created from commits made after the rewrite. A worktree named after a
  session is not necessarily a worktree it uses.
- **Do not fix this by merging the default branch into a pinned worktree.** A
  research worktree detached at the exact commit a measurement's artefacts are
  checksum-pinned from must not move: merging would change the code the
  measurement ran on. Read the live file with `git show` instead; the worktree's
  own copy does not need to be current for that.

## References

- Claude Code docs: [Memory / CLAUDE.md](https://docs.claude.com/en/docs/claude-code/memory)
  — how project instruction files are discovered and loaded at session start.
- Git docs: [`git show`](https://git-scm.com/docs/git-show) — `<rev>:<path>`
  reads a path out of a commit without checking it out, which is what makes
  Step 1 free and unambiguous.
- Git docs: [`git worktree`](https://git-scm.com/docs/git-worktree) — each
  worktree carries its own working-tree copy of every tracked file, including the
  instruction files a harness injects.
