# Dispatch and reasoning effort

Choose the smallest useful team for the question. Helper responsibilities such as extraction, inventories, formatting and exporter implementation do not each require a permanent session. Use a bounded helper or an existing specialist when useful; create persistent lanes for sustained independent work within the user's request.

## Deliberate model choice before launch

Check the host's model, reasoning and context-inheritance semantics. An omitted model can inherit an expensive parent; a reasoning setting alone does not necessarily choose a cheaper model. When a particular model is intended, specify it through the supported controls, or report that the host cannot select it. Some hosts disallow model overrides with full-history forks: use an allowed focused-context dispatch rather than pretending the override worked.

For a substantial fan-out, state the model or tier, effort, planned count or ceiling, and purpose before launch. Include nested agents and external consultations in the budget. Coordinate timing with an existing queue owner where needed. Existing authorization still applies; this announcement is not a new mandatory approval ceremony. A peer's timing agreement does not expand the user's permissions. Read recorded decisions before dispatching a team to rediscover them.

For simple work, an efficient model may suffice; difficult diagnosis or synthesis may merit stronger reasoning. Verify current model options rather than treating brand names as permanent capability rankings. Use [fan-out cost control](../../fan-out-cost-control/SKILL.md) when context or nested consultation costs become material.

## Escalate for a reason, not through a ladder

When High stalls on a specific hard diagnosis, Extra High or Max can be appropriate if the host and owner permit them. Explain what remains unresolved, why more reasoning may help, and what result or limit ends the attempt. A clearly difficult task can start stronger without first paying for predictable failures. Missing evidence, broken tools and permissions need their own fixes.

As a dated example, OpenAI's September 2026 [model guidance](https://learn.chatgpt.com/docs/models) describes Extra High for difficult reasoning, Max for more reasoning on one task, and Ultra for parallel subagent work. A host exposing Astra may use `gpt-6-astra` with `xhigh`, `max` or `ultra`; check its actual tool schema and behavior. These examples neither mandate Astra nor inherit a private user's permission to spend or delegate. Account for existing fan-out before adding another parallel layer. Where Ultra means parallel work and the diagnosis has no useful independent split, choose an appropriate single-task effort rather than Ultra merely because it sounds stronger.

Continue an existing task at higher effort when its context remains useful and the host supports it. Use a fresh specialist for a genuinely independent angle, a clean second opinion or a smaller sufficient evidence packet. Give it the question, exact inputs/base, relevant decisions, failed approaches, owned files, budget and stop condition. Avoid importing the entire programme transcript by default. Return to ordinary effort for routine follow-up.

## Compare the total attempt

Higher effort can avoid retries but is not a guaranteed token saving. Compare input/context, reasoning, visible output, retries, duplicated tools and integration. Parallel work often saves elapsed time while consuming more total tokens. A fresh focused helper can be cheaper than repeatedly processing a large history; continuing can be cheaper than rediscovering its evidence. Measure when possible and label estimates otherwise.

API billing, cached-input discounts and subscription usage are different quantities. Do not claim a weekly-usage saving from an API price calculation. The [API reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) documents reasoning-token accounting; it does not establish that this dispatch policy saves tokens.

## Keep loaded guidance current

Separate canonical source, installed files, discovered skill metadata and instructions already read into a task. A repository merge does not prove that a plugin cache or local copy updated, and an updated file does not prove every active task reread it. Compare the actual relevant files before claiming synchronization.

Current [Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) says local changes are detected automatically, with restart as a fallback if an update does not appear. For a material correction, explicitly reread the changed entrypoint/reference before continuing and identify which earlier guidance it supersedes. Other hosts and plugin installers may have different refresh behavior. Do not restart all tasks or overwrite divergent local copies automatically.
