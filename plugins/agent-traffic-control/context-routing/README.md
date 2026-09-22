# Context routing adapter (opt-in draft)

No new skill and no default hook. The shared implementation lives in memory-hygiene;
this directory only adapts workflow state, preserves ATC safeguards and offers a
scratch lean preview. It does not execute commands or grant permission.

## Dependency

Use the companion memory-hygiene context-routing PR's scripts directory. The adapter
verifies engine-lock.json's **file hashes before importing anything**, and asserts the
engine's API/version constants immediately after the module executes — the digest is what
guards the import, the version constants are a contract check on code already loaded.
Do not select a random 'latest' cache directory. If either core/provider file changes,
review the change and update the lock together; a mismatch is visible, not ignored.
The lock's companion_commit is the exact source revision for CI checkout.

```sh
ENGINE=/absolute/path/to/memory-hygiene/plugins/memory-hygiene/scripts
ATC=/absolute/path/to/agent-traffic-control/plugins/agent-traffic-control
python "$ATC/context-routing/adapter.py" --engine "$ENGINE" --root "$ATC" index > atc-registry.json
python "$ATC/context-routing/adapter.py" --engine "$ENGINE" --root "$ATC" route \
  --registry atc-registry.json --state private-session-state.json > shadow.json
```

Default routing is **shadow**. No source bodies are injected; no installed catalogue is
suppressed. Preserve private permissions on state/index/report files (umask 077), and
keep them outside the public repo. The existing plugin installation continues unchanged.

The current repository already has live/reference-only tiers and a catalogue budget.
This adapter respects those decisions, not '123 full skills loaded on every turn'.
Manual-only source controls are preserved. Declaring a required dependency cannot make
one automatically invocable. Existing host tool/fork permissions remain the host's job.

## Trusted workflow state

Supply the shared engine's session_id, as_of (ISO day), goal, latest_message, phase,
next_action, worktree, scope, required_ids, explicit_ids and previous_ids fields.
The adapter adds a mandatory local safeguard reference. For code-writing dispatches it
also requires the canonical isolation procedure. Host-observed fields include
writes_code, isolation_verified, claim_verified, current_revision, checked_revision
and resume_integrity. These are not values to infer from the user's prompt.

A next_action of pickup needs live claim verification. A writing dispatch needs real
isolation evidence. push, merge, deploy, publish, release, create-pr and edit-deploy-label
need interrupted-work verification and matching checked/current revision observations.
These checks emit **preflight_required**, not permission decisions. Reread actual live
state at the action boundary and retain the existing separately installed resume-gate.
Even status=ok carries authorizes_execution=false. No tool call is executed here.

Unknown required evidence or a changed source/index is visible and uses the existing
retrieval path. Do not react by bulk-loading all procedures. Do not store mutable
active-skill settings globally across parallel sessions.

## Combine with private memories: one budget

Use the shared engine's combine command on the ATC and memory registries, then give
this adapter `--roots /absolute/path/to/private-roots.json` instead of a single root
for route/hook. The map must explicitly name both original namespaces and approved
local directories. The combined registry supports reviewed cross-store dependencies,
conflicts and supersession without duplicating either engine or source files.

See the companion memory-hygiene `docs/context-routing.md` for the complete schema,
read-only maintenance audit, optional semantic pair review and A/B/C evaluation.

## Optional Jev

Only route --jev enables an outbound ranking call. It additionally needs reviewed
per-record public_summary/egress_approved metadata and a sanitized public_task in state.
Index defaults never approve egress. Set TYPESAFE_API_KEY locally, not in JSON or Git.
The prompt hook has **no Jev/network option**. No provider owns a permission boundary.
The same core can run with local retrieval alone; no separately loaded Jev skill exists.

## Optional Claude UserPromptSubmit advisory

Nothing registers this hook. After the shadow/installed-host trial, an owner may append
an explicitly configured command to their existing hook settings; never replace the
settings file. Use stable, reviewed absolute paths, not a transient worktree/cache/tmp
script. Hook state must be **session-local** and its session_id/worktree must match the
actual hook payload. Point each host session at its own trusted state file.

Command shape (all paths supplied by the owner):

```sh
python /stable/atc/context-routing/adapter.py \
  --engine /stable/memory-hygiene/scripts --root /stable/atc \
  hook --registry /private/session/registry.json \
  --state /private/session/state.json --mode active
```

Use type=command under UserPromptSubmit with a host timeout suitable for local reads.
Start with --mode shadow. Shadow emits no hook context or persistent trace; use the
route CLI/evaluation harness for shadow capture. The hook validates the event/session,
adds only compact canonical **pointers**, and tells the model to use its normal skill
loader; it never pastes executable skill bodies as a replacement for that loader.
It discards saved preflight verification because a prompt hook cannot prove that an
old shipping/isolation observation is still fresh. Errors emit a short stderr note,
exit zero and leave native retrieval/gates intact. No permissionDecision field exists.

UserPromptSubmit is **not** a hook before every internal LLM call. The advisory does
not remove existing plugin descriptions or unload earlier conversation content.
There is no claimed catalogue-token saving from enabling it. A controlled agent harness
may call the shared API at action/phase transitions and rebuild outgoing context itself.
In-process callers may keep one Session cache per real session. CLI processes do not
share a persistent cache. A full off switch, checked before loading files, is
CONTEXT_ROUTER_DISABLE=1 or --mode off.

## Lean preview, not an installed release

A separate scratch builder can test a smaller live catalogue after owner-reviewed
A/B/C measurements. It copies the full plugin into a **new external directory**,
demotes omitted automatic skills only in that copy, preserves every manual-only skill
and every hook file, and changes only the preview plugin's name. It never promotes a
reference-only skill, deletes a procedure or writes inside .claude/.codex/.git.
No installation or global skillOverrides mutation occurs.

```sh
python "$ATC/context-routing/adapter.py" --engine "$ENGINE" --root "$ATC" stage-lean \
  --registry atc-registry.json \
  --keep pre-dispatch-agent-isolation-parameter-not-prompt \
  --output /absolute/new-scratch-directory/atc-preview --ack-preview
```

The parent directory must already exist and be resolved (on macOS use the real /private
path when applicable). A failed staging operation can leave an incomplete scratch
preview; never install one without status=preview_only and inspection. The original
plugin is unchanged. Use a **leaf ATC registry**, not the combined memory index.
Preserve the existing isolation procedure and other required entry points in any
actual profile. Test reference reachability from the chosen live entries; this builder
does not certify it or the native host's discovery behaviour.

Do not enable the preview and full plugin simultaneously. This is not a new marketplace
release and does not change the existing skill count/version. Hook installation remains
its existing separate opt-in operation. Actual catalogue tokens, cache effects and
end-to-end success are unmeasured until the installed-host trial. The provider cannot
choose to publish or activate a profile.

## Verification

```sh
CONTEXT_ROUTER_HOME="$ENGINE" python -m unittest discover -s tests/context_routing -v
```

The new CI workflow checks out the digest-pinned companion commit and runs the tests
against the full ATC checkout, including a live/reference inventory census. Existing
route, tier, description, leak, release-parity and resume-gate tests remain unchanged.
Synthetic fixtures also verify no settings/source writes, stale/unknown preflight,
manual-only preservation, missing/wrong dependency, off mode, hook schema and preview
hook-byte preservation. Offline passes are not a live Jev or native-agent benchmark.

Roll back by removing only the optional advisory or selecting off, discarding any scratch
preview, and using the unchanged full plugin. No source memories need reconstruction.

Sources checked 2026-09-20:
https://docs.typesafe.ai/api
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/hooks

Prepared by ChatGPT. This is an opt-in draft implementation, not a production activation.
