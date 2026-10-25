"""Explicit rebuilt runtime identity, byte binding and closed approval gate (#1427)."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import custom_distribution as profile
from contrib.browser_check_poc import custom_sources as sources
from contrib.browser_check_poc.distribution_audit import audit
from scripts.build_website_checker import build


class RebuildProfileTests(unittest.TestCase):
    def test_profile_identity_and_source_recipe_are_separate(self):
        new = profile.runtime_lock(profile.REBUILD_RUNTIME_PROFILE)
        old = profile.runtime_lock()
        self.assertEqual(sum(new[k] != old[k] for k in old), 3)
        metadata = profile.source_metadata(profile.REBUILD_RUNTIME_PROFILE)
        lock = json.loads(metadata["source-lock.json"])
        self.assertEqual(lock["archives"], sources.load_lock()["archives"])
        self.assertEqual(lock["runtime_profile"], profile.REBUILD_RUNTIME_PROFILE)
        self.assertEqual(lock["source_recipe_profile"], profile.DEFAULT_RUNTIME_PROFILE)
        proof = json.loads(metadata["source-build-proof.json"])
        self.assertEqual(proof["runtime_files"], new)
        self.assertEqual(proof["profile"], profile.DEFAULT_RUNTIME_PROFILE)
        self.assertIn("staging_input_check", proof)
        self.assertEqual(
            json.loads(metadata["icu-proof.json"])["independent_permission_acceptance"],
            "pending",
        )

    def test_unknown_profile_and_missing_runtime_fail_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "site"
            with self.assertRaisesRegex(ValueError, "requires runtime"):
                build(output, hkscs_profile=profile.REBUILD_RUNTIME_PROFILE)
            with self.assertRaisesRegex(ValueError, "unknown"):
                profile.build(output, Path(temp), None, runtime_profile="profile3")
            self.assertFalse(output.exists())

    def test_live_proof_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "profiles/hkscs-free-2"
            shutil.copytree(profile.SOURCE / "profiles/hkscs-free-2", target)
            for name in (
                "profile.json",
                "candidate.json",
                "source-build-proof.json",
                "wasm-proof.json",
                "runtime-observations.json",
                "icu-proof.json",
                "mapping-attribution.json",
            ):
                with self.subTest(name=name):
                    path = target / name
                    original = path.read_bytes()
                    path.write_bytes(original + b" ")
                    try:
                        with (
                            patch.object(profile, "SOURCE", root),
                            self.assertRaisesRegex(ValueError, "drift"),
                        ):
                            profile.runtime_lock(profile.REBUILD_RUNTIME_PROFILE)
                    finally:
                        path.write_bytes(original)

    @unittest.skipUnless(
        os.environ.get("LIFETXT_PROFILE2_ARTIFACT"), "actual profile2 artifact required"
    )
    def test_actual_artifact_rehashed_mutations_and_crossed_runtime(self):
        original = Path(os.environ["LIFETXT_PROFILE2_ARTIFACT"])
        report = audit(original)
        self.assertEqual(report["profile"], profile.REBUILD_PROFILE)
        self.assertEqual(report["integrity"], "passed")
        self.assertFalse(report["complete_distribution_audit"])
        self.assertFalse(report["public_distribution_approved"])
        with self.assertRaisesRegex(ValueError, "differs"):
            profile.check_runtime(original / "checker/runtime")
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            profile.audit(original, runtime_profile=profile.DEFAULT_RUNTIME_PROFILE)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "site"
            shutil.copytree(original, root)
            manifest_path = root / "manifest.json"
            manifest_bytes = manifest_path.read_bytes()
            targets = [
                "ja/check/index.html",
                "en/check/index.html",
                "checker/worker.mjs",
                "checker/core.zip",
                "checker/runtime/pyodide.asm.wasm",
                "checker/notices/mapping-attribution.json",
                "checker/sources/profile.json",
                "checker/sources/source-build-proof.json",
                "checker/sources/icu-proof.json",
                "checker/sources/source-lock.json",
                "checker/sources/cpython-source.tar.gz",
                "checker/sources/pyodide-source.tar.gz",
            ]
            for name in targets:
                with self.subTest(name=name):
                    path = root / name
                    raw = path.read_bytes()
                    try:
                        path.write_bytes(raw + b"changed")
                        manifest = json.loads(manifest_bytes)
                        manifest["files"][name] = {
                            "bytes": path.stat().st_size,
                            "sha256": sources.sha(path.read_bytes()),
                        }
                        manifest_path.write_bytes(sources.json_bytes(manifest))
                        with self.assertRaises((ValueError, json.JSONDecodeError)):
                            audit(root)
                    finally:
                        path.write_bytes(raw)
                        manifest_path.write_bytes(manifest_bytes)
            victim = root / "checker/worker.mjs"
            raw = victim.read_bytes()
            victim.unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                audit(root)
            victim.symlink_to(original.resolve() / "checker/worker.mjs")
            with self.assertRaisesRegex(ValueError, "Symlinks"):
                audit(root)
            victim.unlink()
            victim.write_bytes(raw)
            extra = root / "extra.js"
            extra.write_text("unexpected")
            manifest = json.loads(manifest_bytes)
            manifest["files"]["extra.js"] = {
                "bytes": 10,
                "sha256": sources.sha(extra.read_bytes()),
            }
            manifest_path.write_bytes(sources.json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "allowlist"):
                audit(root)
            extra.unlink()
            manifest_path.write_bytes(manifest_bytes)
            self.assertEqual(audit(root)["integrity"], "passed")
