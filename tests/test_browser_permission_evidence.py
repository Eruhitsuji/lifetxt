"""Source-specific permission evidence is reproducible, not a fabricated approval (#1413)."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import permission_probe as probe
from contrib.browser_check_poc.publication_gate import mapping_blockers
from contrib.browser_check_poc.source_delivery import load_lock


class PermissionEvidenceTests(unittest.TestCase):
    def test_custom_source_verification_reads_curated_archive_and_keeps_acceptance_pending(
        self,
    ):
        from contrib.browser_check_poc import custom_sources
        import tarfile

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache, sources, notice = root / "cache", root / "sources", root / "notices"
            for path in (cache, sources, notice):
                path.mkdir()
            raw = b"<mapping/>\n"
            bodies = {
                "icu-xml": raw,
                "icu-license": b"Synthetic grant",
                "icu-repository-readme": b"released under [LICENSE]",
                "icu-charset-readme": b"Synthetic charset scope",
            }
            rows = []
            for key, data in bodies.items():
                (cache / key).write_bytes(data)
                rows.append(
                    {
                        "id": key,
                        "file": key,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
            (notice / "grant.txt").write_bytes(bodies["icu-license"])
            archive = sources / "curated.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                item = tarfile.TarInfo("curated/mapping.xml")
                item.size = len(raw) + 1
                tar.addfile(item, io.BytesIO(raw + b"\n"))
            entry = {
                "id": "cpython",
                "file": archive.name,
                "root": "curated",
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "required_members": {
                    "mapping.xml": hashlib.sha256(raw + b"\n").hexdigest()
                },
                "base_upstream_sha256": "a" * 64,
            }
            metadata = {
                "inputs": rows,
                "cpython_member": "mapping.xml",
                "license_notice": "grant.txt",
                "icu_data_commit": "b" * 40,
            }
            with (
                patch.object(probe, "evidence", return_value=metadata),
                patch.object(
                    custom_sources, "load_lock", return_value={"archives": [entry]}
                ),
                patch.object(
                    probe,
                    "load_lock",
                    side_effect=AssertionError("old source lock used"),
                ),
            ):
                result = probe.verify(cache, sources, root, custom_source_profile=True)
                self.assertEqual(result["cpython_archive_sha256"], entry["sha256"])
                self.assertEqual(result["base_upstream_cpython_sha256"], "a" * 64)
                self.assertEqual(result["independent_permission_acceptance"], "pending")
                self.assertFalse(result["public_distribution_approved"])
                archive.write_bytes(archive.read_bytes() + b"changed")
                with self.assertRaises(ValueError):
                    probe.verify(cache, sources, root, custom_source_profile=True)

    def test_exact_xml_correspondence_allows_only_the_recorded_single_lf(self):
        self.assertIn(
            "all other bytes identical",
            probe.compare_xml(b"<mapping/>\n\n", b"<mapping/>\n"),
        )
        for raw in (
            b"<mapping/>\n",
            b"<mapping/>\n\n\n",
            b"<changed/>\n\n",
            b"<mapping/> \n\n",
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                probe.compare_xml(raw, b"<mapping/>\n")

    def test_changed_origin_paths_sizes_and_inventories_are_rejected(self):
        original = probe.evidence()
        for mode in (
            "url",
            "path",
            "duplicate",
            "missing",
            "size",
            "notice",
            "revision",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                source = Path(d)
                (source / "notices").mkdir()
                value = copy.deepcopy(original)
                if mode == "url":
                    value["inputs"][0]["url"] = "https://127.0.0.1/private"
                elif mode == "path":
                    value["inputs"][0]["file"] = "../escape"
                elif mode == "duplicate":
                    value["inputs"][0]["id"] = value["inputs"][1]["id"]
                elif mode == "missing":
                    value["inputs"].pop()
                elif mode == "size":
                    value["inputs"][0]["bytes"] = 2_000_000
                elif mode == "notice":
                    value["license_notice"] = "../private"
                else:
                    value["icu_data_commit"] = "main"
                (source / "notices/mapping-attribution.json").write_text(
                    json.dumps({"permission_evidence": value}), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    probe.evidence(source)

    def test_fetch_is_explicit_bounded_and_never_accepts_bad_bytes(self):
        value = {
            "inputs": [
                {
                    "file": "sample.txt",
                    "url": "https://raw.githubusercontent.com/unicode-org/icu-data/fixed/LICENSE",
                    "bytes": 7,
                    "sha256": hashlib.sha256(b"fixture").hexdigest(),
                }
            ]
        }

        class Opener:
            def open(self, url, timeout):
                return io.BytesIO(b"fixture")

        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(probe, "evidence", return_value=value),
        ):
            cache = Path(d)
            with patch("urllib.request.build_opener", return_value=Opener()):
                probe.fetch(cache)
                probe.fetch(cache)
                self.assertEqual((cache / "sample.txt").read_bytes(), b"fixture")
                (cache / "sample.txt").write_bytes(b"corrupt")
                with self.assertRaises(ValueError):
                    probe.fetch(cache)
                self.assertEqual((cache / "sample.txt").read_bytes(), b"corrupt")

        class BadOpener:
            def open(self, url, timeout):
                return io.BytesIO(b"unexpected payload")

        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(probe, "evidence", return_value=value),
            patch("urllib.request.build_opener", return_value=BadOpener()),
        ):
            cache = Path(d)
            with self.assertRaises(ValueError):
                probe.fetch(cache)
            self.assertEqual(list(cache.iterdir()), [])

    def test_located_licence_does_not_silently_remove_independent_acceptance_gate(self):
        source = probe.SOURCE
        mapping = json.loads(
            (source / "notices/mapping-attribution.json").read_text("utf-8")
        )
        cpython = next(e for e in load_lock()["archives"] if e["id"] == "cpython")
        blockers = mapping_blockers(mapping, cpython["sha256"])
        self.assertTrue(any("icu-gb18030" in b for b in blockers))
        self.assertTrue(any("hkscs-2004" in b for b in blockers))
        self.assertEqual(
            mapping["permission_evidence"]["candidate_status"],
            "source-specific-grant-located-independent-acceptance-pending",
        )
        self.assertFalse(mapping["permission_evidence"]["public_distribution_approved"])
        notice = source / "notices" / mapping["permission_evidence"]["license_notice"]
        self.assertIn(b"ICU 1.8.1 to ICU 57.1", notice.read_bytes())

    @unittest.skipUnless(
        os.environ.get("LIFETXT_PERMISSION_CACHE"),
        "Explicit pinned permission-data cache required; no upstream result inferred",
    )
    def test_actual_official_icu_data_and_cpython_correspondence(self):
        result = probe.verify(
            Path(os.environ["LIFETXT_PERMISSION_CACHE"]),
            Path(os.environ["LIFETXT_SOURCE_CACHE"]),
        )
        self.assertTrue(result["licence_bytes_match"])
        self.assertEqual(result["independent_permission_acceptance"], "pending")
        self.assertFalse(result["hkscs_new_permission_received"])
        self.assertFalse(result["public_distribution_approved"])
