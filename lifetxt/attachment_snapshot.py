"""Private optional Linux snapshot supervisor, not a resource authority service."""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import stat
import subprocess
import threading
import time


UNAVAILABLE = (
    "Attachment chunk reading is unavailable on this platform or configuration."
)
MAX_SECONDS = 30.0
# Version pin for the reviewed native source (not a payload identifier).
SOURCE_SHA256 = "d343c3ea2fd8a8a619feb311ca606ded7e8dae1559610958fa1a3100b03c02de"
_lock = threading.Lock()
_active = 0
_principals = set()


class SnapshotUnavailable(ValueError):
    def __init__(self):
        super().__init__(UNAVAILABLE)


class SnapshotLimit(ValueError):
    def __init__(self):
        super().__init__("Attachment exceeds the configured file limit.")


class SnapshotStale(ValueError):
    def __init__(self):
        super().__init__("Attachment changed during chunk read.")


@dataclass(frozen=True)
class Snapshot:
    data: bytes
    revision: str


def _package_directory():
    return Path(__file__).absolute().parent


def _owned(s):
    return s.st_uid in (0, os.geteuid()) and not s.st_mode & 0o022


def _root_fd(path):
    """Fresh no-symlink walk from /; no reused descendant authority handles."""
    path = os.path.abspath(path)
    flags = os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for component in Path(path).parts[1:]:
            nxt = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
            s = os.fstat(fd)
            sticky_root = s.st_uid == 0 and bool(s.st_mode & stat.S_ISVTX)
            if not _owned(s) and not sticky_root:
                raise SnapshotUnavailable()
        if not _owned(os.fstat(fd)):
            raise SnapshotUnavailable()
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file_stat(rootfd, relative):
    components = relative.split("/")
    if any(p in ("", ".", "..") for p in components) or relative.startswith("/"):
        raise SnapshotUnavailable()
    fd = os.dup(rootfd)
    root_dev = os.fstat(fd).st_dev
    try:
        for index, component in enumerate(components):
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            if index != len(components) - 1:
                flags |= os.O_DIRECTORY
            nxt = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
            s = os.fstat(fd)
            if s.st_dev != root_dev or not _owned(s):
                raise SnapshotStale()
            if index != len(components) - 1 and not stat.S_ISDIR(s.st_mode):
                raise SnapshotStale()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
            raise SnapshotStale()
        return s
    finally:
        os.close(fd)


def _fingerprint(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _read_owned(fd, maximum):
    s = os.fstat(fd)
    if (
        not stat.S_ISREG(s.st_mode)
        or not _owned(s)
        or s.st_nlink != 1
        or s.st_size > maximum
    ):
        raise SnapshotUnavailable()
    data = bytearray()
    while len(data) <= maximum:
        block = os.read(fd, min(65536, maximum + 1 - len(data)))
        if not block:
            break
        data.extend(block)
    if len(data) > maximum or _fingerprint(s) != _fingerprint(os.fstat(fd)):
        raise SnapshotUnavailable()
    return bytes(data)


def _helper_fd():
    directory = _root_fd(_package_directory())
    executable = manifest_fd = None
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        manifest_fd = os.open(
            ".attachment-snapshot-helper.json", flags, dir_fd=directory
        )
        manifest = json.loads(_read_owned(manifest_fd, 4096))
        if not isinstance(manifest, dict) or (
            manifest.get("protocol"),
            manifest.get("architecture"),
            manifest.get("libc"),
        ) != ("LTXS1", "x86_64", "glibc"):
            raise SnapshotUnavailable()
        if manifest.get("source_sha256") != SOURCE_SHA256:
            raise SnapshotUnavailable()
        executable = os.open("_attachment_snapshot_helper", flags, dir_fd=directory)
        binary = _read_owned(executable, 4 * 1024 * 1024)
        if (
            not binary.startswith(b"\x7fELF")
            or not os.fstat(executable).st_mode & 0o100
        ):
            raise SnapshotUnavailable()
        if hashlib.sha256(binary).hexdigest() != manifest.get("helper_sha256"):
            raise SnapshotUnavailable()
        os.lseek(executable, 0, os.SEEK_SET)
        result = executable
        executable = None
        return result
    finally:
        for fd in (directory, executable, manifest_fd):
            if fd is not None:
                os.close(fd)


def _exchange(process, request, cap, deadline, cancelled):
    """Bounded nonblocking pipes; never communicate() into unbounded memory."""
    result = bytearray()
    pending = memoryview(request)
    with selectors.DefaultSelector() as selector:
        for pipe in (process.stdin, process.stdout):
            os.set_blocking(pipe.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "input")
        selector.register(process.stdout, selectors.EVENT_READ, "output")
        while selector.get_map():
            if cancelled.is_set() or time.monotonic() >= deadline:
                raise SnapshotUnavailable()
            for key, _ in selector.select(
                min(0.05, max(0, deadline - time.monotonic()))
            ):
                if key.data == "input":
                    written = os.write(key.fd, pending)
                    pending = pending[written:]
                    if not pending:
                        selector.unregister(key.fileobj)
                        process.stdin.close()
                else:
                    block = os.read(key.fd, min(65536, cap + 513 - len(result)))
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        result.extend(block)
                        newline = result.find(b"\n")
                        if (
                            len(result) > cap + 512
                            or (newline < 0 and len(result) > 512)
                            or newline > 512
                        ):
                            raise SnapshotUnavailable()
    return result


def _parse(output, cap, before, root):
    try:
        header, payload = output.split(b"\n", 1)
        fields = header.decode("ascii").split(" ")
        if len(fields) != 10 or fields[0] != "LTXS1" or len(header) > 512:
            raise SnapshotUnavailable()
        size, rd, ri, dev, ino, ms, mn, cs, cn = map(int, fields[1:])
        if size < 0 or size > cap or len(payload) != size or min(rd, ri, dev, ino) < 0:
            raise SnapshotUnavailable()
        if not (0 <= mn < 10**9 and 0 <= cn < 10**9):
            raise SnapshotUnavailable()
        if (rd, ri) != (root.st_dev, root.st_ino) or (
            dev,
            ino,
            size,
            ms * 10**9 + mn,
            cs * 10**9 + cn,
        ) != _fingerprint(before):
            raise SnapshotStale()
        data = bytes(payload)
        return Snapshot(data, hashlib.sha256(data).hexdigest())
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, (SnapshotStale, SnapshotUnavailable)):
            raise
        raise SnapshotUnavailable() from None


def _perform(root_path, relative, cap, expected, deadline, cancelled):
    rootfd = helperfd = None
    process = None
    try:
        rootfd = _root_fd(root_path)
        root = os.fstat(rootfd)
        before = _file_stat(rootfd, relative)
        if before.st_size > cap:
            raise SnapshotLimit()
        helperfd = _helper_fd()
        encoded = os.fsencode(relative)
        if not encoded or len(encoded) > 4095 or b"\0" in encoded:
            raise SnapshotUnavailable()
        request = f"LTXS1 {cap} {len(encoded)}\n".encode("ascii") + encoded
        if cancelled.is_set() or time.monotonic() >= deadline:
            raise SnapshotUnavailable()
        process = subprocess.Popen(
            [f"/proc/self/fd/{helperfd}", str(rootfd)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(rootfd, helperfd),
            close_fds=True,
            env={},
        )
        output = _exchange(process, request, cap, deadline, cancelled)
        process.wait(timeout=max(0, deadline - time.monotonic()))
        if process.returncode == 4:
            raise SnapshotLimit()
        if process.returncode == 5:
            raise SnapshotStale()
        if process.returncode:
            raise SnapshotUnavailable()
        snapshot = _parse(output, cap, before, root)
        current = _root_fd(root_path)
        try:
            now = os.fstat(current)
            if (now.st_dev, now.st_ino) != (root.st_dev, root.st_ino) or (
                _fingerprint(_file_stat(current, relative)) != _fingerprint(before)
            ):
                raise SnapshotStale()
        finally:
            os.close(current)
        if expected not in (None, "") and str(expected) != snapshot.revision:
            raise SnapshotStale()
        return snapshot
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            # Deliberately may block: the supervising thread retains its slot.
            # The caller's deadline does not wait for this physical cleanup.
            process.wait()
            for pipe in (process.stdin, process.stdout):
                if pipe is not None:
                    pipe.close()
        for fd in (helperfd, rootfd):
            if fd is not None:
                os.close(fd)


def read_snapshot(
    root,
    relative,
    cap,
    expected=None,
    *,
    seconds=MAX_SECONDS,
    cancel=None,
    principal=None,
):
    """Return verified bytes, or fail closed. Admission is per process, no queue."""
    global _active
    if (
        platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or platform.libc_ver()[0] != "glibc"
    ):
        raise SnapshotUnavailable()
    if isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap < 2**63:
        raise SnapshotUnavailable()
    if (
        not isinstance(relative, str)
        or not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
    ):
        raise SnapshotUnavailable()
    if not math.isfinite(seconds) or not 0 < seconds <= MAX_SECONDS:
        raise SnapshotUnavailable()
    if principal is not None and (
        not isinstance(principal, str) or not 1 <= len(principal) <= 256
    ):
        raise SnapshotUnavailable()
    if cancel is not None and cancel.is_set():
        raise SnapshotUnavailable()
    deadline = time.monotonic() + seconds
    cancelled = threading.Event()
    done = threading.Event()
    outcome = []
    with _lock:
        if _active >= 2 or (principal is not None and principal in _principals):
            raise SnapshotUnavailable()
        _active += 1
        if principal is not None:
            _principals.add(principal)

    def worker():
        global _active
        try:
            outcome.append(_perform(root, relative, cap, expected, deadline, cancelled))
        except (SnapshotLimit, SnapshotStale) as exc:
            outcome.append(exc)
        except BaseException:
            outcome.append(SnapshotUnavailable())
        finally:
            with _lock:
                _active -= 1
                if principal is not None:
                    _principals.discard(principal)
            done.set()

    thread = threading.Thread(target=worker, name="attachment-snapshot", daemon=True)
    try:
        thread.start()
        while not done.wait(min(0.05, max(0, deadline - time.monotonic()))):
            if time.monotonic() >= deadline or (cancel is not None and cancel.is_set()):
                cancelled.set()
                raise SnapshotUnavailable()
        if time.monotonic() >= deadline or (cancel is not None and cancel.is_set()):
            raise SnapshotUnavailable()
        if isinstance(outcome[0], Exception):
            raise outcome[0]
        return outcome[0]
    except BaseException:
        cancelled.set()
        if thread.ident is None:
            with _lock:
                _active -= 1
                if principal is not None:
                    _principals.discard(principal)
        raise
