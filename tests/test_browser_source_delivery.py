"""Locked source availability, tamper rejection and offline artifact boundaries (#1409)."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import source_delivery as delivery


class SourceDeliveryTests(unittest.TestCase):
    def fixture(self, root):
        source, cache = root / "source", root / "cache"
        source.mkdir()
        cache.mkdir()
        lock = copy.deepcopy(delivery.load_lock())
        for entry in lock["archives"]:
            wanted = next(iter(entry["required_members"]))
            raw = ("Synthetic source fixture: " + entry["id"]).encode()
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                member = tarfile.TarInfo(entry["root"] + "/" + wanted)
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            path = cache / entry["file"]
            path.write_bytes(buffer.getvalue())
            entry["bytes"] = path.stat().st_size
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["required_members"] = {wanted: hashlib.sha256(raw).hexdigest()}
        (source / "source-lock.json").write_text(json.dumps(lock), encoding="utf-8")
        shutil.copyfile(
            delivery.SOURCE / "SOURCE_DELIVERY.md", source / "SOURCE_DELIVERY.md"
        )
        shutil.copyfile(
            delivery.SOURCE / "source-provenance.json",
            source / "source-provenance.json",
        )
        return source, cache, lock

    def test_offline_links_and_complete_bundle_have_different_explicit_modes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, cache, lock = self.fixture(root)
            with patch(
                "urllib.request.OpenerDirector.open",
                side_effect=AssertionError("Unexpected network"),
            ):
                for mode in ("links", "bundle"):
                    output = root / mode
                    output.mkdir()
                    delivery.write_delivery(
                        output / "sources", source, cache if mode == "bundle" else None
                    )
                    report, paths = delivery.audit_delivery(output, source)
                    self.assertEqual(report["archive_count"], 10)
                    self.assertEqual(len(paths), 14 if mode == "bundle" else 4)
                    self.assertEqual(
                        report["mode"],
                        "hash-verified-self-hosted-archives"
                        if mode == "bundle"
                        else "pinned-upstream-acquisition-links",
                    )
                    self.assertFalse((output / "sources/pyodide-core.tar.bz2").exists())
                    self.assertIn(
                        "MPL-2.0", (output / "sources/index.html").read_text("utf-8")
                    )
                    self.assertNotIn(
                        "<script", (output / "sources/index.html").read_text("utf-8")
                    )

    def test_delivery_is_utf8_with_legacy_windows_default_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, cache, lock = self.fixture(root)
            output = root / "site"
            output.mkdir()
            original_read, original_write = Path.read_text, Path.write_text

            def legacy_read(path, encoding=None, **kwargs):
                return original_read(path, encoding=encoding or "cp932", **kwargs)

            def legacy_write(path, data, encoding=None, **kwargs):
                return original_write(
                    path, data, encoding=encoding or "cp932", **kwargs
                )

            with (
                patch.object(Path, "read_text", legacy_read),
                patch.object(Path, "write_text", legacy_write),
            ):
                delivery.write_delivery(output / "sources", source, cache)
                status, _ = delivery.audit_delivery(output, source)
            self.assertEqual(status["mode"], "hash-verified-self-hosted-archives")

    def test_missing_changed_partial_extra_and_rehashed_source_fail(self):
        for mode in (
            "missing",
            "tamper",
            "member",
            "partial",
            "extra",
            "metadata",
            "index",
            "symlink",
            "payload",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                source, cache, lock = self.fixture(root)
                first = lock["archives"][0]
                target = cache / first["file"]
                if mode in ("missing", "tamper", "member"):
                    if mode == "missing":
                        target.unlink()
                    elif mode == "tamper":
                        target.write_bytes(b"wrong archive bytes")
                    else:
                        # Re-hash a well-formed archive with a missing required licence.
                        with tarfile.open(target, "w:gz"):
                            pass
                        first["bytes"] = target.stat().st_size
                        first["sha256"] = hashlib.sha256(
                            target.read_bytes()
                        ).hexdigest()
                    with self.assertRaises(ValueError):
                        delivery.validate_cache(cache, lock)
                    continue
                output = root / "site"
                output.mkdir()
                delivery.write_delivery(output / "sources", source, cache)
                directory = output / "sources"
                if mode == "partial":
                    (directory / first["file"]).unlink()
                elif mode == "extra":
                    (directory / "unlisted.tar.gz").write_bytes(b"extra")
                elif mode == "metadata":
                    (directory / "source-lock.json").write_text("{}")
                elif mode == "payload":
                    (directory / first["file"]).write_bytes(b"corrupt bundled source")
                elif mode == "index":
                    (directory / "index.html").write_text("<script>bad</script>")
                else:
                    path = directory / first["file"]
                    path.unlink()
                    try:
                        path.symlink_to(target)
                    except OSError:
                        self.skipTest("Symlink creation unavailable")
                with self.assertRaises(ValueError):
                    delivery.audit_delivery(output, source)

    def test_lock_rejects_missing_component_unsafe_path_origin_and_overclaim(self):
        for mode in (
            "missing",
            "duplicate",
            "path",
            "url",
            "size",
            "hash",
            "complete",
            "approved",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                source, cache, lock = self.fixture(Path(d))
                if mode == "missing":
                    lock["archives"].pop()
                elif mode == "duplicate":
                    lock["archives"][0]["file"] = lock["archives"][1]["file"]
                elif mode == "path":
                    lock["archives"][0]["file"] = "../escape.tar.gz"
                elif mode == "url":
                    lock["archives"][0]["url"] = "https://127.0.0.1/private"
                elif mode == "size":
                    lock["archives"][0]["bytes"] = 999_999_999
                elif mode == "hash":
                    lock["archives"][0]["sha256"] = "unknown"
                elif mode == "complete":
                    lock["complete_distribution_audit"] = True
                else:
                    lock["public_distribution_approved"] = True
                (source / "source-lock.json").write_text(
                    json.dumps(lock), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    delivery.load_lock(source)
        for url in (
            "http://github.com/file",
            "https://evil.example/file",
            "https://github.com@127.0.0.1/file",
            "https://github.com:444/file",
        ):
            with self.assertRaises(ValueError):
                delivery.check_url(url)

    def test_explicit_fetch_checks_locked_bytes_and_does_not_overwrite_cache(self):
        with tempfile.TemporaryDirectory() as d:
            source, original, lock = self.fixture(Path(d))
            payloads = {
                e["url"]: (original / e["file"]).read_bytes() for e in lock["archives"]
            }

            class Opener:
                def open(self, url, timeout):
                    return io.BytesIO(payloads[url])

            cache = Path(d) / "fetched"
            with patch("urllib.request.build_opener", return_value=Opener()):
                delivery.fetch_sources(cache, lock)
                delivery.fetch_sources(cache, lock)
                self.assertEqual(
                    {p.name for p in cache.iterdir()},
                    {e["file"] for e in lock["archives"]},
                )
                first = cache / lock["archives"][0]["file"]
                first.write_bytes(b"bad existing cache")
                with self.assertRaises(ValueError):
                    delivery.fetch_sources(cache, lock)
                self.assertEqual(first.read_bytes(), b"bad existing cache")
            bad = Path(d) / "bad"

            class BadOpener:
                def open(self, url, timeout):
                    return io.BytesIO(b"unexpected payload")

            with patch("urllib.request.build_opener", return_value=BadOpener()):
                with self.assertRaises(ValueError):
                    delivery.fetch_sources(bad, lock)
            self.assertEqual(list(bad.iterdir()), [])

    def test_retained_proof_is_bound_to_current_source_and_runtime_policy(self):
        lock = delivery.load_lock()
        proof = json.loads(
            (delivery.SOURCE / "source-provenance.json").read_text("utf-8")
        )
        self.assertEqual(
            proof["source_lock_sha256"],
            hashlib.sha256(
                (delivery.SOURCE / "source-lock.json").read_bytes()
            ).hexdigest(),
        )
        inventory = json.loads(
            (delivery.SOURCE / "notices/components.json").read_text("utf-8")
        )
        self.assertEqual(
            proof["runtime_files"], inventory["runtime_observations"]["runtime_files"]
        )
        self.assertFalse(proof["complete_distribution_audit"])
        self.assertFalse(proof["public_distribution_approved"])
        self.assertEqual(
            sum(proof["stdlib_counts"].values()), len(proof["stdlib_mapping"])
        )
        self.assertEqual(len({row["file"] for row in proof["stdlib_mapping"]}), 567)
        pyodide = next(e for e in lock["archives"] if e["id"] == "pyodide")
        for patch_record in proof["cpython_patch_checks"]:
            self.assertEqual(
                patch_record["sha256"],
                pyodide["required_members"][patch_record["member"]],
            )
        from contrib.browser_check_poc.source_probe import patch_member_paths

        self.assertEqual(
            patch_member_paths(b"--- a/Lib/a.py\n+++ b/Lib/a.py\n"), {"Lib/a.py"}
        )
        for data in (
            b"--- a/../../escape\n+++ b/../../escape\n",
            b"--- /tmp/private\n+++ /tmp/private\n",
        ):
            with self.assertRaises(ValueError):
                patch_member_paths(data)

    @unittest.skipUnless(
        os.environ.get("LIFETXT_RUN_SOURCE_AUDIT") == "1",
        "Full upstream source cache audit is opt-in; no result inferred",
    )
    def test_actual_locked_release_sources_and_all_upstream_patches(self):
        from contrib.browser_check_poc.source_probe import probe

        cache = Path(os.environ["LIFETXT_SOURCE_CACHE"])
        runtime = Path(os.environ["LIFETXT_SOURCE_RUNTIME"])
        with tempfile.TemporaryDirectory() as d:
            report = probe(cache, runtime, Path(d) / "evidence.json")
            self.assertEqual(
                report,
                json.loads(
                    (delivery.SOURCE / "source-provenance.json").read_text("utf-8")
                ),
            )
            self.assertEqual(len(report["cpython_patch_checks"]), 9)
            self.assertEqual(sum(report["stdlib_counts"].values()), 567)
            self.assertFalse(report["complete_distribution_audit"])
            self.assertFalse(report["public_distribution_approved"])
