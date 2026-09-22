"""ATC adapter for the canonical memory-hygiene engine; never a new skill.

Default shadow mode. No settings writes, installs, Git operations or permissions.
Load an explicitly supplied, digest-pinned shared engine, not an arbitrary cache hit.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PREFIX = "agent-traffic-control:"
GUARD = "context-routing/safeguards.md"
ISOLATION = "skills/pre-dispatch-agent-isolation-parameter-not-prompt/SKILL.md"
SHIP_ACTIONS = {"push", "merge", "deploy", "publish", "release", "create-pr", "edit-deploy-label"}


def load_engine(directory: Path):
    lock = json.loads((HERE / "engine-lock.json").read_text())
    directory = directory.resolve()
    for filename, expected in lock["files"].items():
        path = directory / filename
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("shared_engine_digest_mismatch")
    spec = importlib.util.spec_from_file_location("atc_shared_context_router", directory / "context_router.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.API_VERSION != lock["api_version"] or module.ENGINE_VERSION != lock["engine_version"]:
        raise ValueError("shared_engine_contract_mismatch")
    return module


def export(core, root: Path, metadata=None) -> dict:
    metadata = dict(metadata or {})
    # A provider cannot make these local guardrails disappear. No egress of them.
    metadata[GUARD] = {"id": PREFIX + GUARD, "kind": "policy", "mandatory": True,
                       "reviewed": True, "summary": "Preserve host permission, freshness and isolation gates",
                       "verification": "reviewed_adapter_policy", "egress_approved": False}
    return core.index(root, "agent-traffic-control", ["skills/*/SKILL.md", GUARD], metadata)


def prepare_state(state: dict, registry: dict) -> tuple[dict, list[str]]:
    """Only host-observed state belongs here; prompt text is not verification."""
    state = dict(state)
    required = set(state.get("required_ids", []))
    required.add(PREFIX + GUARD)
    findings = []
    # Compare a NORMALISED copy. An exact-string membership test made the whole shipping
    # preflight bypassable by a capital letter: next_action "Merge" returned status ok with
    # zero findings while "merge" returned preflight_required. Normalise here only; the
    # engine reads next_action as free text for term matching, so the state it sees is
    # deliberately left alone.
    action = str(state.get("next_action", "")).strip().lower().replace("_", "-")
    if action == "dispatch" and state.get("writes_code") is not False:
        required.add(PREFIX + ISOLATION)
        if state.get("isolation_verified") is not True:
            findings.append("Verify real dispatch isolation parameters/worktree paths before workers write.")
    if action in SHIP_ACTIONS:
        if state.get("resume_integrity") != "verified":
            findings.append("Interrupted-work integrity is unverified; preserve the existing resume-gate review.")
        if not state.get("current_revision") or state.get("checked_revision") != state["current_revision"]:
            findings.append("Re-read live/base revision immediately before shipping; recorded verification is stale or absent.")
    if action == "pickup" and state.get("claim_verified") is not True:
        findings.append("Read current issue ownership and perform the existing claim protocol before starting work.")
    state["required_ids"] = sorted(required)
    state["policy_revision"] = "atc-context-routing-v1"
    return state, findings


def run(core, root: Path, registry: dict, state: dict, *, mode="shadow", budget_bytes=16000,
        provider=None, session=None) -> dict:
    if mode == "off" or os.environ.get("CONTEXT_ROUTER_DISABLE") == "1":
        return {"status": "off", "context": "", "selected_ids": []}
    state, findings = prepare_state(state, registry)
    # A route the adapter is going to refuse must not reach the provider first. The
    # downgrade below used to run AFTER core.route, so a shipping action with unverified
    # observations returned preflight_required having already sent the public capsule and
    # candidate summaries to the third party, and paid for it. Drop the provider before the
    # call, not after: the refusal has to precede the egress, not describe it.
    if findings:
        provider = None
    result = core.route(registry, root, state, mode=mode, budget_bytes=budget_bytes,
                        provider=provider, session=session)
    result["preflight_findings"] = findings
    result["authorizes_execution"] = False
    if findings:
        result["status"] = "preflight_required"
        result["context"] = ""
        result["retire_on_rebuild"] = []
    return result


def hook_output(result: dict, registry: dict, mode: str) -> dict:
    """UserPromptSubmit advisory only; no allow/deny and no automatic Skill calls."""
    if mode != "active" or result.get("status") == "off":
        return {}
    if result.get("status") != "ok":
        text = ("Context routing could not supply a verified complete bundle. Use existing retrieval; "
                "preserve all host gates. " + " ".join(result.get("preflight_findings", [])))
    else:
        by_id = {r["id"]: r for r in registry["records"]}
        pointers = [{"source": by_id[key]["source"], "origin": by_id[key].get("origin", ""), "kind": by_id[key]["kind"],
                     "invocation_policy": by_id[key]["invocation_policy"],
                     "sha256": by_id[key]["content_hash"]} for key in result["selected_ids"]]
        text = ("Candidate canonical references, not permission to execute. Use the host's normal skill loader "
                "and preserve all invocation controls, allowed tools and forked-context requirements. "
                "Do not treat a file read as a skill invocation. " + json.dumps(pointers))
    # Bound the entire hint; never clip individual procedure metadata mid-field.
    if len(text.encode()) > 4096:
        text = "Context routing found a bundle too large for this advisory. Use existing retrieval and preserve host gates."
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def stage_lean(core, root: Path, registry: dict, keep: list[str], output: Path) -> dict:
    """Explicit scratch preview only. Never mutate installed/full plugin or promote a manual skill."""
    if "sources" in registry:
        raise ValueError("preview_requires_atc_leaf_registry")
    core.snapshot(registry, root)
    by_id = core.validate(registry)
    keep_ids = {PREFIX + f"skills/{name}/SKILL.md" for name in keep}
    if not keep_ids or any(key not in by_id or by_id[key]["invocation_policy"] != "automatic" for key in keep_ids):
        raise ValueError("keep_requires_existing_automatic_skills")
    root = root.resolve()
    target = output.absolute()
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(root):
        raise ValueError("preview_target_must_be_new_and_outside_plugin")
    if any(p in {".claude", ".codex", ".git"} for p in target.parts):
        raise ValueError("refuse_installation_or_git_target")
    if target.parent.resolve() != target.parent:
        raise ValueError("preview_parent_must_be_resolved")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("preview_source_symlink")
    shutil.copytree(root, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    demoted = []
    for key, item in by_id.items():
        if item["kind"] != "skill" or item["invocation_policy"] != "automatic" or key in keep_ids:
            continue
        path = target / item["source"]
        text = path.read_text()
        # These files already passed shared frontmatter validation. Remove a false
        # declaration before adding true; never create duplicate security keys.
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            raise ValueError("preview_skill_requires_frontmatter")
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        fm = [line for line in lines[1:end] if not line.startswith(("disable-model-invocation:", "listing_tier:"))]
        path.write_text("---\ndisable-model-invocation: true\n" + "".join(fm) + "".join(lines[end:]))
        demoted.append(key)
    manifest_path = target / ".claude-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["name"] = "agent-traffic-control-lean-preview"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"status": "preview_only", "installed": False, "output": str(target),
            "kept_automatic": sorted(keep_ids), "demoted_in_preview_only": sorted(demoted),
            "source_unchanged": True, "token_savings": "unmeasured",
            "warning": "Do not enable beside the full plugin. Review frozen A/B/C evaluation first. "
                       "Manual-only procedures and all hook files remain present."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", type=Path, required=True, help="pinned memory-hygiene scripts directory")
    p.add_argument("--root", type=Path, default=HERE.parent)
    p.add_argument("--roots", type=Path, help="combined registry's explicit root-map JSON, route/hook only")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("index")
    q.add_argument("--metadata", type=Path)
    for command in ("route", "hook"):
        q = sub.add_parser(command)
        q.add_argument("--registry", type=Path, required=True)
        q.add_argument("--state", type=Path, required=True, help="trusted session-local host state; not a transcript")
        q.add_argument("--mode", choices=["off", "shadow", "active"], default="shadow")
        q.add_argument("--budget-bytes", type=int, default=16000)
        if command == "route":
            q.add_argument("--jev", action="store_true")
    q = sub.add_parser("stage-lean")
    q.add_argument("--registry", type=Path, required=True)
    q.add_argument("--keep", action="append", required=True, help="existing automatic skill name")
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("--ack-preview", action="store_true", required=True)
    args = p.parse_args(argv)
    is_hook = args.command == "hook"
    if getattr(args, "mode", "") == "off" or os.environ.get("CONTEXT_ROUTER_DISABLE") == "1":
        if not is_hook:
            print(json.dumps({"status": "off", "context": ""}))
        return 0
    try:
        core = load_engine(args.engine)
        if args.command == "index":
            meta = json.loads(args.metadata.read_text()) if args.metadata else None
            result = export(core, args.root, meta)
        elif args.command == "stage-lean":
            result = stage_lean(core, args.root, json.loads(args.registry.read_text()), args.keep, args.output)
        else:
            registry = json.loads(args.registry.read_text())
            state = json.loads(args.state.read_text())
            if is_hook:
                raw = sys.stdin.read(65537)
                if len(raw) > 65536:
                    raise ValueError("hook_input_too_large")
                payload = json.loads(raw)
                if payload.get("hook_event_name") != "UserPromptSubmit":
                    raise ValueError("unsupported_hook_event")
                # Both sides must actually CARRY the binding. `!=` alone is vacuous when
                # the payload and the state file both omit a field: None == None passed,
                # so a state file with no worktree key bound to any working directory.
                bound = (payload.get("session_id"), payload.get("cwd"))
                if not all(isinstance(v, str) and v for v in bound):
                    raise ValueError("hook_payload_missing_session_binding")
                if not all(isinstance(state.get(k), str) and state.get(k)
                           for k in ("session_id", "worktree")):
                    raise ValueError("hook_state_missing_session_binding")
                if bound != (state["session_id"], state["worktree"]):
                    raise ValueError("hook_session_or_worktree_mismatch")
                state["latest_message"] = payload.get("prompt", "")
                state["as_of"] = date.today().isoformat()
                # A prompt hook lacks fresh host action observations; it must not claim
                # that a saved action/preflight verification is current.
                # writes_code is discarded with them: a saved `false` would skip the
                # dispatch isolation gate on every later prompt. Dropping it is only safe
                # because prepare_state now treats an absent value as unknown and requires
                # the evidence anyway -- popping it under the old `is True` test disabled
                # the gate instead of tightening it.
                for key in ("isolation_verified", "claim_verified", "checked_revision",
                            "resume_integrity", "writes_code"):
                    state.pop(key, None)
            provider = None
            if getattr(args, "jev", False):
                spec = importlib.util.spec_from_file_location("atc_jev_provider", args.engine / "jev_provider.py")
                provider_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(provider_module)
                provider = provider_module.JevProvider()
            roots = json.loads(args.roots.read_text()) if args.roots else args.root
            result = run(core, roots, registry, state, mode=args.mode,
                         budget_bytes=args.budget_bytes, provider=provider)
            if is_hook:
                result = hook_output(result, registry, args.mode)
        if result:
            print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0 if is_hook or result.get("status") not in {"blocked", "preflight_required"} else 2
    except Exception as exc:
        # Optional hook errors never block a prompt or approve a shipping action.
        # No exception body: it can contain private paths, payloads or credentials.
        if is_hook:
            print("ATC context router unavailable; existing retrieval and gates remain in force (" + type(exc).__name__ + ").", file=sys.stderr)
            return 0
        print(json.dumps({"status": "unavailable", "error_type": type(exc).__name__,
                          "context": "", "authorizes_execution": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
