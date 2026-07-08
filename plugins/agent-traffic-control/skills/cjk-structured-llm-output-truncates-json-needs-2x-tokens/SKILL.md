---
name: cjk-structured-llm-output-truncates-json-needs-2x-tokens
description: |
  When generating LONG Chinese/Japanese/Korean (CJK) STRUCTURED output (a big JSON report, a multi-section
  document) from an LLM chat API, the response truncates mid-JSON and your parser throws "no parseable JSON"
  / "Expecting ',' delimiter" / JSONDecodeError — even though the SAME prompt in English worked. Root cause:
  CJK is token-heavy (≈1–2 tokens per character vs ≈0.25 for English), so a report that fit your max_tokens in
  English overflows it in Chinese. Some models ALSO hard-cap output well below what you request (e.g. qwen-max
  caps at 8192) and silently truncate. Use when: a zh/ja/ko structured-generation run fails JSON parsing,
  worked in English, or a specific model truncates while others on the same prompt succeed. Covers the ~2×
  token budget rule, per-model output caps, and a salvage that recovers the complete sections from a
  truncated object.
author: Claude Code
version: 1.0.0
date: 2026-06-27
disable-model-invocation: true
---

# Long CJK structured output truncates JSON — budget ~2× tokens, and salvage the rest

## Problem
You ask an OpenAI-compatible LLM for a long JSON report. In English it returns valid JSON. In **Chinese
(or Japanese/Korean)** the identical request returns a string that **starts** with valid JSON but is **cut off
mid-object** → `json.loads` fails, your regex `\{.*\}` grabs an unbalanced blob, and you get "no parseable JSON".

## Why
- **CJK is token-dense.** One Han character is often 1–2 BPE tokens; English averages ~0.25 tokens/char. The
  *same* report is ~1.5–2× more output tokens in Chinese. A `max_tokens` that comfortably fit the English report
  truncates the Chinese one.
- **Per-model output caps differ and some are low.** Requesting `max_tokens` above a model's hard cap is either
  rejected (`400 ... Range of max_tokens should be [1, 8192]`) or silently clamped, then the long CJK report
  truncates. Observed: **qwen-max hard-caps at 8192** (can't emit a full Chinese report); glm-4.6 / minimax ≈16K;
  qwen-plus / qwen3-235b / glm-5.2 / kimi / deepseek handle 24–32K. Reasoning models also spend tokens on
  `reasoning_content` *before* the JSON, compounding it.

## Fix
1. **Budget ~2× the English max_tokens for CJK** (e.g. 16000–32000 for a full report), per model, up to its cap.
2. **Probe the cap** if a `400` appears — binary-search `max_tokens` (a tiny call that 400s vs 200s reveals the
   ceiling). For reasoning models, leave headroom for `reasoning_content`.
3. **Salvage truncated JSON** instead of failing — close the object after the last *complete* top-level section.
   Walk the string tracking brace/bracket depth and string/escape state; record the index each time depth returns
   to 1 (a top-level value just closed); cut there and append `}`:
   ```python
   def salvage(c):
       s = c[c.find("{"):]; depth=0; instr=False; esc=False; cut=None
       for i,ch in enumerate(s):
           if esc: esc=False; continue
           if instr:
               if ch=="\\": esc=True
               elif ch=='"': instr=False
               continue
           if ch=='"': instr=True
           elif ch in "{[": depth+=1
           elif ch in "}]":
               depth-=1
               if depth==1: cut=i+1
       if cut:
           try:
               d=json.loads(s[:cut].rstrip().rstrip(",")+"}")
               if isinstance(d,dict) and len(d)>=MIN_SECTIONS: return d
           except Exception: pass
       return None
   ```
   Truncation then degrades gracefully — the report keeps its complete sections, and the missing tail shows up as
   lower "comprehensiveness" in scoring rather than a hard failure.
4. **Also strip reasoning prefixes** before parsing: some models inline chain-of-thought as `<think>…</think>`
   before the JSON (MiniMax-M3) — `re.sub(r"(?is)^.*?</think>","",c)` first.

## Verification
The run produces valid JSON with all expected top-level keys for every model; a model that still truncates is
hitting a hard output cap (flag it — that cap is itself a real production limitation for long-CJK tasks, not just
a config bug). Salvaged reports parse and carry ≥ your minimum section count.

## Notes
- The output cap is a **decision input**, not only a bug: a model that cannot emit a full report in the target
  language is a poor production pick for that task regardless of its quality.
- Sibling: `openai-compatible-chinese-llm-client-divergences` (provider quirks),
  `bq-query-default-max-rows-100-silent-truncation` (a different silent-truncation trap).

## Example (a Chinese-language multi-model bake-off)
8 models × 3 rollouts writing the same ~7-section brand report in Chinese. English runs were ~10–60K chars and
fit 8–16K tokens; the Chinese runs truncated at the same caps. Bumping to 16–32K fixed most; **qwen-max (8192
hard cap) could not be fixed and truncated every long rollout** → it ranked last on a truncation artifact, which
was reported as a genuine production disqualifier. The brace-depth salvage turned the remaining truncations into
judgeable partial reports.
