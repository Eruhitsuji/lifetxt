"""Tests for the provider-independent rclone backup remote backend
(#836/#843): lifetxt/backup_remote.py.

Uses a controlled, local, dependency-free fake `rclone` (a tiny Python
script invoked as ``[sys.executable, fake_rclone.py, ...]``) so these
tests never require a real rclone install or real cloud credentials, per
#843's own explicit test requirement.
"""

import os
import sys
import tempfile
import unittest

from lifetxt.backup_remote import (
    RcloneError,
    delete_remote_backup,
    list_remote_backups,
    rclone_available,
    upload_backup,
)

_FAKE_RCLONE = r"""
import json
import sys

args = sys.argv[1:]
cmd = args[0] if args else ""

if cmd == "copyto":
    src, dest = args[1], args[2]
    dest_path = dest.split(":", 1)[1]
    if "faildest" in dest_path:
        sys.stderr.write("mock upload failure: destination refused\n")
        sys.exit(1)
    with open(src, "rb") as f:
        data = f.read()
    import os as _os
    _os.makedirs(_os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(data)
    sys.exit(0)
elif cmd == "lsjson":
    target = args[1]
    import os as _os
    remote_dir = target.split(":", 1)[1]
    if not _os.path.isdir(remote_dir):
        print("[]")
        sys.exit(0)
    entries = [
        {"Name": name, "IsDir": False}
        for name in sorted(_os.listdir(remote_dir))
        if _os.path.isfile(_os.path.join(remote_dir, name))
    ]
    print(json.dumps(entries))
    sys.exit(0)
elif cmd == "deletefile":
    target = args[1]
    import os as _os
    path = target.split(":", 1)[1]
    if not _os.path.isfile(path):
        sys.stderr.write("mock delete failure: not found\n")
        sys.exit(1)
    _os.unlink(path)
    sys.exit(0)
else:
    sys.stderr.write("unknown command\n")
    sys.exit(2)
"""


class BackupRemoteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.script = os.path.join(self._tmp.name, "fake_rclone.py")
        with open(self.script, "w", encoding="utf-8") as f:
            f.write(_FAKE_RCLONE)
        self.rclone_bin = [sys.executable, self.script]
        self.remote_root = os.path.join(self._tmp.name, "remote")
        os.makedirs(self.remote_root)

    def _remote_target(self, subdir="backups"):
        path = os.path.join(self.remote_root, subdir)
        os.makedirs(path, exist_ok=True)
        return "fakeremote:" + path

    def test_fake_rclone_is_reported_available(self):
        self.assertTrue(rclone_available(self.rclone_bin))

    def test_upload_copies_the_file_to_the_remote_directory(self):
        with open(os.path.join(self._tmp.name, "b.ltbackup"), "wb") as f:
            f.write(b"backup-bytes")
        target = self._remote_target()
        upload_backup(
            os.path.join(self._tmp.name, "b.ltbackup"),
            target,
            rclone_bin=self.rclone_bin,
        )
        dest = os.path.join(target.split(":", 1)[1], "b.ltbackup")
        with open(dest, "rb") as f:
            self.assertEqual(b"backup-bytes", f.read())

    def test_upload_never_deletes_an_existing_remote_file_merely_because_the_source_vanished(
        self,
    ):
        target = self._remote_target()
        remote_dir = target.split(":", 1)[1]
        with open(os.path.join(remote_dir, "old.ltbackup"), "wb") as f:
            f.write(b"already-there")
        # The "source" for this filename never existed locally; upload_backup
        # is never even asked to touch old.ltbackup, and nothing in this
        # module deletes anything on upload -- confirmed by it still being
        # present afterward.
        with open(os.path.join(self._tmp.name, "new.ltbackup"), "wb") as f:
            f.write(b"new-bytes")
        upload_backup(
            os.path.join(self._tmp.name, "new.ltbackup"),
            target,
            rclone_bin=self.rclone_bin,
        )
        self.assertTrue(os.path.isfile(os.path.join(remote_dir, "old.ltbackup")))

    def test_upload_failure_raises_and_leaves_the_local_backup_intact(self):
        with open(os.path.join(self._tmp.name, "b.ltbackup"), "wb") as f:
            f.write(b"local-bytes")
        with self.assertRaises(RcloneError):
            upload_backup(
                os.path.join(self._tmp.name, "b.ltbackup"),
                "fakeremote:" + os.path.join(self.remote_root, "faildest"),
                rclone_bin=self.rclone_bin,
            )
        with open(os.path.join(self._tmp.name, "b.ltbackup"), "rb") as f:
            self.assertEqual(b"local-bytes", f.read())

    def test_missing_rclone_binary_raises_actionably(self):
        missing = [sys.executable, os.path.join(self._tmp.name, "does-not-exist.py")]
        with open(os.path.join(self._tmp.name, "b.ltbackup"), "wb") as f:
            f.write(b"x")
        with self.assertRaises(RcloneError):
            upload_backup(
                os.path.join(self._tmp.name, "b.ltbackup"),
                self._remote_target(),
                rclone_bin=missing,
            )

    def test_paths_with_spaces_are_passed_safely(self):
        weird_dir = os.path.join(self._tmp.name, "has space & stuff")
        os.makedirs(weird_dir)
        src = os.path.join(weird_dir, "weird name.ltbackup")
        with open(src, "wb") as f:
            f.write(b"payload")
        target = self._remote_target("dest with space")
        upload_backup(src, target, rclone_bin=self.rclone_bin)
        dest = os.path.join(target.split(":", 1)[1], "weird name.ltbackup")
        self.assertTrue(os.path.isfile(dest))

    def test_remote_target_without_a_colon_is_rejected(self):
        with self.assertRaises(RcloneError):
            upload_backup(
                os.path.join(self._tmp.name, "b.ltbackup"),
                "not-a-remote-target",
                rclone_bin=self.rclone_bin,
            )

    def test_bare_remote_root_with_no_path_is_rejected(self):
        with self.assertRaises(RcloneError):
            upload_backup(
                os.path.join(self._tmp.name, "b.ltbackup"),
                "fakeremote:",
                rclone_bin=self.rclone_bin,
            )

    def test_list_remote_backups_returns_filenames(self):
        target = self._remote_target()
        remote_dir = target.split(":", 1)[1]
        for name in ("a.ltbackup", "b.ltbackup"):
            with open(os.path.join(remote_dir, name), "wb") as f:
                f.write(b"x")
        names = list_remote_backups(target, rclone_bin=self.rclone_bin)
        self.assertEqual(["a.ltbackup", "b.ltbackup"], sorted(names))

    def test_delete_remote_backup_removes_exactly_the_named_object(self):
        target = self._remote_target()
        remote_dir = target.split(":", 1)[1]
        with open(os.path.join(remote_dir, "a.ltbackup"), "wb") as f:
            f.write(b"x")
        with open(os.path.join(remote_dir, "b.ltbackup"), "wb") as f:
            f.write(b"y")
        delete_remote_backup(target, "a.ltbackup", rclone_bin=self.rclone_bin)
        self.assertFalse(os.path.exists(os.path.join(remote_dir, "a.ltbackup")))
        self.assertTrue(os.path.exists(os.path.join(remote_dir, "b.ltbackup")))

    def test_delete_remote_backup_rejects_a_path_like_filename(self):
        target = self._remote_target()
        with self.assertRaises(RcloneError):
            delete_remote_backup(
                target, "../escape.ltbackup", rclone_bin=self.rclone_bin
            )
        with self.assertRaises(RcloneError):
            delete_remote_backup(
                target, "sub/child.ltbackup", rclone_bin=self.rclone_bin
            )


if __name__ == "__main__":
    unittest.main()
