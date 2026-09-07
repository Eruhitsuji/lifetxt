"""Unit tests for lifetxt.sqlite_codec (lifetxt-sqlite-v1, #690/#691)."""

import os
import sqlite3
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.model import Item
from lifetxt.sqlite_codec import (
    SCHEMA_VERSION,
    SQLiteInterchangeError,
    export_sqlite,
    import_sqlite,
)


def _item(status, kind, title, details=None, indent=0):
    return Item(status, kind, title, details=details or OrderedDict(), indent=indent)


class ExportSqliteTests(unittest.TestCase):
    def test_export_writes_expected_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "out.db")
            export_sqlite([_item("[ ] ", "T", "Task")], db_path)
            conn = sqlite3.connect(db_path)
            try:
                metadata = dict(conn.execute("SELECT key, value FROM metadata"))
            finally:
                conn.close()
            self.assertEqual(SCHEMA_VERSION, metadata["schema_version"])
            self.assertEqual("lifetxt", metadata["generator"])
            self.assertEqual("1", metadata["item_count"])
            self.assertIn("T", metadata["exported_at"])  # ISO-8601 has a "T"

    def test_export_preserves_item_order_and_repeated_details(self):
        items = [
            _item(
                "[ ]",
                "T",
                "First",
                details=OrderedDict([("id", ["t1"]), ("tag", ["alpha", "beta"])]),
            ),
            _item("[ ]", "T", "Second", details=OrderedDict([("id", ["t2"])])),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "out.db")
            export_sqlite(items, db_path)
            conn = sqlite3.connect(db_path)
            try:
                rows = conn.execute(
                    "SELECT item_seq, title FROM items ORDER BY item_seq"
                ).fetchall()
                details = conn.execute(
                    "SELECT item_seq, detail_seq, key, value FROM details "
                    "ORDER BY item_seq, detail_seq"
                ).fetchall()
            finally:
                conn.close()
            self.assertEqual([(1, "First"), (2, "Second")], rows)
            self.assertEqual(
                [
                    (1, 1, "id", "t1"),
                    (1, 2, "tag", "alpha"),
                    (1, 3, "tag", "beta"),
                    (2, 1, "id", "t2"),
                ],
                details,
            )

    def test_export_canonicalizes_indentation_into_parent_links(self):
        parent = _item("[ ]", "T", "Parent", details=OrderedDict([("id", ["p1"])]))
        child = _item("[ ]", "T", "Child", indent=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "out.db")
            export_sqlite([parent, child], db_path)
            conn = sqlite3.connect(db_path)
            try:
                child_details = dict(
                    (row[0], row[1])
                    for row in conn.execute(
                        "SELECT key, value FROM details WHERE item_seq = 2"
                    )
                )
            finally:
                conn.close()
            self.assertEqual("p1", child_details.get("parent"))

    def test_export_is_deterministic_in_content_and_order(self):
        items = [
            _item("[ ]", "T", "A", details=OrderedDict([("tag", ["x", "y"])])),
            _item("[ ]", "T", "B"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            db_a = os.path.join(temp_dir, "a.db")
            db_b = os.path.join(temp_dir, "b.db")
            export_sqlite(items, db_a)
            export_sqlite(items, db_b)

            def rows(path):
                conn = sqlite3.connect(path)
                try:
                    return (
                        conn.execute(
                            "SELECT item_seq, status, kind, title FROM items "
                            "ORDER BY item_seq"
                        ).fetchall(),
                        conn.execute(
                            "SELECT item_seq, detail_seq, key, value FROM details "
                            "ORDER BY item_seq, detail_seq"
                        ).fetchall(),
                    )
                finally:
                    conn.close()

            self.assertEqual(rows(db_a), rows(db_b))

    def test_export_multiline_body_round_trips_through_a_single_column(self):
        item = _item(
            "[N]",
            "J",
            "Journal",
            details=OrderedDict([("body", ["line one\nline two"])]),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "out.db")
            export_sqlite([item], db_path)
            conn = sqlite3.connect(db_path)
            try:
                value = conn.execute(
                    "SELECT value FROM details WHERE key = 'body'"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual("line one\nline two", value)

    def test_failed_export_leaves_no_partial_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "nested", "out.db")
            with self.assertRaises(Exception):
                # A non-str value in details breaks the sqlite3 bind step.
                export_sqlite(
                    [
                        _item(
                            "[ ]",
                            "T",
                            "Broken",
                            details=OrderedDict([("bad", [object()])]),
                        )
                    ],
                    db_path,
                )
            self.assertFalse(os.path.exists(db_path))


class ImportSqliteTests(unittest.TestCase):
    def test_round_trip_reconstructs_status_kind_title_and_details(self):
        items = [
            _item(
                "[ ]",
                "T",
                "Task",
                details=OrderedDict(
                    [
                        ("id", ["t1"]),
                        ("tag", ["alpha", "beta"]),
                        ("due", ["2026-06-08"]),
                    ]
                ),
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "out.db")
            export_sqlite(items, db_path)
            restored = import_sqlite(db_path)
            self.assertEqual(1, len(restored))
            restored_item = restored[0]
            self.assertEqual("[ ]", restored_item.status)
            self.assertEqual("T", restored_item.kind)
            self.assertEqual("Task", restored_item.title)
            self.assertEqual(["t1"], restored_item.details["id"])
            self.assertEqual(["alpha", "beta"], restored_item.details["tag"])
            self.assertEqual(["2026-06-08"], restored_item.details["due"])

    def test_import_missing_file_is_refused(self):
        with self.assertRaises(SQLiteInterchangeError):
            import_sqlite(os.path.join(tempfile.gettempdir(), "does-not-exist.db"))

    def test_import_refuses_a_non_sqlite_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "not-a-db.db")
            with open(path, "wb") as handle:
                handle.write(b"this is not a sqlite database")
            with self.assertRaises(SQLiteInterchangeError):
                import_sqlite(path)

    def test_import_refuses_a_foreign_sqlite_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "foreign.db")
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE unrelated (x INTEGER)")
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(SQLiteInterchangeError):
                import_sqlite(path)

    def test_import_refuses_missing_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "no-version.db")
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
                conn.execute(
                    "CREATE TABLE items (item_seq INTEGER PRIMARY KEY, status TEXT, "
                    "kind TEXT, title TEXT, source_line TEXT)"
                )
                conn.execute(
                    "CREATE TABLE details (item_seq INTEGER, detail_seq INTEGER, "
                    "key TEXT, value TEXT)"
                )
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(SQLiteInterchangeError):
                import_sqlite(path)

    def test_import_refuses_a_mismatched_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "future.db")
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
                conn.execute(
                    "INSERT INTO metadata VALUES ('schema_version', 'lifetxt-sqlite-v2')"
                )
                conn.execute(
                    "CREATE TABLE items (item_seq INTEGER PRIMARY KEY, status TEXT, "
                    "kind TEXT, title TEXT, source_line TEXT)"
                )
                conn.execute(
                    "CREATE TABLE details (item_seq INTEGER, detail_seq INTEGER, "
                    "key TEXT, value TEXT)"
                )
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(SQLiteInterchangeError) as ctx:
                import_sqlite(path)
            self.assertIn("lifetxt-sqlite-v2", str(ctx.exception))

    def test_import_refuses_a_database_missing_the_details_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "no-details.db")
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
                conn.execute(
                    "INSERT INTO metadata VALUES ('schema_version', ?)",
                    (SCHEMA_VERSION,),
                )
                conn.execute(
                    "CREATE TABLE items (item_seq INTEGER PRIMARY KEY, status TEXT, "
                    "kind TEXT, title TEXT, source_line TEXT)"
                )
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(SQLiteInterchangeError):
                import_sqlite(path)


if __name__ == "__main__":
    unittest.main()
