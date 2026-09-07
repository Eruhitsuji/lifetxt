"""SQLite interchange codec (`lifetxt-sqlite-v1`).

Implements the schema and round-trip contract frozen by #690 (see
``docs/en/format-sqlite-interchange-v1.md``). Reuses the existing ``Item``
model and the shared native rendering boundary (:mod:`lifetxt.native_codec`,
#689) rather than a parallel data model -- see #691.

Dependency-free: only the standard-library ``sqlite3`` module is used.
"""

import datetime
import os
import sqlite3
import tempfile
from collections import OrderedDict

from .atomic import atomic_write_bytes
from .model import Item
from .native_codec import canonical_hierarchy_items
from .serializer import item_to_line

#: The only schema version this codec produces or accepts. See #690.
SCHEMA_VERSION = "lifetxt-sqlite-v1"

#: Extensions unambiguously recognized as a lifetxt SQLite interchange file
#: for `lifetxt import`'s extension-inference path (#690 section 7).
SQLITE_IMPORT_EXTENSIONS = (".db", ".sqlite", ".sqlite3")

_SCHEMA_DDL = (
    "CREATE TABLE metadata ("
    "    key TEXT PRIMARY KEY,"
    "    value TEXT NOT NULL"
    ");"
    "CREATE TABLE items ("
    "    item_seq INTEGER PRIMARY KEY,"
    "    status TEXT NOT NULL,"
    "    kind TEXT NOT NULL,"
    "    title TEXT NOT NULL,"
    "    source_line TEXT NOT NULL"
    ");"
    "CREATE TABLE details ("
    "    item_seq INTEGER NOT NULL REFERENCES items(item_seq),"
    "    detail_seq INTEGER NOT NULL,"
    "    key TEXT NOT NULL,"
    "    value TEXT NOT NULL,"
    "    PRIMARY KEY (item_seq, detail_seq)"
    ");"
    "CREATE INDEX idx_details_item_seq ON details(item_seq);"
    "CREATE INDEX idx_items_kind_status ON items(kind, status);"
)


class SQLiteInterchangeError(ValueError):
    """Raised when a database does not satisfy the lifetxt-sqlite-v1 contract.

    Always raised before any destination file is mutated (export) or before
    any item is returned for writing (import) -- see #690 sections 5 and 6.
    """


def export_sqlite(items, output_path, key="id"):
    """Write ``items`` to a SQLite database at ``output_path``.

    Transactional: the database is built at a private temporary path first;
    on any failure the temporary file is removed and ``output_path`` is
    never touched. On success the built bytes are committed to
    ``output_path`` through the shared atomic-replace primitive
    (:func:`lifetxt.atomic.atomic_write_bytes`), matching #690 section 6.
    """
    canonical_items = canonical_hierarchy_items(items, key=key)

    with tempfile.TemporaryDirectory(prefix="lifetxt-sqlite-export-") as temp_dir:
        temp_db_path = os.path.join(temp_dir, "export.db")
        conn = sqlite3.connect(temp_db_path)
        try:
            conn.executescript(_SCHEMA_DDL)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("schema_version", SCHEMA_VERSION),
                    ("generator", "lifetxt"),
                    ("item_count", str(len(canonical_items))),
                    ("exported_at", now),
                ],
            )
            for item_seq, item in enumerate(canonical_items, start=1):
                conn.execute(
                    "INSERT INTO items(item_seq, status, kind, title, source_line) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (item_seq, item.status, item.kind, item.title, item_to_line(item)),
                )
                detail_seq = 1
                for detail_key, values in item.details.items():
                    for value in values:
                        conn.execute(
                            "INSERT INTO details(item_seq, detail_seq, key, value) "
                            "VALUES (?, ?, ?, ?)",
                            (item_seq, detail_seq, detail_key, value),
                        )
                        detail_seq += 1
            conn.commit()
        finally:
            conn.close()

        with open(temp_db_path, "rb") as handle:
            data = handle.read()

    atomic_write_bytes(output_path, data)


def import_sqlite(path):
    """Read a lifetxt-sqlite-v1 database at ``path`` and return ``Item`` objects.

    Raises :class:`SQLiteInterchangeError` for a malformed/foreign database,
    a missing or mismatched ``schema_version``, or a missing/malformed
    ``items``/``details`` table -- always before returning any item, per
    #690 section 5.
    """
    if not os.path.isfile(path):
        raise SQLiteInterchangeError("SQLite database not found: %s" % path)

    try:
        conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    except sqlite3.OperationalError as exc:
        raise SQLiteInterchangeError(
            "Cannot open '%s' as a SQLite database: %s" % (path, exc)
        ) from exc

    try:
        try:
            metadata_rows = conn.execute("SELECT key, value FROM metadata").fetchall()
        except sqlite3.DatabaseError as exc:
            raise SQLiteInterchangeError(
                "'%s' is not a lifetxt SQLite database: missing or unreadable "
                "'metadata' table (%s)" % (path, exc)
            ) from exc

        metadata = dict(metadata_rows)
        version = metadata.get("schema_version")
        if version is None:
            raise SQLiteInterchangeError(
                "'%s' has no schema_version in its metadata table." % path
            )
        if version != SCHEMA_VERSION:
            raise SQLiteInterchangeError(
                "Unsupported lifetxt SQLite schema version %r in '%s' "
                "(expected %r). Unknown, older, or newer schema versions "
                "are refused rather than guessed." % (version, path, SCHEMA_VERSION)
            )

        try:
            item_rows = conn.execute(
                "SELECT item_seq, status, kind, title FROM items ORDER BY item_seq"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise SQLiteInterchangeError(
                "'%s' is missing a valid 'items' table: %s" % (path, exc)
            ) from exc

        try:
            detail_rows = conn.execute(
                "SELECT item_seq, detail_seq, key, value FROM details "
                "ORDER BY item_seq, detail_seq"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise SQLiteInterchangeError(
                "'%s' is missing a valid 'details' table: %s" % (path, exc)
            ) from exc
    finally:
        conn.close()

    details_by_item = {}
    for item_seq, _detail_seq, detail_key, value in detail_rows:
        details_by_item.setdefault(item_seq, OrderedDict()).setdefault(
            detail_key, []
        ).append(value)

    items = []
    for item_seq, status, kind, title in item_rows:
        details = details_by_item.get(item_seq, OrderedDict())
        items.append(Item(status, kind, title, details=details))
    return items
