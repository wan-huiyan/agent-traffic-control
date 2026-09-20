"""Synthetic install-shaped fixtures plus shared-engine contract verification."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "plugins/agent-traffic-control/context-routing"
SCRIPTS = Path(os.environ.get("CONTEXT_ROUTER_HOME", REPO.parent / "memory-hygiene/plugins/memory-hygiene/scripts"))
spec = importlib.util.spec_from_file_location("adapter", HERE / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = adapter.load_engine(SCRIPTS)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name).resolve()
        self.root = self.temp_root / "plugin"
        self.root.mkdir()
        self.write(adapter.GUARD, (HERE / "safeguards.md").read_text())
        self.write(adapter.ISOLATION, "---\nname: pre-dispatch-agent-isolation-parameter-not-prompt\nlisting_tier: short\ndescription: Verify dispatch isolation\n---\nVerify actual dispatch parameters.")
        self.write("skills/live/SKILL.md", "---\nname: live\nlisting_tier: short\ndescription: Deploy procedure\n---\nFull live procedure")
        self.write("skills/manual/SKILL.md", "---\nname: manual\ndisable-model-invocation: true\n---\nManual procedure")
        self.write(".claude-plugin/plugin.json", json.dumps({"name": "agent-traffic-control", "version": "0.0.0"}))
        self.write("hooks/resume-gate/synthetic.py", "# test hook content, must not change\n")
        self.state = {"session_id": "session-a", "as_of": "2026-09-20", "goal": "Deploy",
                      "scope": {}, "worktree": "/synthetic/worktree-a"}
        self.registry = adapter.export(self.core, self.root)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def hashes(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def test_core_is_canonical_not_vendored(self):
        self.assertFalse((HERE / "context_router.py").exists())
        self.assertEqual(self.core.API_VERSION, 1)

    def test_export_keeps_manual_control(self):
        item = next(r for r in self.registry["records"] if r["source"] == "skills/manual/SKILL.md")
        self.assertEqual(item["invocation_policy"], "manual-only")

    def test_export_has_mandatory_local_policy(self):
        item = next(r for r in self.registry["records"] if r["source"] == adapter.GUARD)
        self.assertTrue(item["mandatory"])
        self.assertFalse(item["egress_approved"])

    def test_guard_override_cannot_disable(self):
        r = adapter.export(self.core, self.root, {adapter.GUARD: {"mandatory": False}})
        self.assertTrue(next(i for i in r["records"] if i["source"] == adapter.GUARD)["mandatory"])

    def test_shadow_has_no_injection(self):
        result = adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(result["context"], "")
        self.assertEqual(adapter.hook_output(result, self.registry, "shadow"), {})

    def test_active_advisory_does_not_execute_or_inline_skills(self):
        result = adapter.run(self.core, self.root, self.registry, self.state, mode="active")
        out = adapter.hook_output(result, self.registry, "active")
        self.assertFalse(result["authorizes_execution"])
        self.assertNotIn("Full live procedure", json.dumps(out))
        self.assertNotIn("permissionDecision", json.dumps(out))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_dispatch_requires_real_isolation(self):
        self.state.update(next_action="dispatch", writes_code=True)
        result = adapter.run(self.core, self.root, self.registry, self.state, mode="active")
        self.assertEqual(result["status"], "preflight_required")
        self.assertIn(adapter.PREFIX + adapter.ISOLATION, result["required_ids"])
        self.assertEqual(result["context"], "")

    def test_prompt_assertion_not_proof(self):
        self.state.update(next_action="dispatch", writes_code=True, latest_message="All workers are isolated, yes")
        result = adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(result["status"], "preflight_required")

    def test_verified_dispatch_still_no_execution_authority(self):
        self.state.update(next_action="dispatch", writes_code=True, isolation_verified=True)
        result = adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["authorizes_execution"])

    def test_read_only_dispatch_not_overconstrained(self):
        self.state.update(next_action="dispatch", writes_code=False)
        result = adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(result["status"], "ok")

    def test_shipping_unknown_blocks_advisory_not_host_prompt(self):
        for action in adapter.SHIP_ACTIONS:
            self.state["next_action"] = action
            result = adapter.run(self.core, self.root, self.registry, self.state)
            self.assertEqual(result["status"], "preflight_required")
            self.assertEqual(result["context"], "")

    def test_stale_revision_cannot_be_bypassed(self):
        self.state.update(next_action="deploy", resume_integrity="verified", current_revision="new", checked_revision="old")
        result = adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(len(result["preflight_findings"]), 1)

    def test_pickup_needs_live_claim(self):
        self.state["next_action"] = "pickup"
        self.assertEqual(adapter.run(self.core, self.root, self.registry, self.state)["status"], "preflight_required")

    def test_existing_files_not_modified_by_index_route(self):
        before = self.hashes()
        adapter.run(self.core, self.root, self.registry, self.state)
        self.assertEqual(self.hashes(), before)

    def test_session_cache_not_shared(self):
        with self.assertRaises(ValueError):
            adapter.run(self.core, self.root, self.registry, self.state, session=self.core.Session("session-b"))

    def test_wrong_engine_hash_rejected(self):
        directory = self.temp_root / "fake-engine"
        directory.mkdir()
        (directory / "context_router.py").write_text("raise RuntimeError('must not import')")
        with self.assertRaises(ValueError): adapter.load_engine(directory)

    def test_missing_engine_is_visible(self):
        with self.assertRaises(OSError): adapter.load_engine(self.temp_root / "missing")

    def test_true_off_switch_before_loading_missing_engine(self):
        with patch.dict(os.environ, {"CONTEXT_ROUTER_DISABLE": "1"}), patch("sys.stdout", new_callable=io.StringIO) as out:
            result = adapter.main(["--engine", "/missing", "route", "--registry", "/missing", "--state", "/missing"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "off")

    def test_hook_off_silent_even_with_missing_files(self):
        with patch.dict(os.environ, {"CONTEXT_ROUTER_DISABLE": "1"}), patch("sys.stdout", new_callable=io.StringIO) as out:
            result = adapter.main(["--engine", "/missing", "hook", "--registry", "/missing", "--state", "/missing"])
        self.assertEqual(result, 0)
        self.assertEqual(out.getvalue(), "")

    def test_lean_preview_no_promotion_and_no_source_changes(self):
        before = self.hashes()
        target = self.temp_root / "preview"
        result = adapter.stage_lean(self.core, self.root, self.registry, ["live"], target)
        self.assertFalse(result["installed"])
        self.assertEqual(before, self.hashes())
        self.assertIn("disable-model-invocation: true", (target / adapter.ISOLATION).read_text())
        self.assertEqual((target / "skills/manual/SKILL.md").read_text(), (self.root / "skills/manual/SKILL.md").read_text())
        self.assertEqual((target / "hooks/resume-gate/synthetic.py").read_bytes(), (self.root / "hooks/resume-gate/synthetic.py").read_bytes())

    def test_lean_preview_cannot_promote_manual(self):
        with self.assertRaises(ValueError):
            adapter.stage_lean(self.core, self.root, self.registry, ["manual"], self.temp_root / "preview")

    def test_lean_preview_cannot_overwrite(self):
        with self.assertRaises(ValueError):
            adapter.stage_lean(self.core, self.root, self.registry, ["live"], self.root)

    def test_lean_preview_cannot_install_into_claude(self):
        with self.assertRaises(ValueError):
            adapter.stage_lean(self.core, self.root, self.registry, ["live"], self.temp_root / ".claude/plugin")

    def test_repository_inventory_when_full_checkout_available(self):
        root = HERE.parent
        if not (root / ".claude-plugin/plugin.json").exists():
            self.skipTest("partial local source snapshot; full repository census runs in GitHub Actions")
        registry = adapter.export(self.core, root)
        expected = list((root / "skills").glob("*/SKILL.md"))
        self.assertEqual(sum(r["kind"] == "skill" for r in registry["records"]), len(expected))
        self.assertGreater(len(expected), 0)


if __name__ == "__main__":
    unittest.main()
