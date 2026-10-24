"""Independent-review regressions: final artifact, notice access and evidence gates (#1411)."""

import copy
import hashlib
import json
import re
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from urllib.parse import urlsplit

from contrib.browser_check_poc import build as builder
from contrib.browser_check_poc.distribution_audit import audit, digest
from contrib.browser_check_poc.notice_inventory import validate_notices
from contrib.browser_check_poc.publication_gate import evaluate, P1, P2
from contrib.browser_check_poc.source_probe import validate_generated_sysconfig
from scripts.build_website_checker import build
from scripts.check_website import Document


class PublicationGateTests(unittest.TestCase):
    def fixture(self):
        facts = {
            "profile": "website-checker",
            "source_clean": True,
            "source_mode": "hash-verified-self-hosted-archives",
            "commit": "a" * 40,
            "manifest_sha256": "b" * 64,
        }
        record = {
            "schema_version": 1,
            "target_commit": facts["commit"],
            "manifest_sha256": facts["manifest_sha256"],
            "implementer": "Codex",
            "findings": {
                key: {"status": "fixed", "evidence": "synthetic-test-only"}
                for key in P1 | P2
            },
            "source_retention": {
                "owner": "Eruhitsuji",
                "minimum_period": "entire-binary-distribution-period",
                "reference": "synthetic-test-only",
            },
            "reviews": [
                {
                    "type": t,
                    "reviewer": "Independent synthetic reviewer",
                    "target_commit": facts["commit"],
                    "result": "accepted",
                    "reference": "synthetic-test-only",
                }
                for t in ("implementation-distribution", "integration")
            ],
            "publication_approval": {
                "owner": "Eruhitsuji",
                "decision": "approved",
                "target_commit": facts["commit"],
                "manifest_sha256": facts["manifest_sha256"],
                "reference": "synthetic-test-only",
            },
        }
        for key in ("P2-6", "P2-7"):
            record["findings"][key].update(
                status="owner-risk-accepted",
                owner="Eruhitsuji",
                verified_scope="Official-release identity/recipes/runtime observations",
                remaining_risk="No bitwise rebuild; some upstream recipe inputs lack hash pins",
            )
        return facts, record

    def test_complete_synthetic_evidence_can_pass_without_removing_checks(self):
        facts, record = self.fixture()
        report = evaluate(facts, record)
        self.assertTrue(report["complete_distribution_audit"])
        self.assertTrue(report["public_distribution_approved"])
        self.assertEqual(report["blockers"], [])
        # Distribution review is distinct from publication permission.
        record.pop("publication_approval")
        report = evaluate(facts, record)
        self.assertTrue(report["complete_distribution_audit"])
        self.assertFalse(report["public_distribution_approved"])

    def test_each_missing_stale_self_review_or_unverified_claim_blocks(self):
        for mode in (
            "commit",
            "manifest",
            "links",
            "poc",
            "dirty",
            "identity",
            "p1",
            "p2",
            "scope",
            "risk",
            "owner",
            "self",
            "review",
            "retention",
            "approval",
        ):
            with self.subTest(mode=mode):
                facts, record = self.fixture()
                if mode == "commit":
                    record["target_commit"] = "c" * 40
                elif mode == "manifest":
                    record["manifest_sha256"] = "c" * 64
                elif mode == "links":
                    facts["source_mode"] = "pinned-upstream-acquisition-links"
                elif mode == "poc":
                    facts["profile"] = "poc"
                elif mode == "dirty":
                    facts["source_clean"] = False
                elif mode == "identity":
                    record["implementer"] = None
                elif mode == "p1":
                    record["findings"]["P1-1"]["status"] = "owner-risk-accepted"
                elif mode == "p2":
                    record["findings"].pop("P2-5")
                elif mode == "scope":
                    record["findings"]["P2-6"]["verified_scope"] = None
                elif mode == "risk":
                    record["findings"]["P2-7"]["remaining_risk"] = None
                elif mode == "owner":
                    record["findings"]["P2-7"]["owner"] = "Implementer"
                elif mode == "self":
                    record["reviews"][0]["reviewer"] = "Codex"
                elif mode == "review":
                    record["reviews"][1]["target_commit"] = "c" * 40
                elif mode == "retention":
                    record["source_retention"]["minimum_period"] = "one-day"
                else:
                    record["publication_approval"]["target_commit"] = "c" * 40
                report = evaluate(facts, record)
                self.assertFalse(report["public_distribution_approved"])
                self.assertTrue(report["blockers"])
        facts, _ = self.fixture()
        pending = json.loads(
            (builder.SOURCE / "publication-review.example.json").read_text("utf-8")
        )
        self.assertFalse(evaluate(facts, pending)["complete_distribution_audit"])


class FinalArtifactTests(unittest.TestCase):
    def source_fixture(self, root):
        source = root / "source"
        shutil.copytree(
            builder.SOURCE,
            source,
            ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
        )
        runtime = source / "node_modules/pyodide"
        runtime.mkdir(parents=True)
        (runtime / "package.json").write_text(
            json.dumps({"version": builder.VERSION}), encoding="utf-8"
        )
        inventory_path = source / "notices/components.json"
        inventory = json.loads(inventory_path.read_text("utf-8"))
        for name in builder.RUNTIME_FILES:
            (runtime / name).write_bytes(b"synthetic-runtime")
            inventory["runtime_observations"]["runtime_files"]["runtime/" + name] = (
                digest(runtime / name)
            )
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        return source

    def test_final_checker_allows_only_bound_assets_and_reachable_notices(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = self.source_fixture(root)
            clean = root / "site"
            with patch.object(builder, "SOURCE", source):
                build(clean)
            report = audit(clean, source)
            self.assertEqual(report["profile"], "website-checker")
            self.assertEqual(report["integrity"], "passed")
            self.assertFalse(report["public_distribution_approved"])
            for lang in ("ja", "en"):
                links = Document(
                    (clean / lang / "check/index.html").read_text("utf-8")
                ).links
                self.assertIn("../../checker/notices/index.html", links)
                self.assertIn("../../checker/sources/index.html", links)
            index = clean / "checker/notices/index.html"
            page = Document(index.read_text("utf-8"))
            self.assertEqual(page.errors, [])
            notices = json.loads(
                (source / "notices/provenance.json").read_text("utf-8")
            )
            self.assertEqual(len(notices["files"]), 25)
            for entry in notices["files"]:
                self.assertIn(entry["file"], page.links)
            for directory in ("notices", "sources"):
                path = clean / "checker" / directory / "index.html"
                for link in Document(path.read_text("utf-8")).links:
                    if not urlsplit(link).scheme:
                        self.assertTrue((path.parent / link).resolve().is_file(), link)
            self.assertIn(
                "../notices/index.html",
                Document(
                    (clean / "checker/sources/index.html").read_text("utf-8")
                ).links,
            )
            for name in (
                "checker/adapter.py",
                "checker/engine.mjs",
                "checker/limits.mjs",
                "checker/ui.mjs",
                "checker/worker.mjs",
                "checker/core.zip",
                "checker/runtime/pyodide.mjs",
                "checker/notices/index.html",
                "checker/notices/unicode-license-v3-2026.txt",
                "checker/sources/source-provenance.json",
                "ja/check/index.html",
                "en/check/index.html",
                "en/index.html",
                "unlisted.js",
            ):
                with self.subTest(name=name):
                    target = root / "mutated"
                    shutil.copytree(clean, target)
                    (target / name).write_bytes(b"changed-with-rehashed-manifest")
                    manifest_path = target / "manifest.json"
                    manifest = json.loads(manifest_path.read_text("utf-8"))
                    manifest["files"][name] = digest(target / name)
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(
                        (ValueError, FileNotFoundError, zipfile.BadZipFile)
                    ):
                        audit(target, source)
                    shutil.rmtree(target)

    def test_repository_document_links_and_notice_sections_resolve(self):
        for relative in ("SOURCE_DELIVERY.md", "notices/README.md"):
            document = builder.SOURCE / relative
            for link in re.findall(
                r"\[[^\]]+\]\(([^)]+)\)", document.read_text("utf-8")
            ):
                if not urlsplit(link).scheme:
                    self.assertTrue((document.parent / link).is_file(), link)
        inventory = json.loads(
            (builder.SOURCE / "notices/components.json").read_text("utf-8")
        )
        for entry in inventory["components"]:
            if entry.get("notice_section"):
                text = (builder.SOURCE / "notices" / entry["notice"]).read_text("utf-8")
                self.assertIn(entry["notice_section"], text)

    def test_introduction_validator_accepts_windows_relative_paths(self):
        from scripts.build_website import build as intro
        from scripts.check_website import check

        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "site"
            intro(output)
            original = Path.relative_to

            def windows_relative(path, *args, **kwargs):
                return PureWindowsPath(original(path, *args, **kwargs).as_posix())

            with patch.object(Path, "relative_to", windows_relative):
                self.assertEqual(check(output), [])

    def test_publication_candidate_requires_source_bundle_before_build(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "site"
            with self.assertRaisesRegex(ValueError, "source archives"):
                build(output, publication_candidate=True)
            self.assertFalse(output.exists())

    def test_unicode_provenance_rejects_unsafe_origins_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            source = self.source_fixture(Path(d))
            path = source / "notices/provenance.json"
            original = json.loads(path.read_text("utf-8"))
            for url in (
                "http://www.unicode.org/license.txt",
                "https://www.unicode.org.evil.example/license.txt",
                "https://www.unicode.org:444/license.txt",
                "https://evil@www.unicode.org/license.txt",
            ):
                value = copy.deepcopy(original)
                value["files"][-1]["source_url"] = url
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    validate_notices(source)
            path.write_text(json.dumps(original), encoding="utf-8")
            (source / "notices/unicode-license-v3-2026.txt").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                validate_notices(source)

    def test_generated_sysconfig_requires_bytes_and_build_constants(self):
        lock = {
            "generated_sysconfig": {
                "file": "_sysconfig.py",
                "sha256": "",
                "required_values": {"WITH_MIMALLOC": 1},
            }
        }
        raw = b"build_time_vars = {'WITH_MIMALLOC': 1}"
        lock["generated_sysconfig"]["sha256"] = hashlib.sha256(raw).hexdigest()
        validate_generated_sysconfig("_sysconfig.py", raw, lock)
        with self.assertRaises(ValueError):
            validate_generated_sysconfig("_sysconfig.py", raw + b"#tamper", lock)
        bad = b"build_time_vars = {'WITH_MIMALLOC': 0}"
        lock["generated_sysconfig"]["sha256"] = hashlib.sha256(bad).hexdigest()
        with self.assertRaises(ValueError):
            validate_generated_sysconfig("_sysconfig.py", bad, lock)
