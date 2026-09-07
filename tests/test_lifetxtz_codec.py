"""Unit tests for lifetxt.lifetxtz_codec (lifetxtz-v1, #692/#693)."""

import json
import os
import tempfile
import unittest
import zipfile
from collections import OrderedDict

from lifetxt.lifetxtz_codec import (
    CONTAINER_VERSION,
    MANIFEST_NAME,
    PAYLOAD_NAME,
    LifetxtzError,
    export_lifetxtz,
    import_lifetxtz,
)
from lifetxt.model import Item


def _item(status, kind, title, details=None, indent=0):
    return Item(status, kind, title, details=details or OrderedDict(), indent=indent)


class ExportLifetxtzTests(unittest.TestCase):
    def test_export_writes_exactly_the_two_required_members(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "out.lifetxtz")
            export_lifetxtz([_item("[ ]", "T", "Task")], archive_path)
            with zipfile.ZipFile(archive_path) as zf:
                self.assertEqual({MANIFEST_NAME, PAYLOAD_NAME}, set(zf.namelist()))

    def test_manifest_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "out.lifetxtz")
            export_lifetxtz(
                [_item("[ ]", "T", "Task", details=OrderedDict([("id", ["t1"])]))],
                archive_path,
                created_at="2026-01-01T00:00:00+00:00",
            )
            with zipfile.ZipFile(archive_path) as zf:
                manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
                payload = zf.read(PAYLOAD_NAME).decode("utf-8")
            self.assertEqual(CONTAINER_VERSION, manifest["container"])
            self.assertEqual("lifetxt", manifest["generator"])
            self.assertEqual("2026-01-01T00:00:00+00:00", manifest["created_at"])
            self.assertEqual(PAYLOAD_NAME, manifest["payload_name"])
            self.assertEqual(1, manifest["item_count"])
            self.assertEqual(len(payload.encode("utf-8")), manifest["payload_bytes"])
            import hashlib

            self.assertEqual(
                hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                manifest["payload_sha256"],
            )

    def test_export_is_byte_identical_given_the_same_created_at(self):
        items = [
            _item("[ ]", "T", "A", details=OrderedDict([("tag", ["x", "y"])])),
            _item("[ ]", "T", "B"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path_a = os.path.join(temp_dir, "a.lifetxtz")
            path_b = os.path.join(temp_dir, "b.lifetxtz")
            export_lifetxtz(items, path_a, created_at="2026-01-01T00:00:00+00:00")
            export_lifetxtz(items, path_b, created_at="2026-01-01T00:00:00+00:00")
            with open(path_a, "rb") as a, open(path_b, "rb") as b:
                self.assertEqual(a.read(), b.read())

    def test_export_canonicalizes_indentation_into_parent_links(self):
        parent = _item("[ ]", "T", "Parent", details=OrderedDict([("id", ["p1"])]))
        child = _item("[ ]", "T", "Child", indent=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "out.lifetxtz")
            export_lifetxtz([parent, child], archive_path)
            with zipfile.ZipFile(archive_path) as zf:
                payload = zf.read(PAYLOAD_NAME).decode("utf-8")
            self.assertIn("parent:p1", payload)

    def test_failed_export_leaves_no_partial_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "nested", "out.lifetxtz")
            with self.assertRaises(Exception):
                export_lifetxtz(["not an item"], archive_path)
            self.assertFalse(os.path.exists(archive_path))


class ImportLifetxtzTests(unittest.TestCase):
    def test_round_trip_recovers_the_exact_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "out.lifetxtz")
            export_lifetxtz(
                [
                    _item(
                        "[ ]",
                        "T",
                        "Task",
                        details=OrderedDict([("id", ["t1"]), ("tag", ["a", "b"])]),
                    )
                ],
                archive_path,
            )
            payload = import_lifetxtz(archive_path)
            self.assertIn("Task", payload)
            self.assertIn("id:t1", payload)
            self.assertIn("tag:a", payload)
            self.assertIn("tag:b", payload)

    def test_import_refuses_a_non_zip_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "not-a-zip.lifetxtz")
            with open(path, "wb") as handle:
                handle.write(b"this is not a zip archive")
            with self.assertRaises(LifetxtzError):
                import_lifetxtz(path)

    def test_import_refuses_a_foreign_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "foreign.lifetxtz")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("something-else.txt", "hello")
            with self.assertRaises(LifetxtzError):
                import_lifetxtz(path)

    def test_import_refuses_an_extra_member(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "extra-member.lifetxtz")
            export_lifetxtz([_item("[ ]", "T", "Task")], path)
            # Rebuild with an extra member injected.
            with zipfile.ZipFile(path) as zf:
                manifest = zf.read(MANIFEST_NAME)
                payload = zf.read(PAYLOAD_NAME)
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(MANIFEST_NAME, manifest)
                zf.writestr(PAYLOAD_NAME, payload)
                zf.writestr("extra.txt", "unexpected")
            with self.assertRaises(LifetxtzError):
                import_lifetxtz(path)

    def test_import_refuses_a_path_traversal_member_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "traversal.lifetxtz")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(MANIFEST_NAME, "{}")
                zf.writestr("../../evil.txt", "payload")
            with self.assertRaises(LifetxtzError):
                import_lifetxtz(path)

    def test_import_refuses_a_mismatched_container_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "future.lifetxtz")
            payload = "[ ] T Task\n".encode("utf-8")
            import hashlib

            manifest = json.dumps(
                {
                    "container": "lifetxtz-v2",
                    "generator": "lifetxt",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "payload_name": PAYLOAD_NAME,
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                    "payload_bytes": len(payload),
                    "item_count": 1,
                }
            ).encode("utf-8")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(MANIFEST_NAME, manifest)
                zf.writestr(PAYLOAD_NAME, payload)
            with self.assertRaises(LifetxtzError) as ctx:
                import_lifetxtz(path)
            self.assertIn("lifetxtz-v2", str(ctx.exception))

    def test_import_refuses_a_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "tampered.lifetxtz")
            export_lifetxtz([_item("[ ]", "T", "Task")], path)
            with zipfile.ZipFile(path) as zf:
                manifest = zf.read(MANIFEST_NAME)
            tampered_payload = b"[ ] T Tampered\n"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(MANIFEST_NAME, manifest)
                zf.writestr(PAYLOAD_NAME, tampered_payload)
            with self.assertRaises(LifetxtzError) as ctx:
                import_lifetxtz(path)
            self.assertIn("checksum", str(ctx.exception).lower())

    def test_import_refuses_an_oversized_declared_payload_without_decompressing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "huge.lifetxtz")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(MANIFEST_NAME, "{}")
                info = zipfile.ZipInfo(PAYLOAD_NAME)
                zf.writestr(info, "x")
                # Force a declared size over the ceiling without writing
                # gigabytes of real data.
                zf.NameToInfo[PAYLOAD_NAME].file_size = 10**12
            with self.assertRaises(LifetxtzError) as ctx:
                import_lifetxtz(path)
            self.assertIn("byte limit", str(ctx.exception))

    def test_import_refuses_a_missing_manifest_field(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "no-checksum.lifetxtz")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(
                    MANIFEST_NAME,
                    json.dumps(
                        {"container": CONTAINER_VERSION, "payload_name": PAYLOAD_NAME}
                    ),
                )
                zf.writestr(PAYLOAD_NAME, "[ ] T Task\n")
            with self.assertRaises(LifetxtzError):
                import_lifetxtz(path)


if __name__ == "__main__":
    unittest.main()
