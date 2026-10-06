"""Private SQLite identity index; current files/config remain the authority."""

from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading

from .attachment_snapshot import _root_fd


class BindingUnavailable(ValueError):
    def __init__(self):
        super().__init__("Resource unavailable.")


class BindingBusy(BindingUnavailable):
    pass


HEX = re.compile(r"[0-9a-f]{64}\Z")
REF = re.compile(r"att:v1:[0-9a-f]{32}\Z")
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE bindings (
 ref TEXT PRIMARY KEY, epoch TEXT NOT NULL, workspace TEXT NOT NULL,
 source TEXT NOT NULL, item TEXT NOT NULL, association TEXT NOT NULL,
 generation TEXT NOT NULL UNIQUE, source_hash TEXT NOT NULL,
 source_identity TEXT NOT NULL, resource_identity TEXT NOT NULL,
 policy TEXT NOT NULL, live INTEGER NOT NULL CHECK(live IN (0,1)));
CREATE TABLE tokens (
 token TEXT PRIMARY KEY, ref TEXT NOT NULL, namespace TEXT NOT NULL,
 validator TEXT NOT NULL, policy TEXT NOT NULL, live INTEGER NOT NULL CHECK(live IN (0,1)));
CREATE INDEX selection ON bindings(workspace,source,item,live);
"""


def _check_file(path, optional=False):
    try:
        s = os.lstat(path)
    except FileNotFoundError:
        if optional:
            return None
        raise BindingUnavailable() from None
    if (
        not stat.S_ISREG(s.st_mode)
        or s.st_nlink != 1
        or s.st_uid != os.geteuid()
        or stat.S_IMODE(s.st_mode) != 0o600
    ):
        raise BindingUnavailable()
    return (s.st_dev, s.st_ino)


class BindingStore:
    """Single worker/owner, no rollback-stable public references or implicit repair."""

    @classmethod
    def provision(cls, path):
        """Explicit operator-only creation; never overwrite existing state."""
        path = Path(path).absolute()
        fd = _root_fd(path.parent)
        try:
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700:
                raise BindingUnavailable()
            if any(
                os.path.lexists(str(path) + suffix)
                for suffix in (".owner", "-wal", "-shm", "-journal")
            ):
                raise BindingUnavailable()
            new = os.open(
                path.name,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            os.close(new)
            connection = sqlite3.connect(path)
            try:
                connection.executescript(SCHEMA)
                connection.executemany(
                    "INSERT INTO meta VALUES (?,?)",
                    [
                        ("version", "1"),
                        ("install", secrets.token_hex(16)),
                        ("epoch", secrets.token_hex(16)),
                        ("sequence", "0"),
                    ],
                )
                connection.commit()
            finally:
                connection.close()
            durable = os.open(
                ".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            try:
                os.fsync(durable)
            finally:
                os.close(durable)
        finally:
            os.close(fd)

    def __init__(self, path, *, max_active=10000, max_total=50000):
        if fcntl is None:
            raise BindingUnavailable()
        self.path = Path(path).absolute()
        self.lock = threading.Lock()
        self.connection = self.owner_fd = self.root = None
        if any(
            isinstance(n, bool) or not isinstance(n, int)
            for n in (max_active, max_total)
        ):
            raise BindingUnavailable()
        if not 1 <= max_active <= 10000 or not max_active <= max_total <= 50000:
            raise BindingUnavailable()
        self.max_active, self.max_total = max_active, max_total
        try:
            self.root = _root_fd(self.path.parent)
            s = os.fstat(self.root)
            if stat.S_IMODE(s.st_mode) != 0o700:
                raise BindingUnavailable()
            self.root_identity = (s.st_dev, s.st_ino)
            self.db_identity = _check_file(self.path)
            self.owner_fd = os.open(
                self.path.name + ".owner",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self.root,
            )
            self.owner_identity = _check_file(str(self.path) + ".owner")
            fcntl.flock(self.owner_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._files()
            self.connection = sqlite3.connect(
                self.path, timeout=0.1, check_same_thread=False
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA trusted_schema=OFF")
            self.connection.execute("PRAGMA synchronous=FULL")
            # DELETE journal is sufficient for the single writer. Reject foreign
            # WAL/SHM; never adopt an unverified recovery configuration.
            if self.connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise BindingUnavailable()
            if self.connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise BindingUnavailable()
            if (
                self.connection.execute(
                    "SELECT value FROM meta WHERE key='version'"
                ).fetchone()[0]
                != "1"
            ):
                raise BindingUnavailable()
            sequence = self.connection.execute(
                "SELECT value FROM meta WHERE key='sequence'"
            ).fetchone()
            if sequence is None or not sequence[0].isdigit():
                raise BindingUnavailable()
            self.sequence = int(sequence[0])
            if not 0 <= self.sequence < 2**63 - 1:
                raise BindingUnavailable()
            self.epoch = secrets.token_hex(16)
            self.install = self.connection.execute(
                "SELECT value FROM meta WHERE key='install'"
            ).fetchone()[0]
            if not isinstance(self.install, str) or not re.fullmatch(
                r"[0-9a-f]{32}", self.install
            ):
                raise BindingUnavailable()
            with self._transaction(check_epoch=False):
                self.connection.execute("UPDATE bindings SET live=0")
                self.connection.execute("UPDATE tokens SET live=0")
                self.connection.execute(
                    "UPDATE meta SET value=? WHERE key='epoch'", (self.epoch,)
                )
                self._quota(0)
        except BaseException as exc:
            self.close()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise BindingUnavailable() from None

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        for name in ("owner_fd", "root"):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)

    def _files(self):
        if _check_file(self.path) != self.db_identity:
            raise BindingUnavailable()
        if _check_file(str(self.path) + ".owner") != self.owner_identity:
            raise BindingUnavailable()
        # Never recover an externally restored WAL/SHM or hot journal.
        for suffix in ("-wal", "-shm", "-journal"):
            if os.path.lexists(str(self.path) + suffix):
                raise BindingUnavailable()
        current = _root_fd(self.path.parent)
        try:
            s = os.fstat(current)
            if (s.st_dev, s.st_ino) != self.root_identity or stat.S_IMODE(
                s.st_mode
            ) != 0o700:
                raise BindingUnavailable()
        finally:
            os.close(current)

    @contextmanager
    def _transaction(self, check_epoch=True):
        if not self.lock.acquire(timeout=0.1):
            raise BindingBusy()
        try:
            self._files()
            if self.connection is None:
                raise BindingUnavailable()
            self.connection.execute("BEGIN IMMEDIATE")
            if check_epoch:
                value = self.connection.execute(
                    "SELECT value FROM meta WHERE key='epoch'"
                ).fetchone()
                if value is None or value[0] != self.epoch:
                    raise BindingUnavailable()
            persisted = self.connection.execute(
                "SELECT value FROM meta WHERE key='sequence'"
            ).fetchone()
            if (
                persisted is None
                or persisted[0] != str(self.sequence)
                or self.sequence >= 2**63 - 1
            ):
                raise BindingUnavailable()
            next_sequence = self.sequence + 1
            yield
            self.connection.execute(
                "UPDATE meta SET value=? WHERE key='sequence'", (str(next_sequence),)
            )
            self.connection.commit()
            self.sequence = next_sequence
        except BaseException as exc:
            if self.connection is not None:
                self.connection.rollback()
            if isinstance(exc, (KeyboardInterrupt, SystemExit, BindingUnavailable)):
                raise
            raise BindingUnavailable() from None
        finally:
            self.lock.release()

    def _quota(self, additional, active=0):
        rows = self.connection.execute(
            "SELECT (SELECT count(*) FROM bindings)+(SELECT count(*) FROM tokens)"
        ).fetchone()[0]
        lives = self.connection.execute(
            "SELECT count(*) FROM bindings WHERE live=1"
        ).fetchone()[0]
        if rows + additional > self.max_total or lives + active > self.max_active:
            raise BindingUnavailable()

    def _random(self, prefix, table, column):
        for _ in range(8):
            value = prefix + secrets.token_hex(16)
            if not self.connection.execute(
                f"SELECT 1 FROM {table} WHERE {column}=?", (value,)
            ).fetchone():
                return value
        raise BindingUnavailable()

    def enroll(
        self,
        workspace,
        source,
        item,
        association,
        source_hash,
        source_identity,
        resource_identity,
        policy,
    ):
        """Only verified owner enrollment invokes this, never HTTP discovery."""
        if not all(
            isinstance(v, str) and HEX.fullmatch(v)
            for v in (workspace, source, source_hash, policy)
        ):
            raise BindingUnavailable()
        if not isinstance(item, str) or not 1 <= len(item) <= 128:
            raise BindingUnavailable()
        if (
            not isinstance(association, str)
            or not 1 <= len(association.encode()) <= 4095
        ):
            raise BindingUnavailable()
        with self._transaction():
            self._quota(1, 1)
            if self.connection.execute(
                "SELECT 1 FROM bindings WHERE workspace=? AND source=? AND item=? AND association=? AND live=1",
                (workspace, source, item, association),
            ).fetchone():
                raise BindingUnavailable()
            reference = self._random("att:v1:", "bindings", "ref")
            generation = self._random("", "bindings", "generation")
            self.connection.execute(
                "INSERT INTO bindings VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    reference,
                    self.epoch,
                    workspace,
                    source,
                    item,
                    association,
                    generation,
                    source_hash,
                    json.dumps(source_identity),
                    json.dumps(resource_identity),
                    policy,
                ),
            )
            return reference

    def get(self, workspace, reference):
        if not isinstance(reference, str) or not REF.fullmatch(reference):
            raise BindingUnavailable()
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM bindings WHERE ref=? AND workspace=? AND epoch=? AND live=1",
                (reference, workspace, self.epoch),
            ).fetchone()
            if row is None:
                raise BindingUnavailable()
            return dict(row)

    def verify_source(self, workspace, source, source_hash, identity):
        """Observed out-of-band edits retire every affected association atomically."""
        with self._transaction():
            refs = self.connection.execute(
                "SELECT ref FROM bindings WHERE workspace=? AND source=? AND epoch=? AND live=1 AND (source_hash!=? OR source_identity!=?)",
                (workspace, source, self.epoch, source_hash, json.dumps(identity)),
            ).fetchall()
            for row in refs:
                self.connection.execute(
                    "UPDATE bindings SET live=0 WHERE ref=?", (row[0],)
                )
                self.connection.execute(
                    "UPDATE tokens SET live=0 WHERE ref=?", (row[0],)
                )

    def item_bindings(self, workspace, source, item):
        with self._transaction():
            rows = self.connection.execute(
                "SELECT * FROM bindings WHERE workspace=? AND source=? AND item=? AND epoch=? AND live=1 LIMIT 10001",
                (workspace, source, item, self.epoch),
            ).fetchall()
            return [dict(row) for row in rows]

    def detach(self, reference):
        with self._transaction():
            self.connection.execute(
                "UPDATE bindings SET live=0 WHERE ref=?", (reference,)
            )
            self.connection.execute(
                "UPDATE tokens SET live=0 WHERE ref=?", (reference,)
            )

    def revisions(self, row, source_hash, resource_hash, policy):
        if not all(
            isinstance(x, str) and HEX.fullmatch(x)
            for x in (source_hash, resource_hash, policy)
        ):
            raise BindingUnavailable()
        with self._transaction():
            current = self.connection.execute(
                "SELECT * FROM bindings WHERE ref=? AND epoch=? AND live=1",
                (row["ref"], self.epoch),
            ).fetchone()
            if (
                current is None
                or current["generation"] != row["generation"]
                or current["source_hash"] != source_hash
            ):
                raise BindingUnavailable()
            result = []
            for namespace, validator in (
                ("source", source_hash),
                ("resource", resource_hash),
            ):
                existing = self.connection.execute(
                    "SELECT token FROM tokens WHERE ref=? AND namespace=? AND validator=? AND policy=? AND live=1",
                    (row["ref"], namespace, validator, policy),
                ).fetchone()
                if existing:
                    result.append(existing[0])
                    continue
                self._quota(1)
                self.connection.execute(
                    "UPDATE tokens SET live=0 WHERE ref=? AND namespace=?",
                    (row["ref"], namespace),
                )
                token = self._random("rev:v1:", "tokens", "token")
                self.connection.execute(
                    "INSERT INTO tokens VALUES (?,?,?,?,?,1)",
                    (token, row["ref"], namespace, validator, policy),
                )
                result.append(token)
            return tuple(result)
