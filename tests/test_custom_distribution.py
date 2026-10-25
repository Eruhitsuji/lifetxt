"""Custom final-artifact integrity and still-closed publication gates (#1417)."""

import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import custom_distribution as profile
from contrib.browser_check_poc import custom_sources as sources
from contrib.browser_check_poc.publication_gate import evaluate
from tests import test_browser_review_remediation as gate_tests


class CustomDistributionTests(unittest.TestCase):
    def test_runtime_and_source_proof_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("wasm-proof.json", "source-build-proof.json"):
                (root / name).write_bytes((profile.PROOF / name).read_bytes())
            data = json.loads((root / "wasm-proof.json").read_text())
            data["files"]["pyodide.asm.wasm"]["sha256"] = "0" * 64
            (root / "wasm-proof.json").write_bytes(sources.json_bytes(data))
            with (
                patch.object(profile, "PROOF", root),
                self.assertRaisesRegex(ValueError, "proofs disagree"),
            ):
                profile.runtime_lock()

    def fixture(self, root):
        cache, runtime = root / "sources", root / "runtime"
        cache.mkdir()
        runtime.mkdir()
        entries = []
        for original in sources.load_lock()["archives"]:
            entry = dict(original)
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                member = tarfile.TarInfo(entry["root"] + "/LICENSE")
                body = ("Synthetic test source " + entry["id"]).encode()
                member.size = len(body)
                archive.addfile(member, io.BytesIO(body))
            raw = data.getvalue()
            entry.update(
                bytes=len(raw),
                sha256=sources.sha(raw),
                required_members={"LICENSE": sources.sha(body)},
            )
            (cache / entry["file"]).write_bytes(raw)
            entries.append(entry)
        lock = {**sources.load_lock(), "archives": entries}
        runtime_lock = {}
        for name in profile.runtime_lock():
            data = ("Synthetic runtime fixture: " + name).encode()
            (runtime / name).write_bytes(data)
            runtime_lock[name] = {"bytes": len(data), "sha256": sources.sha(data)}
        return cache, runtime, lock, runtime_lock

    def test_rehashed_mutations_cannot_bless_custom_final_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache, runtime, lock, runtime_lock = self.fixture(root)
            proof = root / "profile"
            proof.mkdir()
            for path in profile.PROOF.iterdir():
                if path.is_file():
                    (proof / path.name).write_bytes(path.read_bytes())
            mapping = json.loads((proof / "mapping-attribution.json").read_text())
            mapping["source_archive_sha256"] = next(
                e["sha256"] for e in lock["archives"] if e["id"] == "cpython"
            )
            (proof / "mapping-attribution.json").write_bytes(
                sources.json_bytes(mapping)
            )
            with (
                patch.object(sources, "load_lock", return_value=lock),
                patch.object(profile, "runtime_lock", return_value=runtime_lock),
                patch.object(profile, "PROOF", proof),
            ):
                output = root / "site"
                profile.build(output, runtime, cache)
                report = profile.audit(output)
                self.assertEqual(report["integrity"], "passed")
                self.assertFalse(report["public_distribution_approved"])
                original_manifest = (output / "manifest.json").read_bytes()
                targets = [
                    "ja/check/index.html",
                    "en/check/index.html",
                    "checker/ui.mjs",
                    "checker/worker.mjs",
                    "checker/adapter.py",
                    "checker/core.zip",
                    "checker/runtime/pyodide.asm.wasm",
                    "checker/notices/icu-data-bae5ca6-LICENSE.txt",
                    "checker/notices/mapping-attribution.json",
                    "checker/sources/source-lock.json",
                    "checker/sources/" + lock["archives"][0]["file"],
                ]
                for name in targets:
                    with self.subTest(name=name):
                        path = output / name
                        old = path.read_bytes()
                        try:
                            path.write_bytes(old + b"changed")
                            manifest = json.loads(original_manifest)
                            manifest["files"][name] = {
                                "bytes": path.stat().st_size,
                                "sha256": sources.sha(path.read_bytes()),
                            }
                            (output / "manifest.json").write_bytes(
                                sources.json_bytes(manifest)
                            )
                            with self.assertRaises((ValueError, json.JSONDecodeError)):
                                profile.audit(output)
                        finally:
                            path.write_bytes(old)
                            (output / "manifest.json").write_bytes(original_manifest)
                extra = output / "checker/extra.js"
                extra.write_bytes(b"unexpected script")
                with self.assertRaises(ValueError):
                    profile.audit(output)
                extra.unlink()
                victim = output / "checker/worker.mjs"
                data = victim.read_bytes()
                victim.unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    profile.audit(output)
                victim.write_bytes(data)
                self.assertEqual(profile.audit(output)["integrity"], "passed")

    def test_owner_and_review_claims_cannot_clear_actual_mapping_acceptance(self):
        facts, record = gate_tests.PublicationGateTests().fixture()
        mapping = json.loads(profile.notice_files()["mapping-attribution.json"])
        facts.update(
            mapping_attribution=mapping,
            mapping_source_sha256=mapping["source_archive_sha256"],
        )
        report = evaluate(facts, record)
        self.assertFalse(report["public_distribution_approved"])
        self.assertFalse(report["complete_distribution_audit"])
        self.assertTrue(any("hkscs-2004" in b for b in report["blockers"]))
        self.assertTrue(any("icu-gb18030" in b for b in report["blockers"]))

    def test_acceptance_status_is_reviewed_profile_data_not_code_override(self):
        facts, record = gate_tests.PublicationGateTests().fixture()
        actual = json.loads((profile.PROOF / "mapping-attribution.json").read_text())
        synthetic = facts["mapping_attribution"]
        synthetic["source_archive_sha256"] = actual["source_archive_sha256"]
        synthetic["runtime_profile"] = "lifetxt-hkscs-free-1"
        for row in synthetic["inputs"]:
            if "resolution" in row:
                row["resolution"]["source_archive_sha256"] = actual[
                    "source_archive_sha256"
                ]
        runtime = profile.runtime_lock()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "mapping-attribution.json").write_bytes(
                sources.json_bytes(synthetic)
            )
            with (
                patch.object(profile, "PROOF", root),
                patch.object(profile, "runtime_lock", return_value=runtime),
            ):
                packaged = json.loads(
                    profile.notice_files()["mapping-attribution.json"]
                )
        facts.update(
            mapping_attribution=packaged,
            mapping_source_sha256=packaged["source_archive_sha256"],
        )
        self.assertTrue(evaluate(facts, record)["public_distribution_approved"])
        self.assertFalse(evaluate(facts, record)["authority_verified"])
        self.assertEqual(
            json.loads((profile.PROOF / "mapping-attribution.json").read_text()), actual
        )

    def test_missing_source_and_old_runtime_have_no_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "ten derived"):
                profile.build(root / "site", root / "runtime", None)
            cache, runtime, _, _ = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "differs"):
                profile.build(root / "site", runtime, cache)
            self.assertFalse((root / "site").exists())

    @unittest.skipUnless(
        os.environ.get("LIFETXT_CUSTOM_ARTIFACT"),
        "explicit actual custom artifact required",
    )
    def test_actual_rehashed_mutations_on_isolated_copy(self):
        original = Path(os.environ["LIFETXT_CUSTOM_ARTIFACT"])
        self.assertEqual(profile.audit(original)["integrity"], "passed")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "mutated"
            root.mkdir()
            for path in original.rglob("*"):
                if path.is_file():
                    target = root / path.relative_to(original)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
            self.assertEqual(profile.audit(root)["integrity"], "passed")
            manifest_path = root / "manifest.json"
            manifest_bytes = manifest_path.read_bytes()
            targets = [
                "checker/runtime/pyodide.asm.wasm",
                "checker/core.zip",
                "checker/ui.mjs",
                "ja/check/index.html",
                "checker/notices/icu-data-bae5ca6-LICENSE.txt",
                "checker/notices/mapping-attribution.json",
                "checker/sources/source-lock.json",
                "checker/sources/cpython-source.tar.gz",
                "checker/sources/pyodide-source.tar.gz",
            ]
            for name in targets:
                with self.subTest(name=name):
                    path = root / name
                    data = path.read_bytes()
                    try:
                        changed = data + b"changed"
                        path.write_bytes(changed)
                        manifest = json.loads(manifest_bytes)
                        manifest["files"][name] = {
                            "bytes": len(changed),
                            "sha256": sources.sha(changed),
                        }
                        manifest_path.write_bytes(sources.json_bytes(manifest))
                        with self.assertRaises(ValueError):
                            profile.audit(root)
                    finally:
                        path.write_bytes(data)
                        manifest_path.write_bytes(manifest_bytes)
            self.assertEqual(profile.audit(root)["integrity"], "passed")
            # Keep the extra-file case last: never rely on cleanup to recover a
            # review candidate, and never modify the caller's original artifact.
            extra = root / "checker/extra.js"
            extra.write_bytes(b"unexpected")
            manifest = json.loads(manifest_bytes)
            manifest["files"]["checker/extra.js"] = {
                "bytes": 10,
                "sha256": sources.sha(b"unexpected"),
            }
            manifest_path.write_bytes(sources.json_bytes(manifest))
            with self.assertRaises(ValueError):
                profile.audit(root)
        self.assertEqual(profile.audit(original)["integrity"], "passed")

    @unittest.skipUnless(
        os.environ.get("LIFETXT_CUSTOM_ARTIFACT"),
        "explicit actual custom artifact required",
    )
    def test_actual_custom_artifact_is_bound_and_publication_blocked(self):
        report = profile.audit(Path(os.environ["LIFETXT_CUSTOM_ARTIFACT"]))
        self.assertEqual(report["source_archives"], 10)
        self.assertFalse(report["public_distribution_approved"])
        self.assertEqual(report["runtime_files"], profile.runtime_lock())
