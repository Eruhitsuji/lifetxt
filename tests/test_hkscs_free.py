"""HKSCS source removal, fixed inputs and fail-closed output (#1415)."""

import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import hkscs_free as profile
from contrib.browser_check_poc import hkscs_free_build as builder
import zipfile


class HkscsFreeTests(unittest.TestCase):
    def test_embed_overwrites_an_existing_generated_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, data in {
                "src/js/generated/_pyodide.out.js": b"inner();\n",
                "src/core/stack_switching/stack_switching.out.js": b"stack();\n",
                "src/core/pre.js": b"pre();\n",
            }.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            output = root / "src/core/pyodide_pre.gen.dat"
            output.write_bytes(b"stale duplicate data")
            builder.embed(root)
            first = output.read_bytes()
            builder.embed(root)
            self.assertEqual(first, output.read_bytes())
            self.assertEqual(first.count(b"inner();"), 1)
            self.assertEqual(first.count(b"pyodide_js_init();"), 1)

    def test_stdlib_zip_is_complete_and_independent_of_source_mtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tools").mkdir()
            (root / "tools/create_zipfile.py").write_text(
                "def default_filterfunc(*args):\n"
                "    return lambda directory, names: set()\n"
            )
            library = root / "lib"
            (library / "encodings").mkdir(parents=True)
            first = library / "encodings/__init__.py"
            first.write_bytes("日本語".encode())
            before = Path.cwd()
            try:
                os.chdir(root)
                builder.stdlib([library], [], [], root / "one.zip", 6)
                os.utime(first, (1_500_000_000, 1_500_000_000))
                builder.stdlib([library], [], [], root / "two.zip", 6)
            finally:
                os.chdir(before)
            self.assertEqual(
                (root / "one.zip").read_bytes(), (root / "two.zip").read_bytes()
            )
            with zipfile.ZipFile(root / "one.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    archive.read("encodings/__init__.py"), "日本語".encode()
                )
                self.assertEqual(
                    archive.getinfo("encodings/__init__.py").create_system, 3
                )

    def fixture(self, root, omit=None):
        source = root / "input.tar.gz"
        bodies = {name: b"synthetic mapping input" for name in profile.REMOVED}
        bodies["Lib/encodings/aliases.py"] = b"before\n" + profile.ALIASES + b"after\n"
        bodies["LICENSE"] = b"Retained original licensing"
        bodies["Lib/encodings/shift_jis.py"] = b"Retained Japanese codec"
        with tarfile.open(source, "w:gz") as tar:
            for name, body in bodies.items():
                if name == omit:
                    continue
                member = tarfile.TarInfo(profile.ROOT + "/" + name)
                member.size = len(body)
                tar.addfile(member, io.BytesIO(body))
        entry = {
            "id": "cpython",
            "bytes": source.stat().st_size,
            "sha256": profile.digest(source.read_bytes()),
        }
        (root / "source-lock.json").write_text(json.dumps({"archives": [entry]}))
        return source, bodies

    def test_curated_source_has_no_table_wrapper_samples_or_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, bodies = self.fixture(root)
            with patch.object(profile, "HERE", root):
                first = profile.prepare(source, root / "one")
                second = profile.prepare(source, root / "two")
            self.assertEqual(first, second)
            self.assertEqual(
                (root / "one/cpython-hkscs-free.tar.gz").read_bytes(),
                (root / "two/cpython-hkscs-free.tar.gz").read_bytes(),
            )
            with tarfile.open(root / "one/cpython-hkscs-free.tar.gz") as tar:
                actual = {
                    m.name.removeprefix(profile.ROOT + "/"): tar.extractfile(m).read()
                    for m in tar
                }
            self.assertFalse(profile.REMOVED.intersection(actual))
            self.assertEqual(actual["Lib/encodings/aliases.py"], b"before\nafter\n")
            for name in ("LICENSE", "Lib/encodings/shift_jis.py"):
                self.assertEqual(actual[name], bodies[name])
            self.assertFalse(first["runtime_verified"])
            self.assertFalse(first["public_distribution_approved"])

    def test_tampered_input_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _ = self.fixture(root)
            source.write_bytes(source.read_bytes() + b"changed")
            with (
                patch.object(profile, "HERE", root),
                self.assertRaisesRegex(ValueError, "does not match"),
            ):
                profile.prepare(source, root / "out")
            self.assertFalse((root / "out").exists())

    def test_incomplete_input_cannot_claim_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _ = self.fixture(root, "Modules/cjkcodecs/mappings_hk.h")
            with (
                patch.object(profile, "HERE", root),
                self.assertRaisesRegex(ValueError, "missing HKSCS"),
            ):
                profile.prepare(source, root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
