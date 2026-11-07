"""Fail-closed technical evidence helpers; full candidate is privately retained."""

import hashlib
import json
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest
import zipfile
from contrib.browser_check_poc import unicode_verify as mod, unicode_minimal


class VerificationTests(unittest.TestCase):
    def test_config_and_objects_reject_each_cjk_module(self):
        config = "_PyImport_Inittab PyInit__codecs"
        listing = ["_codecsmodule.o", "json.o"]
        self.assertEqual(
            mod.config_and_objects(config, listing, listing)["archive_members"], 2
        )
        for module in mod.BLOCKED:
            with self.subTest(module=module):
                with self.assertRaises(ValueError):
                    mod.config_and_objects(
                        config + " PyInit_" + module, listing, listing
                    )
                with self.assertRaises(ValueError):
                    mod.config_and_objects(config, listing + [module + ".o"], listing)
                with self.assertRaises(ValueError):
                    mod.config_and_objects(
                        config, listing, ["Modules/" + module + ".o"]
                    )
        for config, listing, objects in [
            ("", listing, listing),
            (config, [], listing),
            (config, listing, []),
        ]:
            with self.assertRaises(ValueError):
                mod.config_and_objects(config, listing, objects)

    def test_removed_source_directories_allow_only_empty_generated_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.removed_source_directories(root)
            directory = root / "Modules/cjkcodecs"
            directory.mkdir(parents=True)
            mod.removed_source_directories(root)
            (directory / "mappings_cn.h").write_bytes(b"table")
            with self.assertRaises(ValueError):
                mod.removed_source_directories(root)
            (directory / "mappings_cn.h").unlink()
            directory.rmdir()
            directory.write_bytes(b"not a directory")
            with self.assertRaises(ValueError):
                mod.removed_source_directories(root)

    def test_candidate_tamper_missing_and_extra_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "file"
            path.write_bytes(b"fixed")
            pin = {"file": {"bytes": 5, "sha256": hashlib.sha256(b"fixed").hexdigest()}}
            self.assertEqual(mod.runtime_identity(root, pin), pin)
            path.write_bytes(b"other")
            with self.assertRaises(ValueError):
                mod.runtime_identity(root, pin)
            path.unlink()
            with self.assertRaises(ValueError):
                mod.runtime_identity(root, pin)
            path.write_bytes(b"fixed")
            (root / "extra").write_bytes(b"x")
            with self.assertRaises(ValueError):
                mod.runtime_identity(root, pin)

    def test_checkpoint_manifest_and_payload_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            metadata = root / "profiles/unicode-minimal-3"
            metadata.mkdir(parents=True)
            build = root / "build"
            build.mkdir()
            payload = build / "file"
            payload.write_bytes(b"fixed")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": {
                            "build/file": {
                                "bytes": 5,
                                "sha256": hashlib.sha256(b"fixed").hexdigest(),
                            }
                        }
                    }
                )
            )
            (metadata / "retention.json").write_text(
                json.dumps(
                    {
                        "manifest_sha256": hashlib.sha256(
                            manifest.read_bytes()
                        ).hexdigest()
                    }
                )
            )
            with patch.object(mod, "HERE", root):
                self.assertEqual(mod.checkpoint_build_identity(build, manifest), 1)
                payload.write_bytes(b"other")
                with self.assertRaisesRegex(ValueError, "payload differs"):
                    mod.checkpoint_build_identity(build, manifest)
                manifest.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "manifest differs"):
                    mod.checkpoint_build_identity(build, manifest)

    def test_stdlib_encoding_set_hash_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stdlib.zip"
            expected = hashlib.sha256(b"cp437").hexdigest()

            def write(extra=None, missing=None):
                with zipfile.ZipFile(path, "w") as z:
                    for name in unicode_minimal.KEEP_ENCODINGS:
                        filename = "encodings/" + name + ".py"
                        if filename != missing:
                            z.writestr(filename, b"source")
                    z.writestr("encodings/cp437.py", b"cp437")
                    if extra:
                        z.writestr(extra, b"extra")

            write()
            self.assertEqual(mod.stdlib_identity(path, expected)["encoding_files"], 19)
            with self.assertRaises(ValueError):
                mod.stdlib_identity(path, "0" * 64)
            for extra in ("encodings/gb18030.py", "encodings/__init__.py", "bad.pyc"):
                with self.subTest(extra=extra):
                    import warnings

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        write(extra=extra)
                    with self.assertRaises(ValueError):
                        mod.stdlib_identity(path, expected)
            write(missing="encodings/utf_8.py")
            with self.assertRaises(ValueError):
                mod.stdlib_identity(path, expected)


if __name__ == "__main__":
    unittest.main()
