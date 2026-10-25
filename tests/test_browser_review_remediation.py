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
from contrib.browser_check_poc.publication_gate import evaluate, P1, P2, NEW_P2
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
        mapping = json.loads(
            (builder.SOURCE / "notices/mapping-attribution.json").read_text("utf-8")
        )
        for entry in mapping["inputs"]:
            if entry["id"] in {"hkscs-2004", "icu-gb18030"}:
                entry["review_status"] = "resolved-terms-confirmed"
                entry["resolution"] = {
                    "status": "resolved-terms-confirmed",
                    "source_id": entry["id"],
                    "source_archive_sha256": mapping["source_archive_sha256"],
                    "owner": "Eruhitsuji",
                    "basis": "Synthetic terms permission evidence for regression only",
                    "verified_scope": "Synthetic fixed CPython mapping source",
                    "remaining_risk": "Synthetic owner claims are not authenticated or legal clearance",
                    "evidence_reference": "https://github.com/Eruhitsuji/lifetxt/issues/1398#issuecomment-123",
                    "independent_review_reference": "https://github.com/Eruhitsuji/lifetxt/pull/1412#issuecomment-123",
                }
        facts["mapping_attribution"] = mapping
        facts["mapping_source_sha256"] = mapping["source_archive_sha256"]
        record = {
            "schema_version": 2,
            "target_commit": facts["commit"],
            "manifest_sha256": facts["manifest_sha256"],
            "implementer_tools": ["codex"],
            "findings": {
                key: {
                    "status": "fixed",
                    "evidence": "https://github.com/Eruhitsuji/lifetxt/issues/1398#issuecomment-123",
                }
                for key in P1 | P2 | NEW_P2
            },
            "source_retention": {
                "owner": "Eruhitsuji",
                "minimum_period": "entire-binary-distribution-period",
                "reference": "https://github.com/Eruhitsuji/lifetxt/pull/1412#issuecomment-123",
            },
            "reviews": [
                {
                    "type": t,
                    "reviewer_login": "Eruhitsuji",
                    "reviewer_kind": "ai-assisted",
                    "reviewer_tool": "claude-code",
                    "target_commit": facts["commit"],
                    "result": "accepted",
                    "reference": "https://github.com/Eruhitsuji/lifetxt/pull/1412#issuecomment-123",
                }
                for t in ("implementation-distribution", "integration")
            ],
            "publication_approval": {
                "owner": "Eruhitsuji",
                "decision": "approved",
                "target_commit": facts["commit"],
                "manifest_sha256": facts["manifest_sha256"],
                "reference": "https://github.com/Eruhitsuji/lifetxt/pull/1412#issuecomment-123",
            },
        }
        for key in ("P2-6", "P2-7", "N-3"):
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
        self.assertFalse(report["authority_verified"])
        self.assertTrue(report["human_reference_verification_required"])
        self.assertEqual(report["record_shape_and_binding"], "passed")
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
                    record["implementer_tools"] = []
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
                    record["reviews"][0]["reviewer_tool"] = "Codex"
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

    def test_reported_case_alias_identity_and_reference_bypasses_fail(self):
        for mode in (
            "case-tool",
            "case-login",
            "alias-implementer",
            "evidence-x",
            "reference-x",
            "external-url",
            "bad-owner",
        ):
            with self.subTest(mode=mode):
                facts, record = self.fixture()
                if mode == "case-tool":
                    record["reviews"][0]["reviewer_tool"] = "CoDeX"
                elif mode == "case-login":
                    record["reviews"][0].update(
                        reviewer_login="codex",
                        reviewer_kind="human",
                        reviewer_tool=None,
                    )
                elif mode == "alias-implementer":
                    record["implementer_tools"] = ["another-tool"]
                elif mode == "evidence-x":
                    for e in record["findings"].values():
                        e["evidence"] = "x"
                elif mode == "reference-x":
                    record["reviews"][0]["reference"] = "x"
                elif mode == "external-url":
                    record["reviews"][0]["reference"] = (
                        "https://github.com/other/repo/pull/1#issuecomment-123"
                    )
                else:
                    record["publication_approval"]["owner"] = "other-person"
                self.assertFalse(
                    evaluate(facts, record)["public_distribution_approved"]
                )
        facts, record = self.fixture()
        record["reviews"][0]["reviewer_login"] = "ERUHITSUJI"
        record["source_retention"]["owner"] = "eruhitsuji"
        self.assertTrue(evaluate(facts, record)["public_distribution_approved"])

    def test_n7_current_blockers_override_valid_owner_acceptance_record(self):
        facts, record = self.fixture()
        original = json.loads(
            (builder.SOURCE / "notices/mapping-attribution.json").read_text("utf-8")
        )
        facts["mapping_attribution"] = original
        report = evaluate(facts, record)
        self.assertFalse(report["complete_distribution_audit"])
        self.assertFalse(report["public_distribution_approved"])
        for source_id in ("hkscs-2004", "icu-gb18030"):
            self.assertTrue(any(source_id in b for b in report["blockers"]))
        for source_id in ("hkscs-2004", "icu-gb18030"):
            partial = copy.deepcopy(facts)
            original_entry = next(
                e
                for e in partial["mapping_attribution"]["inputs"]
                if e["id"] == source_id
            )
            resolved_entry = next(
                e
                for e in self.fixture()[0]["mapping_attribution"]["inputs"]
                if e["id"] == source_id
            )
            original_entry.update(
                review_status=resolved_entry["review_status"],
                resolution=resolved_entry["resolution"],
            )
            self.assertFalse(evaluate(partial, record)["public_distribution_approved"])

    def test_n7_invalid_source_resolution_and_stale_pin_fail_closed(self):
        for mode in (
            "missing",
            "sha",
            "duplicate",
            "removed",
            "benign-pending",
            "unresolved-override",
            "no-resolution",
            "source-id",
            "resolution-sha",
            "owner",
            "scope",
            "risk",
            "basis",
            "evidence",
            "independent",
            "unknown-status",
        ):
            with self.subTest(mode=mode):
                facts, record = self.fixture()
                mapping = facts["mapping_attribution"]
                row = next(e for e in mapping["inputs"] if e["id"] == "hkscs-2004")
                evidence = row["resolution"]
                if mode == "missing":
                    facts.pop("mapping_attribution")
                elif mode == "sha":
                    facts["mapping_source_sha256"] = "c" * 64
                elif mode == "duplicate":
                    mapping["inputs"].append(copy.deepcopy(row))
                elif mode == "removed":
                    mapping["inputs"].remove(row)
                elif mode == "benign-pending":
                    row["review_status"] = "independent-acceptance-pending"
                elif mode == "unresolved-override":
                    row["review_status"] = (
                        "unresolved-permission-scope-publication-blocker"
                    )
                elif mode == "no-resolution":
                    row.pop("resolution")
                elif mode == "source-id":
                    evidence["source_id"] = "icu-gb18030"
                elif mode == "resolution-sha":
                    evidence["source_archive_sha256"] = "c" * 64
                elif mode == "owner":
                    evidence["owner"] = "Codex"
                elif mode == "scope":
                    evidence["verified_scope"] = ""
                elif mode == "risk":
                    evidence["remaining_risk"] = ""
                elif mode == "basis":
                    evidence["basis"] = "Owner accepts risk"
                elif mode == "evidence":
                    evidence["evidence_reference"] = "placeholder"
                elif mode == "independent":
                    evidence["independent_review_reference"] = None
                else:
                    row["review_status"] = "approved"
                report = evaluate(facts, record)
                self.assertFalse(report["complete_distribution_audit"])
                self.assertFalse(report["public_distribution_approved"])
                self.assertTrue(report["blockers"])

    def test_n7_synthetic_positive_does_not_change_actual_licence_assessment(self):
        facts, record = self.fixture()
        self.assertTrue(evaluate(facts, record)["public_distribution_approved"])
        self.assertFalse(evaluate(facts, record)["authority_verified"])
        current = json.loads(
            (builder.SOURCE / "notices/mapping-attribution.json").read_text("utf-8")
        )
        self.assertFalse(current["complete_distribution_audit"])
        self.assertFalse(current["public_distribution_approved"])
        self.assertEqual(
            {
                e["id"]
                for e in current["inputs"]
                if e["review_status"].endswith("publication-blocker")
            },
            {"hkscs-2004", "icu-gb18030"},
        )


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
            self.assertEqual(len(notices["files"]), 29)
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

    def test_host_encoding_and_crlf_defaults_do_not_change_final_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = self.source_fixture(root)
            a, b = root / "unix", root / "windows"
            with patch.object(builder, "SOURCE", source):
                build(a)
                original_read, original_write = Path.read_text, Path.write_text

                def windows_read(path, encoding=None, **kwargs):
                    return original_read(path, encoding=encoding or "cp932", **kwargs)

                def windows_write(path, text, encoding=None, newline=None, **kwargs):
                    return original_write(
                        path,
                        text,
                        encoding=encoding or "cp932",
                        newline="\r\n" if newline is None else newline,
                        **kwargs,
                    )

                with (
                    patch.object(Path, "read_text", windows_read),
                    patch.object(Path, "write_text", windows_write),
                ):
                    build(b)
                    self.assertEqual(audit(b, source)["integrity"], "passed")
            files = [p.relative_to(a) for p in a.rglob("*") if p.is_file()]
            self.assertTrue(files)
            for name in files:
                self.assertEqual(
                    (a / name).read_bytes(), (b / name).read_bytes(), str(name)
                )
            with zipfile.ZipFile(a / "checker/core.zip") as archive:
                self.assertTrue(
                    all(
                        i.create_system == 3 and i.compress_type == zipfile.ZIP_STORED
                        for i in archive.infolist()
                    )
                )
            # Original notices may intentionally have CRLF; generated indexes do not.
            for name in (
                "checker/notices/index.html",
                "checker/sources/index.html",
                "ja/check/index.html",
                "manifest.json",
            ):
                self.assertNotIn(b"\r\n", (b / name).read_bytes())
            source_document = (b / "checker/sources/SOURCE_DELIVERY.md").read_bytes()
            self.assertNotIn(b"/blob/main/", source_document)
            import subprocess

            sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=builder.ROOT, text=True
            ).strip()
            self.assertIn(("/blob/" + sha + "/").encode(), source_document)

    def test_rehashed_core_zip_trailing_bytes_and_zip_metadata_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = self.source_fixture(root)
            site = root / "site"
            with patch.object(builder, "SOURCE", source):
                build(site)
            core = site / "checker/core.zip"
            original = core.read_bytes()
            for mode in ("trailing", "zip-comment"):
                with self.subTest(mode=mode):
                    core.write_bytes(original)
                    if mode == "trailing":
                        core.write_bytes(original + b"appended garbage")
                    else:
                        with zipfile.ZipFile(core, "a") as archive:
                            archive.comment = b"unreviewed ZIP metadata"
                    manifest_path = site / "manifest.json"
                    manifest = json.loads(manifest_path.read_text("utf-8"))
                    manifest["files"]["checker/core.zip"] = digest(core)
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Core ZIP bytes"):
                        audit(site, source)

    def test_mapping_sources_and_terms_evidence_remain_separate_and_hash_bound(self):
        source = builder.SOURCE
        lock = json.loads((source / "source-lock.json").read_text("utf-8"))
        cpython = next(e for e in lock["archives"] if e["id"] == "cpython")
        data = json.loads(
            (source / "notices/mapping-attribution.json").read_text("utf-8")
        )
        self.assertEqual(data["source_archive_sha256"], cpython["sha256"])
        rows = {e["id"]: e for e in data["inputs"]}
        self.assertEqual(
            set(rows),
            {
                "ucd-16-and-3.2",
                "unicode-mappings",
                "hkscs-2004",
                "icu-gb18030",
                "jis-x-0213",
                "gb2312",
            },
        )
        self.assertIn("3.2.0", rows["ucd-16-and-3.2"]["origin"])
        for key in ("hkscs-2004", "icu-gb18030"):
            self.assertTrue(rows[key]["review_status"].startswith("unresolved-"))
        for row in rows.values():
            for member in row["evidence_members"]:
                self.assertEqual(
                    cpython["required_members"][member["member"]], member["sha256"]
                )
        self.assertFalse(data["public_distribution_approved"])

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
