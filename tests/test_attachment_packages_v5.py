import json
import os
import tempfile
import unittest
import zipfile

from lifetxt import mutation
from lifetxt.attachment_transactions import (
    AttachmentTransactionError,
    build_directory_package,
    package_directory,
    prepare_open_reference,
    put_attachment_from_path,
    read_bounded_file,
    reconcile_attachment,
    reference_directory,
)


class AttachmentPackageV5Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.life = os.path.join(self.root, "life.txt")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")
        self.config = {
            "attachments": {
                "root": self.root,
                "max_files": 20,
                "max_bytes": 1024 * 1024,
                "max_file_bytes": 1024 * 1024,
            },
            "transactions": {"journal_dir": os.path.join(self.root, "journals")},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_bounded_reader_rejects_large_source(self):
        path = os.path.join(self.root, "large.bin")
        with open(path, "wb") as handle:
            handle.write(b"x" * 20)
        with self.assertRaises(AttachmentTransactionError):
            read_bounded_file(path, max_bytes=10, chunk_size=4)

    def test_put_from_path_enforces_mime_policy(self):
        source = os.path.join(self.root, "source.txt")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("hello")
        config = dict(self.config)
        config["attachments"] = dict(self.config["attachments"], allowed_mime=["image/*"])
        with self.assertRaises(AttachmentTransactionError):
            put_attachment_from_path(
                self.life, "t1", "./copy.txt", source,
                config=config,
                attachment_expected_revision=mutation.MISSING_HASH,
            )

    def test_directory_reference_records_tree_revision(self):
        directory = os.path.join(self.root, "docs")
        os.makedirs(directory)
        with open(os.path.join(directory, "a.txt"), "w", encoding="utf-8") as handle:
            handle.write("a")
        result = reference_directory(self.life, "t1", "./docs", config=self.config)
        self.assertEqual(result["action"], "directory-reference")
        self.assertEqual(len(result["attachment_revision"]), 64)
        with open(self.life, encoding="utf-8") as handle:
            self.assertIn("dir:./docs#sha256=", handle.read())

    def test_directory_package_is_deterministic_and_has_manifest(self):
        directory = os.path.join(self.root, "src")
        os.makedirs(directory)
        with open(os.path.join(directory, "b.txt"), "w", encoding="utf-8") as handle:
            handle.write("b")
        with open(os.path.join(directory, "a.txt"), "w", encoding="utf-8") as handle:
            handle.write("a")
        first, manifest1 = build_directory_package(directory, config=self.config)
        second, manifest2 = build_directory_package(directory, config=self.config)
        self.assertEqual(first, second)
        self.assertEqual(manifest1["package_sha256"], manifest2["package_sha256"])
        package_path = os.path.join(self.root, "package.zip")
        result = package_directory(
            self.life, "t1", directory, "./package.zip",
            config=self.config,
            attachment_expected_revision=mutation.MISSING_HASH,
        )
        self.assertEqual(result["action"], "package")
        self.assertTrue(os.path.exists(package_path))
        with zipfile.ZipFile(package_path) as archive:
            self.assertEqual(archive.namelist(), ["a.txt", "b.txt", "lifetxt-package-manifest.json"])
            manifest = json.loads(archive.read("lifetxt-package-manifest.json"))
            self.assertEqual(manifest["file_count"], 2)

    def test_reconcile_updates_external_file_hash(self):
        target = os.path.join(self.root, "report.txt")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("old")
        initial = put_attachment_from_path(
            self.life, "t1", "./copy.txt", target,
            config=self.config,
            attachment_expected_revision=mutation.MISSING_HASH,
        )
        stored = os.path.join(self.root, "copy.txt")
        with open(stored, "w", encoding="utf-8") as handle:
            handle.write("new")
        result = reconcile_attachment(
            self.life, "t1", "./copy.txt",
            recorded_revision=initial["attachment_revision"][:16],
            config=self.config,
        )
        self.assertEqual(result["action"], "reconcile")
        with open(self.life, encoding="utf-8") as handle:
            self.assertIn(result["attachment_revision"][:16], handle.read())

    def test_open_reference_records_revision_checked_metadata(self):
        target = os.path.join(self.root, "open.txt")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("open")
        result = prepare_open_reference(self.life, "./open.txt", config=self.config)
        self.assertTrue(result["metadata_written"])
        self.assertTrue(result["command"])
        with open(result["metadata_path"], encoding="utf-8") as handle:
            metadata = json.load(handle)
        self.assertEqual(metadata["references"]["./open.txt"]["count"], 1)
        with self.assertRaises(AttachmentTransactionError):
            prepare_open_reference(
                self.life, "./open.txt",
                attachment_expected_revision="stale",
                config=self.config,
                require_revisions=True,
                metadata_revision=result["metadata_revision"],
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_package_rejects_symlink_by_default(self):
        directory = os.path.join(self.root, "symlink-src")
        os.makedirs(directory)
        outside = os.path.join(self.root, "outside.txt")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("outside")
        try:
            os.symlink(outside, os.path.join(directory, "link.txt"))
        except OSError as exc:
            self.skipTest("symlink unavailable: %s" % exc)
        with self.assertRaises(AttachmentTransactionError):
            build_directory_package(directory, config=self.config)


if __name__ == "__main__":
    unittest.main()
