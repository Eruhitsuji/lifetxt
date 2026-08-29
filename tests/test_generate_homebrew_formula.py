import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_homebrew_formula.py"

FAKE_SHA256SUMS = "\n".join(
    "%s  %s" % (str(i) * 64, name)
    for i, name in enumerate(
        [
            "lifetxt-windows-x86_64.exe",
            "lifetxt-linux-x86_64",
            "lifetxt-linux-arm64",
            "lifetxt-macos-arm64",
            "lifetxt-macos-x86_64",
        ],
        start=1,
    )
)


def _ruby_available():
    return shutil.which("ruby") is not None


class GenerateHomebrewFormulaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sums_path = Path(self.tmp.name) / "SHA256SUMS"
        self.sums_path.write_text(FAKE_SHA256SUMS, encoding="utf-8")
        self.output_path = Path(self.tmp.name) / "lifetxt.rb"

    def run_cli(self, *extra_args):
        args = [
            sys.executable,
            str(SCRIPT),
            "--version",
            "1.0.0",
            "--sha256sums",
            str(self.sums_path),
            "--output",
            str(self.output_path),
        ]
        args += list(extra_args)
        return subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

    def test_generates_a_formula_referencing_all_four_release_platforms(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.output_path.read_text(encoding="utf-8")
        self.assertIn("lifetxt-macos-arm64", text)
        self.assertIn("lifetxt-macos-x86_64", text)
        self.assertIn("lifetxt-linux-arm64", text)
        self.assertIn("lifetxt-linux-x86_64", text)
        self.assertIn('version "1.0.0"', text)
        self.assertIn("v1.0.0/lifetxt-macos-arm64", text)

    def test_fails_loudly_when_a_platform_checksum_is_missing(self):
        incomplete = Path(self.tmp.name) / "SHA256SUMS_incomplete"
        incomplete.write_text(
            "1111111111111111111111111111111111111111111111111111111111111111  lifetxt-macos-arm64\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--version",
                "1.0.0",
                "--sha256sums",
                str(incomplete),
                "--output",
                str(self.output_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing", result.stderr.lower())
        self.assertFalse(self.output_path.exists())

    def test_ruby_string_interpolation_in_the_test_block_is_not_mangled(self):
        # Regression guard: the generator builds the Ruby source through
        # Python's str.format(); Ruby's own "#{expr}" interpolation syntax
        # must survive that (as a literal "#{bin}" in the output), not be
        # consumed as a Python format placeholder.
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.output_path.read_text(encoding="utf-8")
        self.assertIn('shell_output("#{bin}/lifetxt --version")', text)

    @unittest.skipUnless(_ruby_available(), "ruby is not installed")
    def test_generated_formula_is_syntactically_valid_ruby(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        check = subprocess.run(
            ["ruby", "-c", str(self.output_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("Syntax OK", check.stdout)


if __name__ == "__main__":
    unittest.main()
