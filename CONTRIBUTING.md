# Contributing — publishing hygiene

These skills are often distilled from real client engagements. Before anything is pushed, a
**leak gate** checks for client / PII identifiers so engagement-specific details never ship to
this public repo.

## What runs automatically

**CI** (`.github/workflows/ci.yml`) runs `scripts/leak_scan.sh` on every PR and push. It
enforces low-false-positive generic patterns: Salesforce custom fields (`__c` / `__r`), API
keys / tokens, and real email addresses. A hit fails the check.

## One-time local setup (recommended)

Enable the committed pre-push hook so leaks are caught **before** they leave your machine:

```bash
git config core.hooksPath .githooks
cp .leakterms.example .leakterms      # then add YOUR real client / brand / project names
```

`.leakterms` is gitignored — it holds the names only you know are sensitive (client brands,
dataset / project ids, your username), one `grep -E` regex per line. **Never commit it.** The
generic CI patterns plus your local `.leakterms` together catch the *enumerable* leaks; a first
public publish still deserves a human / LLM semantic read for client-shaped names a fixed
pattern can't enumerate.

## If the gate fires

Sanitize the flagged content (replace the identifier with a neutral placeholder), or — for a
genuine false positive — narrow the pattern or add an exclusion in `scripts/leak_scan.sh`.
