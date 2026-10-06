"""Synthetic build-time tests; no runtime compiler requirement."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest


class NativeSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != "Linux" or not shutil.which("cc"):
            raise unittest.SkipTest("Linux build-time compiler unavailable")
        cls.build = tempfile.TemporaryDirectory()
        cls.helper = Path(cls.build.name) / "snapshot"
        source = Path(__file__).resolve().parents[1] / "native/resource_snapshot.c"
        subprocess.run(
            [
                "cc",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(source),
                "-o",
                str(cls.helper),
            ],
            check=True,
            capture_output=True,
        )
        cls.growth_helper = Path(cls.build.name) / "growth"
        fixture = Path(__file__).resolve().parent / "native_snapshot_growth.c"
        subprocess.run(
            [
                "cc",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(fixture),
                "-o",
                str(cls.growth_helper),
            ],
            check=True,
            capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "file").write_bytes(b"AAAAAAA")

    def call(self, path="file", cap=7, root=None, request=None):
        encoded = os.fsencode(path)
        fd = os.open(root or self.root, os.O_PATH | os.O_DIRECTORY)
        try:
            return subprocess.run(
                [str(self.helper), str(fd)],
                pass_fds=(fd,),
                input=request
                if request is not None
                else f"LTXS1 {cap} {len(encoded)}\n".encode() + encoded,
                capture_output=True,
                timeout=3,
            )
        finally:
            os.close(fd)

    def test_regular_exact_bytes_and_empty(self):
        result = self.call()
        self.assertEqual(0, result.returncode, result.stderr)
        header, data = result.stdout.split(b"\n", 1)
        self.assertTrue(header.startswith(b"LTXS1 7 "))
        self.assertEqual(b"AAAAAAA", data)
        (self.root / "file").write_bytes(b"")
        self.assertEqual(b"", self.call(cap=0).stdout.split(b"\n", 1)[1])

    def test_oversize_has_no_output(self):
        result = self.call(cap=6)
        self.assertEqual(4, result.returncode)
        self.assertEqual(b"", result.stdout)

    def test_growth_after_inspection_hits_cap_plus_one(self):
        helper = self.helper
        try:
            self.helper = self.growth_helper
            result = self.call(cap=7)
        finally:
            self.helper = helper
        self.assertEqual(4, result.returncode)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"AAAAAAAB", (self.root / "file").read_bytes())

    def test_leaf_and_ancestor_symlinks(self):
        (self.root / "link").symlink_to("file")
        (self.root / "directory").mkdir()
        (self.root / "directory" / "file").write_bytes(b"x")
        (self.root / "alias").symlink_to("directory", target_is_directory=True)
        for path in ("link", "alias/file"):
            with self.subTest(path=path):
                self.assertEqual(3, self.call(path).returncode)

    def test_escape_and_bad_protocol(self):
        for path in ("../file", "/etc/passwd", "directory/../file"):
            self.assertEqual(3, self.call(path).returncode)
        for request in (b"BAD\n", b"LTXS1 7 5\nfi\x00le", b"LTXS1 7 5000\n"):
            self.assertEqual(3, self.call(request=request).returncode)

    def test_nonregular_and_hardlinks(self):
        (self.root / "dir").mkdir()
        os.mkfifo(self.root / "pipe")
        for path in ("dir", "pipe"):
            self.assertEqual(3, self.call(path).returncode)
        os.link(self.root / "file", self.root / "alias")
        self.assertEqual(3, self.call().returncode)

    def test_world_writable_and_pseudo_root_denied(self):
        (self.root / "file").chmod(0o666)
        self.assertEqual(3, self.call().returncode)
        self.assertEqual(2, self.call("version", root="/proc").returncode)

    def test_mount_boundary_denied(self):
        result = self.call("proc/version", root="/")
        self.assertIn(result.returncode, (2, 3))
        self.assertEqual(b"", result.stdout)

    def test_missing_file_repeated_cleanup(self):
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(20):
            self.assertEqual(3, self.call("missing").returncode)
        self.assertEqual(before, len(os.listdir("/proc/self/fd")))
