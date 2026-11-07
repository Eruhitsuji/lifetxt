"""Isolated source-only Unicode-minimal PoC tests (not binary acceptance)."""

import ast
import hashlib
import gzip
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from contrib.browser_check_poc import unicode_minimal as mod


def fixture(missing=None, symlink=False):
    content = {name: b"source" for name in mod.REQUIRED_INPUTS if name != missing}
    content.update(
        {
            "Lib/encodings/" + key + ".py": b"source"
            for key in mod.KEEP_ENCODINGS
            if key != "aliases"
        }
    )
    content["Lib/encodings/aliases.py"] = (
        b"aliases = {'u8': 'utf_8', 'gb_18030': 'gb18030', 'latin': 'latin_1'}\n"
    )
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as arc:
        for name, data in sorted(content.items()):
            item = tarfile.TarInfo(mod.ROOT + "/" + name)
            item.size = len(data)
            arc.addfile(item, io.BytesIO(data))
        if symlink:
            item = tarfile.TarInfo(mod.ROOT + "/evil")
            item.type = tarfile.SYMTYPE
            item.linkname = "../../secret"
            arc.addfile(item)
    return buf.getvalue()


def checked_curate(source, target):
    """Use fixture bytes as the synthetic expected hash only in unit tests."""
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    return mod._curate(source, target, expected, {})


class SourceOnlyTests(unittest.TestCase):
    def test_cjk_and_icu_removed_and_aliases_pruned(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            report = checked_curate(source, target)
            self.assertFalse(report["runtime_verified"])
            self.assertFalse(report["licence_resolved"])
            with tarfile.open(target, "r:gz") as archive:
                names = [member.name for member in archive]
                self.assertFalse(
                    any(
                        "/Modules/cjkcodecs/" in name
                        or "/Tools/unicode/python-mappings/" in name
                        for name in names
                    )
                )
                self.assertIn(mod.ROOT + "/Lib/encodings/utf_8.py", names)
                self.assertNotIn(mod.ROOT + "/Lib/encodings/gb18030.py", names)
                aliases = (
                    archive.extractfile(mod.ROOT + "/Lib/encodings/aliases.py")
                    .read()
                    .decode()
                )
                self.assertEqual(
                    ast.literal_eval(ast.parse(aliases).body[-1].value),
                    {"latin": "latin_1", "u8": "utf_8"},
                )
            with self.assertRaises(FileExistsError):
                checked_curate(source, target)

    def test_missing_rejects_without_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(
                fixture(missing="Tools/unicode/python-mappings/gb-18030-2000.xml")
            )
            with self.assertRaisesRegex(ValueError, "missing expected"):
                checked_curate(source, target)
            self.assertFalse(target.exists())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture(symlink=True))
            with self.assertRaisesRegex(ValueError, "non-regular"):
                checked_curate(source, target)
            self.assertFalse(target.exists())

    def test_unknown_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            with self.assertRaisesRegex(ValueError, "differs from pinned"):
                mod.curate(source, target)
            self.assertFalse(target.exists())

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "in.gz"
            source.write_bytes(fixture())
            a, b = Path(td) / "a.gz", Path(td) / "b.gz"
            self.assertEqual(
                checked_curate(source, a)["output_sha256"],
                checked_curate(source, b)["output_sha256"],
            )
            self.assertEqual(a.read_bytes(), b.read_bytes())


class ReviewRegressionTests(unittest.TestCase):
    def reject(self, payload, pattern=None):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(payload)
            with self.assertRaisesRegex(
                (ValueError, tarfile.TarError, UnicodeError, gzip.BadGzipFile),
                pattern or ".",
            ):
                checked_curate(source, target)
            self.assertFalse(target.exists())

    def extra(self, name, kind=tarfile.REGTYPE, data=b"x"):
        original = fixture()
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as src:
            with tarfile.open(fileobj=buf, mode="w:gz") as dst:
                for member in src:
                    dst.addfile(member, src.extractfile(member))
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "../../outside"
                member.size = len(data) if kind == tarfile.REGTYPE else 0
                dst.addfile(member, io.BytesIO(data) if member.size else None)
        return buf.getvalue()

    def test_unsafe_paths_duplicates_and_member_types(self):
        for name in [
            "../escape",
            "/absolute",
            mod.ROOT + "/a/../b",
            "Other/file",
            mod.ROOT + "/evil\\name",
            mod.ROOT + "/Lib/encodings/utf_8.py",
        ]:
            with self.subTest(name=name):
                self.reject(self.extra(name))
        for kind in [
            tarfile.LNKTYPE,
            tarfile.SYMTYPE,
            tarfile.CHRTYPE,
            tarfile.FIFOTYPE,
        ]:
            with self.subTest(kind=kind):
                self.reject(self.extra(mod.ROOT + "/special", kind))
        self.reject(self.extra(mod.ROOT))
        self.reject(b"not gzip")

    def test_encoding_subtree_closed(self):
        for filename in ["gb18030.pyc", "utf_8.pyi", "utf_8.txt", "nested/utf_8.py"]:
            with self.subTest(filename=filename):
                self.reject(
                    self.extra(mod.ROOT + "/Lib/encodings/" + filename),
                    "encoding subtree",
                )

    def test_alias_malformed(self):
        for blob in [
            b"x = {}",
            b"aliases = [];",
            b'aliases = {1: "utf_8"}',
            b'aliases = {"a": 1}',
            b"aliases = dict()",
            b"aliases = {}\naliases = {}",
            b"\xff",
        ]:
            with self.subTest(blob=blob), tempfile.TemporaryDirectory() as td:
                payload = io.BytesIO()
                with tarfile.open(fileobj=io.BytesIO(fixture()), mode="r:gz") as src:
                    with tarfile.open(fileobj=payload, mode="w:gz") as dst:
                        for member in src:
                            data = src.extractfile(member).read()
                            if member.name.endswith("/aliases.py"):
                                data = blob
                            member.size = len(data)
                            dst.addfile(member, io.BytesIO(data))
                self.reject(payload.getvalue())

    def test_missing_retained_codec(self):
        payload = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(fixture()), mode="r:gz") as src:
            with tarfile.open(fileobj=payload, mode="w:gz") as dst:
                for member in src:
                    if not member.name.endswith("/utf_16.py"):
                        dst.addfile(member, src.extractfile(member))
        self.reject(payload.getvalue(), "missing required")

    def test_resource_limits(self):
        from unittest.mock import patch

        cases = [
            ("MAX_ARCHIVE_BYTES", 1, "compressed"),
            ("MAX_MEMBERS", 1, "count"),
            ("MAX_MEMBER_BYTES", 1, "size"),
            ("MAX_EXPANDED_BYTES", 100, "expanded"),
        ]
        for name, limit, message in cases:
            with self.subTest(name=name), patch.object(mod, name, limit):
                self.reject(fixture(), message)

    def test_receipt_rejects_each_wrong_value_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            for key in mod.EXPECTED_RESULT:
                with (
                    self.subTest(key=key),
                    self.assertRaisesRegex(ValueError, "receipt mismatch"),
                ):
                    mod._curate(source, target, expected_hash, {key: "wrong"})
                self.assertFalse(target.exists())

    def test_production_entry_enforces_pin_and_receipt(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            with patch.object(
                mod,
                "EXPECTED_SOURCE_SHA256",
                hashlib.sha256(source.read_bytes()).hexdigest(),
            ):
                with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                    mod.curate(source, target)
            self.assertFalse(target.exists())

    def test_publish_failures_cleanup_and_no_clobber(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "out.gz"
            for operation in ["fsync", "link"]:
                with (
                    self.subTest(operation=operation),
                    patch.object(mod.os, operation, side_effect=OSError("simulated")),
                ):
                    with self.assertRaises(OSError):
                        mod._publish(b"complete", target)
                self.assertEqual(list(Path(td).iterdir()), [])
            target.symlink_to(Path(td) / "missing")
            with self.assertRaises(FileExistsError):
                mod._publish(b"complete", target)
            self.assertTrue(target.is_symlink())
            self.assertFalse((Path(td) / "missing").exists())
            self.assertEqual(len(list(Path(td).iterdir())), 1)

    def test_retained_hash_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            report = checked_curate(source, target)
            with tarfile.open(target, "r:gz") as archive:
                expected = {
                    m.name.removeprefix(mod.ROOT + "/"): hashlib.sha256(
                        archive.extractfile(m).read()
                    ).hexdigest()
                    for m in archive
                }
            self.assertEqual(report["retained_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
