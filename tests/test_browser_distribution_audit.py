"""Distribution integrity and fail-closed publication for #1398."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import build as builder
from contrib.browser_check_poc.distribution_audit import audit


class DistributionAuditTests(unittest.TestCase):
    def test_artifact_mutations_and_false_source_clearance_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            shutil.copytree(
                builder.SOURCE,
                source,
                ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
            )
            runtime = source / "node_modules/pyodide"
            runtime.mkdir(parents=True)
            (runtime / "package.json").write_text(
                json.dumps({"version": builder.VERSION})
            )
            import hashlib

            bound = {"bytes": 7, "sha256": hashlib.sha256(b"fixture").hexdigest()}
            inventory_path = source / "notices/components.json"
            inventory = json.loads(inventory_path.read_text("utf-8"))
            for name in builder.RUNTIME_FILES:
                (runtime / name).write_bytes(b"fixture")
                inventory["runtime_observations"]["runtime_files"][
                    "runtime/" + name
                ] = bound
            inventory_path.write_text(json.dumps(inventory))
            clean = Path(directory) / "clean"
            with patch.object(builder, "SOURCE", source):
                builder.build(clean)
            report = audit(clean, source)
            self.assertEqual(report["integrity"], "passed")
            self.assertEqual(report["publication"], "blocked")
            self.assertFalse(report["complete_distribution_audit"])
            for mutation in (
                "extra",
                "missing",
                "hash",
                "runtime",
                "symlink",
                "core",
                "notice",
                "asset",
                "lock",
                "runtime-coverage",
            ):
                with self.subTest(mutation=mutation):
                    artifact = Path(directory) / mutation
                    shutil.copytree(clean, artifact)
                    manifest_path = artifact / "manifest.json"
                    manifest = json.loads(manifest_path.read_text("utf-8"))
                    if mutation == "extra":
                        (artifact / "unapproved.mjs").write_text("alert(1)")
                    elif mutation == "missing":
                        (artifact / "notices/hiwire-6a1e672.txt").unlink()
                    elif mutation == "hash":
                        (artifact / "core.zip").write_bytes(b"tampered")
                    elif mutation == "symlink":
                        (artifact / "alias").symlink_to(artifact / "core.zip")
                    elif mutation == "core":
                        manifest["core_modules"] = []
                    elif mutation == "runtime-coverage":
                        original_inventory = inventory_path.read_bytes()
                        broken = json.loads(original_inventory)
                        broken["runtime_observations"]["runtime_files"] = {}
                        inventory_path.write_text(json.dumps(broken))
                        target = artifact / "notices/components.json"
                        target.write_bytes(inventory_path.read_bytes())
                        from contrib.browser_check_poc.distribution_audit import digest

                        manifest["files"]["notices/components.json"] = digest(target)
                    elif mutation == "lock":
                        lock_path = source / "package-lock.json"
                        original_lock = lock_path.read_bytes()
                        lock = json.loads(original_lock)
                        lock["packages"]["node_modules/pyodide"]["version"] = "latest"
                        lock_path.write_text(json.dumps(lock), encoding="utf-8")
                    else:
                        name = {
                            "runtime": "runtime/pyodide.mjs",
                            "notice": "notices/hiwire-6a1e672.txt",
                            "asset": "worker.mjs",
                        }[mutation]
                        (artifact / name).write_bytes(b"changed with matching manifest")
                        from contrib.browser_check_poc.distribution_audit import digest

                        manifest["files"][name] = digest(artifact / name)
                    manifest_path.write_text(json.dumps(manifest))
                    try:
                        with self.assertRaises(ValueError):
                            audit(artifact, source)
                    finally:
                        if mutation == "lock":
                            lock_path.write_bytes(original_lock)
                        elif mutation == "runtime-coverage":
                            inventory_path.write_bytes(original_inventory)
