import base64
import builtins
import hashlib
import os
from pathlib import Path
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch

from lifetxt import attachment_snapshot as reader
from lifetxt.attachment_transactions import (
    AttachmentTransactionError,
    read_attachment_chunk,
)
from scripts.build_attachment_snapshot_helper import NAME, build_helper


class ChunkSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            platform.system() != "Linux"
            or platform.machine() != "x86_64"
            or not shutil.which("cc")
        ):
            raise unittest.SkipTest("Linux x86_64 build-time compiler unavailable")
        cls.package = tempfile.TemporaryDirectory()
        build_helper(Path(cls.package.name) / NAME)

    @classmethod
    def tearDownClass(cls):
        cls.package.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.life = self.root / "life.txt"
        self.life.write_text("[ ] T Task id:t1\n")
        self.file = self.root / "file"
        self.file.write_bytes(b"AAAAAAA")
        self.config = {
            "attachments": {
                "root": str(self.root),
                "max_file_bytes": 7,
                "remote_chunk_bytes": 4,
            }
        }
        patcher = patch.object(
            reader, "_package_directory", return_value=Path(self.package.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, **kwargs):
        return read_attachment_chunk(self.life, "./file", config=self.config, **kwargs)

    def test_legacy_three_open_aba_never_returns_outside_bytes(self):
        # Before fix, second pathname open sees BBBB; third hash sees AAAAAAA.
        with tempfile.TemporaryDirectory() as outside:
            other = Path(outside) / "other"
            other.write_bytes(b"BBBBBBB")
            original_open = builtins.open
            opens = []

            def swapped_open(path, mode="r", *args, **kwargs):
                if os.fspath(path) == str(self.file) and mode == "rb":
                    opens.append(path)
                    if len(opens) == 2:
                        original = self.root / "saved"
                        self.file.rename(original)
                        self.file.symlink_to(other)
                        try:
                            handle = original_open(path, mode, *args, **kwargs)
                        finally:
                            self.file.unlink()
                            original.rename(self.file)
                        return handle
                return original_open(path, mode, *args, **kwargs)

            with patch("builtins.open", side_effect=swapped_open):
                result = self.read(limit=4)
            self.assertEqual(b"AAAA", base64.b64decode(result["content_base64"]))
            self.assertEqual(
                hashlib.sha256(b"AAAAAAA").hexdigest(), result["attachment_revision"]
            )
            self.assertEqual([], opens, "No Python payload pathname reopen")

    def test_size_cap_before_hash_and_helper(self):
        self.config["attachments"]["max_file_bytes"] = 4
        with (
            patch(
                "lifetxt.attachment_transactions.attachment_revision",
                side_effect=AssertionError("unbounded hash"),
            ),
            patch.object(reader, "_helper_fd") as helper,
        ):
            with self.assertRaisesRegex(AttachmentTransactionError, "file limit"):
                self.read()
            helper.assert_not_called()

    def test_schema_clamps_offsets_expected_and_eof(self):
        result = self.read(offset=-3, limit=-2)
        self.assertEqual(0, result["offset"])
        self.assertEqual(1, result["limit"])
        self.assertEqual(7, result["size"])
        self.assertEqual(str(self.file), result["path"])
        self.assertEqual("./file", result["stored_path"])
        self.assertEqual(10, len(result))
        self.assertEqual(4, self.read(limit=100)["limit"])
        end = self.read(offset=7)
        self.assertEqual(0, end["bytes"])
        self.assertTrue(end["eof"])
        with self.assertRaisesRegex(AttachmentTransactionError, "offset"):
            self.read(offset=8)
        with self.assertRaisesRegex(AttachmentTransactionError, "changed"):
            self.read(attachment_expected_revision="stale")
        self.assertEqual(
            result["attachment_revision"],
            self.read(attachment_expected_revision=result["attachment_revision"])[
                "attachment_revision"
            ],
        )
        self.file.write_bytes(b"")
        self.assertTrue(self.read()["eof"])

    def test_symlink_hardlink_and_escape_denied(self):
        alias = self.root / "alias"
        alias.symlink_to(self.file)
        with self.assertRaises(AttachmentTransactionError):
            read_attachment_chunk(self.life, "alias", config=self.config)
        alias.unlink()
        os.link(self.file, alias)
        with self.assertRaises(AttachmentTransactionError):
            self.read()
        with self.assertRaises(AttachmentTransactionError):
            read_attachment_chunk(self.life, "../outside", config=self.config)

    def test_full_revision_of_exact_snapshot_not_short_hash(self):
        first = self.read(offset=0, limit=4)
        second = self.read(
            offset=4, limit=4, attachment_expected_revision=first["attachment_revision"]
        )
        data = base64.b64decode(first["content_base64"]) + base64.b64decode(
            second["content_base64"]
        )
        self.assertEqual(hashlib.sha256(data).hexdigest(), first["attachment_revision"])
        self.assertEqual(64, len(first["attachment_revision"]))


class ChunkUnavailableTests(unittest.TestCase):
    def test_missing_helper_static_error_no_unbounded_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_bytes(b"x")
            with (
                patch.object(reader, "_package_directory", return_value=root),
                patch(
                    "lifetxt.attachment_transactions.attachment_revision",
                    side_effect=AssertionError("legacy hash"),
                ),
            ):
                with self.assertRaisesRegex(
                    AttachmentTransactionError, "unavailable"
                ) as error:
                    read_attachment_chunk(root / "life.txt", "file")
                self.assertEqual(reader.UNAVAILABLE, str(error.exception))
