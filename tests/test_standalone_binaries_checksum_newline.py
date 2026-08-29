"""Regression guard for a real CRLF bug in standalone-binaries.yml.

The "Compute checksum" step's embedded Python script opened each per-
artifact .sha256 file with a plain text-mode open(), which on a Windows
runner translates written '\n' to '\r\n'. Only the windows-x86_64 job runs
on Windows, so after `cat *.sha256 > SHA256SUMS` combined every platform's
checksum, the Windows entry alone carried a trailing CR -- breaking a
downstream `grep '...exe$'` anchored match in package-manifests.yml
against the combined file (reproduced live: two real v1.0.1 release runs
failed with "lifetxt-windows-x86_64.exe not found in this release's
SHA256SUMS" despite the entry actually being present, just CRLF-terminated).

This test statically asserts the workflow writes with an explicit
newline='\n' (disabling the platform translation) and directly proves,
using the exact same open() call the workflow's Python one-liner uses,
that it writes clean LF-only output regardless of host platform.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "standalone-binaries.yml"


class StandaloneBinariesChecksumNewlineTests(unittest.TestCase):
    def test_workflow_disables_platform_newline_translation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("open(name + '.sha256', 'w', newline='\\n')", text)

    def test_the_same_open_call_writes_lf_only_bytes(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "lifetxt-windows-x86_64.exe.sha256"
            digest = "0" * 64
            name = "lifetxt-windows-x86_64.exe"
            with open(path, "w", newline="\n") as handle:
                handle.write("%s  %s\n" % (digest, name))
            raw = path.read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertTrue(raw.endswith(b"lifetxt-windows-x86_64.exe\n"))


if __name__ == "__main__":
    unittest.main()
