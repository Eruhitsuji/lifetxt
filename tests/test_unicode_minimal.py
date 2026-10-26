"""Isolated source-only Unicode-minimal PoC tests (not binary acceptance)."""

import ast
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


class SourceOnlyTests(unittest.TestCase):
    def test_cjk_and_icu_removed_and_aliases_pruned(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture())
            report = mod.curate(source, target)
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
                mod.curate(source, target)

    def test_missing_rejects_without_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(
                fixture(missing="Tools/unicode/python-mappings/gb-18030-2000.xml")
            )
            with self.assertRaisesRegex(ValueError, "missing expected"):
                mod.curate(source, target)
            self.assertFalse(target.exists())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source, target = Path(td) / "in.gz", Path(td) / "out.gz"
            source.write_bytes(fixture(symlink=True))
            with self.assertRaisesRegex(ValueError, "non-regular"):
                mod.curate(source, target)
            self.assertFalse(target.exists())

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "in.gz"
            source.write_bytes(fixture())
            a, b = Path(td) / "a.gz", Path(td) / "b.gz"
            self.assertEqual(
                mod.curate(source, a)["output_sha256"],
                mod.curate(source, b)["output_sha256"],
            )
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
