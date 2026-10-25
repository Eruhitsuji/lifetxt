"""Reject self-consistent forged build receipts using real locked staging."""

import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from contrib.browser_check_poc import hkscs_free as staging
from contrib.browser_check_poc import hkscs_free_verify as verifier
from tests import test_hkscs_free as curation_tests


class VerificationInputTests(unittest.TestCase):
    def fixture(self, root):
        archive, _ = curation_tests.HkscsFreeTests().fixture(root)
        archive.rename(root / "cpython-source.tar.gz")
        lock = json.loads((root / "source-lock.json").read_text())
        files = {
            "Makefile": (
                b"src/core/pyodide_pre.gen.dat: input\n\trm -f $@\n"
                b"\techo old embedding\n\n# Don't use ccache here\n"
                b"dist/python_stdlib.zip: input\n\t./tools/create_zipfile.py lib\n"
            ),
            "cpython/Makefile": (
                b"\twget -q -O $@ $(PYTHON_ARCHIVE_URL)\n"
                b"wget -q -O - $(LZMATARBALL)\n"
                b"wget -q -O - $(ZSTDTARBALL)\n"
                b"wget -q -O - $(SQLITE3TARBALL)\n"
            ),
            "cpython/Setup.local": b"*disabled*\n",
            "tools/create_zipfile.py": b"# Synthetic selector placeholder\n",
            "tools/nested/helper.py": b"# Synthetic helper\n",
            "cpython/patches/001-test.patch": b"Synthetic CPython patch\n",
            "emsdk/patches/001-test.patch": b"Synthetic SDK patch\n",
            "Makefile.envs": b"SYNTHETIC_VARIABLE=1\n",
        }
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for name, body in files.items():
                member = tarfile.TarInfo("pyodide-test/" + name)
                member.size = len(body)
                tar.addfile(member, io.BytesIO(body))
        data = raw.getvalue()
        (root / "pyodide-source.tar.gz").write_bytes(data)
        lock["archives"].append(
            {
                "id": "pyodide",
                "file": "pyodide-source.tar.gz",
                "root": "pyodide-test",
                "bytes": len(data),
                "sha256": staging.digest(data),
                "required_members": {k: staging.digest(v) for k, v in files.items()},
            }
        )
        for component in ("xz", "zstd", "sqlite"):
            body = ("Synthetic " + component).encode()
            name = component + "-source.tar.gz"
            (root / name).write_bytes(body)
            lock["archives"].append(
                {
                    "id": component,
                    "file": name,
                    "bytes": len(body),
                    "sha256": staging.digest(body),
                }
            )
        (root / "source-lock.json").write_text(json.dumps(lock))
        (root / "hkscs_free_build.py").write_bytes(
            (staging.HERE / "hkscs_free_build.py").read_bytes()
        )

    def test_reconstructed_staging_accepts_original_and_rejects_forged_receipts(self):
        for mutation in (None, "receipt", "archive", "compiler", "missing-cache"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root)
                with patch.object(staging, "HERE", root):
                    output = root / "build"
                    build = staging.prepare_build(root, output)
                    curated = output / "curated"
                    if mutation == "receipt":
                        path = curated / "source-removal.json"
                        receipt = json.loads(path.read_text())
                        receipt["upstream_sha256"] = "0" * 64
                        path.write_text(json.dumps(receipt))
                    elif mutation == "archive":
                        path = curated / "cpython-hkscs-free.tar.gz"
                        path.write_bytes(path.read_bytes() + b"forged")
                        for receipt in (
                            curated / "source-removal.json",
                            output / "build-profile.json",
                        ):
                            data = json.loads(receipt.read_text())
                            data["curated_sha256"] = staging.digest(path.read_bytes())
                            receipt.write_text(json.dumps(data))
                    elif mutation == "compiler":
                        path = build / "cpython/Setup.local"
                        path.write_bytes(path.read_bytes() + b"unreviewed_module\n")
                        receipt = output / "build-profile.json"
                        data = json.loads(receipt.read_text())
                        data["setup_local_sha256"] = staging.digest(path.read_bytes())
                        receipt.write_text(json.dumps(data))
                    elif mutation == "missing-cache":
                        (root / "cpython-source.tar.gz").unlink()
                    if mutation is None:
                        verifier.verify_staging(build, curated, root)
                    else:
                        with self.assertRaises((ValueError, FileNotFoundError)):
                            # Must fail before inspecting or running any runtime/tool.
                            verifier.verify(
                                build,
                                curated,
                                root / "no-runtime",
                                root / "no-llvm",
                                root,
                            )

    def test_build_profile_only_change_is_rejected_before_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with patch.object(staging, "HERE", root):
                output = root / "build"
                build = staging.prepare_build(root, output)
                path = output / "build-profile.json"
                data = json.loads(path.read_text())
                data["setup_local_sha256"] = "0" * 64
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "staging receipt"):
                    verifier.verify(
                        build,
                        output / "curated",
                        root / "no-runtime",
                        root / "no-llvm",
                        root,
                    )

    def test_build_support_changes_missing_extra_and_symlinks_are_rejected(self):
        targets = (
            "tools/create_zipfile.py",
            "tools/nested/helper.py",
            "cpython/patches/001-test.patch",
            "emsdk/patches/001-test.patch",
            "Makefile.envs",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with patch.object(staging, "HERE", root):
                output = root / "build"
                build = staging.prepare_build(root, output)
                expected = verifier.build_input_manifest(build)
                for relative in targets:
                    with self.subTest(relative=relative):
                        path = build / relative
                        original = path.read_bytes()
                        path.write_bytes(original + b"modified")
                        self.assertNotEqual(
                            verifier.build_input_manifest(build), expected
                        )
                        with self.assertRaisesRegex(ValueError, "build inputs differ"):
                            verifier.verify_staging(build, output / "curated", root)
                        path.unlink()
                        self.assertNotEqual(
                            verifier.build_input_manifest(build), expected
                        )
                        with self.assertRaisesRegex(ValueError, "build inputs differ"):
                            verifier.verify_staging(build, output / "curated", root)
                        path.write_bytes(original)
                extra = build / "tools/unreviewed.py"
                extra.write_bytes(b"unexpected")
                with self.assertRaisesRegex(ValueError, "build inputs differ"):
                    verifier.verify_staging(build, output / "curated", root)
                extra.unlink()
                target = build / "tools/create_zipfile.py"
                original = target.read_bytes()
                target.unlink()
                target.symlink_to(build / "tools/nested/helper.py")
                with self.assertRaisesRegex(ValueError, "symlink"):
                    verifier.build_input_manifest(build)
                target.unlink()
                target.write_bytes(original)
                cache = build / "tools/__pycache__"
                cache.mkdir()
                (cache / "create_zipfile.cpython-312.pyc").write_bytes(b"generated")
                self.assertEqual(verifier.build_input_manifest(build), expected)
                verifier.verify_staging(build, output / "curated", root)

    def test_archive_byte_mismatch_reports_host_without_relaxing_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with patch.object(staging, "HERE", root):
                output = root / "build"
                build = staging.prepare_build(root, output)
                archive = output / "curated/cpython-hkscs-free.tar.gz"
                archive.write_bytes(
                    archive.read_bytes() + b"different-compression-bytes"
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "bytes rejected.*Python.*zlib.*Do not replace locked hashes",
                ):
                    verifier.verify_staging(build, output / "curated", root)
