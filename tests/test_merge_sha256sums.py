import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "merge_sha256sums.py"

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class MergeSha256SumsCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_merges_disjoint_files_into_one_sorted_manifest(self):
        # Mirrors the real scenario this fixes: release.yml's wheel/sdist
        # checksums and standalone-binaries.yml's platform-binary checksums
        # cover entirely different filenames and must both survive.
        existing = self.write(
            "existing.txt",
            "%s  lifetxt-linux-x86_64\n%s  lifetxt-windows-x86_64.exe\n"
            % (HASH_A, HASH_B),
        )
        fresh = self.write("fresh.txt", "%s  lifetxt-1.0.0-py3-none-any.whl\n" % HASH_C)
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(existing), str(fresh), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stderr)
        merged = output.read_text(encoding="utf-8")
        self.assertIn("%s  lifetxt-1.0.0-py3-none-any.whl" % HASH_C, merged)
        self.assertIn("%s  lifetxt-linux-x86_64" % HASH_A, merged)
        self.assertIn("%s  lifetxt-windows-x86_64.exe" % HASH_B, merged)
        self.assertEqual(len(merged.splitlines()), 3)

    def test_missing_input_file_is_skipped_not_an_error(self):
        # A workflow run that is the first to publish SHA256SUMS for a given
        # tag has no prior asset to download; the merge must still succeed
        # using only the file(s) that do exist.
        missing = self.dir / "does-not-exist.txt"
        fresh = self.write("fresh.txt", "%s  lifetxt-linux-x86_64\n" % HASH_A)
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(missing), str(fresh), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "%s  lifetxt-linux-x86_64\n" % HASH_A,
        )

    def test_every_input_missing_fails_loudly(self):
        first = self.dir / "gone1.txt"
        second = self.dir / "gone2.txt"
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(first), str(second), "--output", str(output))

        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing to merge", result.stderr)
        self.assertFalse(output.exists())

    def test_later_input_wins_on_a_filename_collision(self):
        # A rerun of the same job for the same tag regenerates byte-identical
        # hashes in practice, but the precedence rule itself (later input
        # wins) must hold regardless, so a caller can rely on argument order.
        older = self.write("older.txt", "%s  lifetxt-linux-x86_64\n" % HASH_A)
        newer = self.write("newer.txt", "%s  lifetxt-linux-x86_64\n" % HASH_B)
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(older), str(newer), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "%s  lifetxt-linux-x86_64\n" % HASH_B,
        )

    def test_output_has_no_carriage_returns(self):
        # A CRLF-contaminated SHA256SUMS previously broke a downstream
        # end-of-line-anchored grep (#586); the merge tool must not
        # reintroduce that regardless of host platform newline conventions.
        fresh = self.write("fresh.txt", "%s  lifetxt-linux-x86_64\n" % HASH_A)
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(fresh), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("\r", output.read_bytes().decode("utf-8"))

    def test_malformed_line_fails_loudly_and_writes_nothing(self):
        bad = self.write("bad.txt", "not-a-valid-checksum-line\n")
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(bad), "--output", str(output))

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not look like", result.stderr)
        self.assertFalse(output.exists())

    def test_blank_lines_are_ignored(self):
        fresh = self.write("fresh.txt", "\n%s  lifetxt-linux-x86_64\n\n" % HASH_A)
        output = self.dir / "SHA256SUMS"

        result = run_cli(str(fresh), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "%s  lifetxt-linux-x86_64\n" % HASH_A,
        )


if __name__ == "__main__":
    unittest.main()
