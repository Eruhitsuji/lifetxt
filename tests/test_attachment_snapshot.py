import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from lifetxt import attachment_snapshot as reader
from scripts.build_attachment_snapshot_helper import build_helper, MANIFEST, NAME


class SnapshotSupervisorTests(unittest.TestCase):
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
        self.file = self.root / "file"
        self.file.write_bytes(b"AAAAAAA")
        self.patch = patch.object(
            reader, "_package_directory", return_value=Path(self.package.name)
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def read(self, **kwargs):
        return reader.read_snapshot(self.root, "file", 7, **kwargs)

    def test_single_snapshot_exact_digest(self):
        result = self.read()
        self.assertEqual(b"AAAAAAA", result.data)
        self.assertEqual(hashlib.sha256(result.data).hexdigest(), result.revision)
        with self.assertRaises(reader.SnapshotStale):
            self.read(expected="wrong")

    def test_oversize_before_helper(self):
        with patch.object(reader, "_helper_fd") as helper:
            with self.assertRaises(reader.SnapshotLimit):
                reader.read_snapshot(self.root, "file", 6)
            helper.assert_not_called()

    def test_root_rebind_denied(self):
        exchange = reader._exchange
        moved = self.root.with_name(self.root.name + "-old")

        def replace(*args):
            result = exchange(*args)
            self.root.rename(moved)
            self.root.mkdir(mode=0o700)
            (self.root / "file").write_bytes(b"BBBBBBB")
            return result

        self.addCleanup(shutil.rmtree, moved, True)
        with patch.object(reader, "_exchange", side_effect=replace):
            with self.assertRaises(reader.SnapshotStale):
                self.read()

    def test_same_inode_rewrite_and_leaf_replacement_denied(self):
        exchange = reader._exchange
        for replacement in (False, True):
            self.file.write_bytes(b"AAAAAAA")

            def replace(*args):
                result = exchange(*args)
                if replacement:
                    self.file.unlink()
                self.file.write_bytes(b"BBBBBBB")
                return result

            with (
                self.subTest(replacement=replacement),
                patch.object(reader, "_exchange", side_effect=replace),
            ):
                with self.assertRaises(reader.SnapshotStale):
                    self.read()

    def test_missing_and_tampered_helper_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            with patch.object(reader, "_package_directory", return_value=package):
                with self.assertRaises(reader.SnapshotUnavailable):
                    self.read()

                shutil.copy(Path(self.package.name) / NAME, package / NAME)
                manifest = json.loads((Path(self.package.name) / MANIFEST).read_text())
                manifest["helper_sha256"] = "0" * 64
                (package / MANIFEST).write_text(json.dumps(manifest))
                with self.assertRaises(reader.SnapshotUnavailable):
                    self.read()

    def test_native_source_version_pin_matches_checkout(self):
        source = Path(__file__).resolve().parents[1] / "native/resource_snapshot.c"
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(), reader.SOURCE_SHA256
        )

    def test_untrusted_mode_and_symlink_ancestor(self):
        self.file.chmod(0o666)
        with self.assertRaises(reader.SnapshotStale):
            self.read()
        self.file.chmod(0o600)
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(reader.SnapshotUnavailable):
            reader.read_snapshot(alias, "file", 7)

    def test_malformed_frame_never_returned(self):
        exchange = reader._exchange
        for frame in (
            b"bad\nbytes",
            b"LTXS1 8 0 0 0 0 0 0 0 0\n" + b"x" * 8,
            b"x" * 513,
        ):

            def malformed(*args):
                exchange(*args)
                return frame

            with (
                self.subTest(frame=frame[:20]),
                patch.object(reader, "_exchange", side_effect=malformed),
            ):
                with self.assertRaises(reader.SnapshotUnavailable):
                    self.read()

    def test_fd_cleanup(self):
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(10):
            self.read()
        self.assertEqual(before, len(os.listdir("/proc/self/fd")))

    def test_exchange_failure_kills_reaps_and_closes_handles(self):
        before = len(os.listdir("/proc/self/fd"))
        with patch.object(reader, "_exchange", side_effect=reader.SnapshotUnavailable):
            with self.assertRaises(reader.SnapshotUnavailable):
                self.read()
        self.assertEqual(0, reader._active)
        self.assertEqual(before, len(os.listdir("/proc/self/fd")))

    def test_growing_file_and_trailing_payload_denied(self):
        exchange = reader._exchange

        def grow(*args):
            output = exchange(*args)
            with self.file.open("ab") as handle:
                handle.write(b"B")
            return output

        with patch.object(reader, "_exchange", side_effect=grow):
            with self.assertRaises(reader.SnapshotStale):
                self.read()
        self.file.write_bytes(b"AAAAAAA")
        with patch.object(
            reader, "_exchange", side_effect=lambda *args: exchange(*args) + b"extra"
        ):
            with self.assertRaises(reader.SnapshotUnavailable):
                self.read()


class SnapshotAdmissionTests(unittest.TestCase):
    def test_thread_start_failure_releases_admission(self):
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            self.skipTest("Linux admission policy")
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                reader.read_snapshot("root", "file", 7)
        self.assertEqual(0, reader._active)

    def test_unsupported_platform_no_spawn(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch.object(reader.subprocess, "Popen") as spawn,
        ):
            with self.assertRaises(reader.SnapshotUnavailable):
                reader.read_snapshot("root", "file", 7)
            spawn.assert_not_called()

    def test_stalled_workers_retain_two_slots_after_deadline(self):
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            self.skipTest("Linux admission policy")
        release = threading.Event()
        entered = threading.Event()

        def blocked(*args):
            entered.set()
            release.wait(3)
            return reader.Snapshot(b"x", "unused")

        with patch.object(reader, "_perform", side_effect=blocked):
            try:
                for _ in range(2):
                    with self.assertRaises(reader.SnapshotUnavailable):
                        reader.read_snapshot("root", "file", 7, seconds=0.05)
                self.assertTrue(entered.is_set())
                self.assertEqual(2, reader._active)
                with self.assertRaises(reader.SnapshotUnavailable):
                    reader.read_snapshot("root", "file", 7)
            finally:
                release.set()
                deadline = time.monotonic() + 2
                while reader._active and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(0, reader._active)

    def test_cancelled_principal_keeps_slot(self):
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            self.skipTest("Linux admission policy")
        release = threading.Event()
        entered = threading.Event()
        cancel = threading.Event()
        errors = []

        def blocked(*args):
            entered.set()
            release.wait(3)
            return reader.Snapshot(b"x", "unused")

        def request():
            try:
                reader.read_snapshot("root", "file", 7, cancel=cancel, principal="user")
            except reader.SnapshotUnavailable as exc:
                errors.append(exc)

        with patch.object(reader, "_perform", side_effect=blocked):
            thread = threading.Thread(target=request)
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                cancel.set()
                thread.join(1)
                self.assertFalse(thread.is_alive())
                self.assertEqual(1, reader._active)
                self.assertEqual(1, len(errors))
                with self.assertRaises(reader.SnapshotUnavailable):
                    reader.read_snapshot("root", "file", 7, principal="user")
            finally:
                release.set()
                thread.join(1)
                deadline = time.monotonic() + 2
                while reader._active and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(0, reader._active)

    def test_real_interruptible_worker_killed_and_reaped(self):
        if platform.system() != "Linux":
            self.skipTest("Linux pipe selector")
        # Synthetic stalled pipe process; not evidence of D-state cleanup.
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        try:
            with self.assertRaises(reader.SnapshotUnavailable):
                reader._exchange(
                    process, b"", 7, time.monotonic() + 0.05, threading.Event()
                )
        finally:
            process.kill()
            process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()
