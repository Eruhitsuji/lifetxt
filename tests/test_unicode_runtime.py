"""Profile3 recipe boundaries; no SDK/downloads are required by these tests."""

import io
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import unicode_runtime as mod


def archive(path, root, files):
    with tarfile.open(path, "w:gz") as target:
        for name, data in files.items():
            member = tarfile.TarInfo(root + "/" + name)
            member.size = len(data)
            target.addfile(member, io.BytesIO(data))


def inputs(directory, setup_body=None):
    entries = []
    makefile = ""
    for repository, commit in [
        ("LIBFFIREPO", "LIBFFI_COMMIT"),
        ("HIWIREREPO", "HIWIRE_COMMIT"),
    ]:
        makefile += f"&& git init \\\n\t\t&& git fetch --depth 1 $({repository}) $({commit}) \\\n\t\t&& git checkout FETCH_HEAD\n"
    pyodide_files = {
        "cpython/Setup.local": b"*static*\n_ctypes test.c\n*disabled*\npwd\n_codecs_hk\n",
        "cpython/Makefile": makefile.encode(),
        "Makefile.envs": b"export PYTHON_ARCHIVE_SHA256=c609e078adab90e2c6bacb6afafacd5eaf60cd94cf670f1e159565725fcd448d\n",
        "pyodide_env.sh": b"export _EMCC_CCACHE=1\n",
        "Makefile": b"dist/python_stdlib.zip: tools/hkscs_free_build.py other\n\tpython3 tools/hkscs_free_build.py stdlib $(CPYTHONLIB) src/py --output $@\n",
    }
    if setup_body is not None:
        pyodide_files["cpython/Setup.local"] = setup_body
    for component in ["pyodide", "cpython", "libffi", "hiwire", "xz", "zstd", "sqlite"]:
        path = directory / (component + "-source.tar.gz")
        root = component + "-fixed"
        archive(
            path,
            root,
            pyodide_files
            if component == "pyodide"
            else {"LICENSE": b"notice", "Lib/encodings/cp437.py": b"# synthetic cp437"},
        )
        entries.append(
            {
                "id": component,
                "file": path.name,
                "root": root,
                "bytes": path.stat().st_size,
                "sha256": mod.sha256(path),
            }
        )
    lock = directory / "inputs.json"
    lock.write_text(
        json.dumps(
            {
                "profile": "synthetic-test-only",
                "archives": entries,
                "internal_cp437_sha256": hashlib.sha256(
                    b"# synthetic cp437"
                ).hexdigest(),
            }
        )
    )
    return lock


def synthetic_curate(source, output):
    # Source curation itself has separate real pin/receipt regression coverage.
    output.write_bytes(b"synthetic-unicode-source")
    return {"output_sha256": mod.sha256(output), "runtime_verified": False}


class RuntimeRecipeTests(unittest.TestCase):
    def test_stage_offline_disables_builtins_pins_sources_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "sources"
            sources.mkdir()
            lock = inputs(sources)
            before = {p.name: p.read_bytes() for p in sources.iterdir()}
            with (
                patch.object(mod, "INPUTS", lock),
                patch.object(mod.unicode_minimal, "curate", synthetic_curate),
            ):
                staged = mod.stage(sources, root / "stage")
            self.assertEqual(
                before, {p.name: p.read_bytes() for p in sources.iterdir()}
            )
            setup = (staged / "cpython/Setup.local").read_text()
            for name in ("_codecs_hk", *mod.DISABLED):
                self.assertEqual(setup.split("*disabled*")[1].split().count(name), 1)
            make = (staged / "cpython/Makefile").read_text()
            self.assertNotIn("git fetch", make)
            self.assertIn("libffi-source.tar.gz --strip-components=1", make)
            self.assertIn("hiwire-source.tar.gz --strip-components=1", make)
            self.assertEqual(
                (staged / "pyodide_env.sh").read_text(), "export _EMCC_CCACHE=\n"
            )
            self.assertEqual(
                (
                    staged / "tools/unicode_stdlib_overlay/encodings/cp437.py"
                ).read_bytes(),
                b"# synthetic cp437",
            )
            self.assertEqual(
                (staged / "tools/unicode_cp437.LICENSE").read_bytes(), b"notice"
            )
            self.assertIn(
                "src/py tools/unicode_stdlib_overlay", (staged / "Makefile").read_text()
            )
            self.assertFalse((root / "stage/INCOMPLETE").exists())
            receipt = json.loads((root / "stage/stage-receipt.json").read_text())
            for flag in [
                "runtime_verified",
                "complete_distribution_audit",
                "public_distribution_approved",
            ]:
                self.assertFalse(receipt[flag])
            for path, digest in receipt["staged_files_sha256"].items():
                self.assertEqual(mod.sha256(staged / path), digest)
            expected = mod.sha256(root / "stage/cpython-unicode-minimal.tar.gz")
            self.assertIn(expected, (staged / "Makefile.envs").read_text())
            with patch.object(mod, "INPUTS", lock), self.assertRaises(FileExistsError):
                mod.stage(sources, root / "stage")

    def test_wrong_input_pin_rejects_before_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock = inputs(root)
            (root / "hiwire-source.tar.gz").write_bytes(b"changed")
            with (
                patch.object(mod, "INPUTS", lock),
                self.assertRaisesRegex(ValueError, "differs from pin"),
            ):
                mod.stage(root, root / "stage")
            self.assertFalse((root / "stage").exists())

    def test_source_mutation_during_snapshot_fails_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock = inputs(root)
            copy = mod.shutil.copyfile

            def changed_copy(source, target):
                result = copy(source, target)
                Path(target).write_bytes(b"changed after preflight")
                return result

            with (
                patch.object(mod, "INPUTS", lock),
                patch.object(mod.shutil, "copyfile", changed_copy),
            ):
                with self.assertRaisesRegex(ValueError, "changed during snapshot"):
                    mod.stage(root, root / "stage")
            self.assertTrue((root / "stage/INCOMPLETE").is_file())
            self.assertFalse((root / "stage/stage-receipt.json").exists())

    def test_cp437_overlay_requires_its_own_pinned_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock = inputs(root)
            data = json.loads(lock.read_text())
            data["internal_cp437_sha256"] = "0" * 64
            lock.write_text(json.dumps(data))
            with (
                patch.object(mod, "INPUTS", lock),
                patch.object(mod.unicode_minimal, "curate", synthetic_curate),
            ):
                with self.assertRaisesRegex(ValueError, "cp437 source differs"):
                    mod.stage(root, root / "stage")
            self.assertTrue((root / "stage/INCOMPLETE").exists())
            self.assertFalse((root / "stage/stage-receipt.json").exists())

    def test_stage_rejects_later_section_without_appending_builtins(self):
        invalid = b"*disabled*\n_codecs_hk\n*static*\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock = inputs(root, setup_body=invalid)
            with (
                patch.object(mod, "INPUTS", lock),
                patch.object(mod.unicode_minimal, "curate", synthetic_curate),
            ):
                with self.assertRaisesRegex(ValueError, "terminal"):
                    mod.stage(root, root / "stage")
            setup = root / "stage/pyodide-fixed/cpython/Setup.local"
            self.assertEqual(setup.read_bytes(), invalid)
            self.assertTrue((root / "stage/INCOMPLETE").exists())
            self.assertFalse((root / "stage/stage-receipt.json").exists())

    def test_disabled_section_must_be_terminal(self):
        for ending in ("*static*", "*shared*", "*noconfig*", "*unknown*"):
            with (
                self.subTest(ending=ending),
                self.assertRaisesRegex(ValueError, "terminal"),
            ):
                mod._disable_builtins("*disabled*\n_codecs_hk\n" + ending + "\n")
        for body in ("*static*\n_codecs_hk\n", "*disabled*\n_codecs_hk\n*disabled*\n"):
            with (
                self.subTest(body=body),
                self.assertRaisesRegex(ValueError, "terminal"),
            ):
                mod._disable_builtins(body)

    def test_disable_guard_ignores_comment_sections_but_not_duplicate_modules(self):
        body = "*static*\n# *shared*\n*disabled*  # final section\n_codecs_hk # existing\n# *static*\n"
        result = mod._disable_builtins(body)
        tail = result.split("*disabled*")[1]
        for name in mod.DISABLED:
            self.assertIn("\n" + name + "\n", tail)
        for body in (
            "*disabled*\n# _codecs_hk\n",
            "*disabled*\n_codecs_hk\n_codecs_hk\n",
            "*disabled*\n_codecs_hk\n_codecs_cn\n",
        ):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "entries"):
                mod._disable_builtins(body)

    def test_recipe_anchors_fail_closed(self):
        for body in ["", "xx", "anchor anchor"]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                mod._once(body, "anchor", "replacement")

    def test_tar_paths_types_duplicates_and_resource_budget(self):
        cases = [
            ("../escape", tarfile.REGTYPE, ""),
            ("/absolute", tarfile.REGTYPE, ""),
            ("fixed/a/../b", tarfile.REGTYPE, ""),
            ("fixed/a\\b", tarfile.REGTYPE, ""),
            ("fixed/alias", tarfile.SYMTYPE, "../../outside"),
            ("fixed/hard", tarfile.LNKTYPE, "fixed/file"),
        ]
        for name, kind, link in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "source.tar.gz"
                with tarfile.open(path, "w:gz") as target:
                    member = tarfile.TarInfo(name)
                    member.type, member.linkname = kind, link
                    target.addfile(member)
                with self.assertRaises(ValueError):
                    mod._members(path, "fixed")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source.tar.gz"
            with tarfile.open(path, "w:gz") as target:
                member = tarfile.TarInfo("fixed/file")
                target.addfile(member)
                target.addfile(member)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                mod._members(path, "fixed")
            with tarfile.open(path, "w:gz") as target:
                member = tarfile.TarInfo("fixed/file")
                member.size = 33 * 1024 * 1024
                target.addfile(member, io.BytesIO(b"\0" * member.size))
            with self.assertRaisesRegex(ValueError, "resource budget"):
                mod._members(path, "fixed")

    def test_only_pinned_zstd_test_links_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source.tar.gz"
            root = "cpython-source-deps-zstd-1.5.7"
            with tarfile.open(path, "w:gz") as target:
                member = tarfile.TarInfo(root + "/tests/cli-tests/bin/unzstd")
                member.type, member.linkname = tarfile.SYMTYPE, "zstd"
                target.addfile(member)
            self.assertEqual(len(mod._members(path, root)), 1)
            with self.assertRaises(ValueError):
                mod._members(path, "other")


if __name__ == "__main__":
    unittest.main()
