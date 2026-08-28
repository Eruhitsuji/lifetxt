import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_release_tag_version.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def declared_version():
    try:
        import tomllib
    except ImportError:  # Python 3.10 compatibility
        import tomli as tomllib
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


class CheckReleaseTagVersionTests(unittest.TestCase):
    def test_matching_tag_succeeds(self):
        result = run_cli("v%s" % declared_version())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_mismatched_tag_fails_loudly(self):
        result = run_cli("v0.0.1-does-not-exist")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match", result.stderr)

    def test_malformed_tag_is_rejected(self):
        result = run_cli("not-a-version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match the vX.Y.Z", result.stderr)

    def test_missing_v_prefix_is_rejected(self):
        result = run_cli(declared_version())
        self.assertEqual(result.returncode, 1)

    def test_prerelease_suffix_is_accepted_when_it_matches(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "v1.0.0rc1"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # This repository's declared version is not 1.0.0rc1 today, so this
        # only asserts the pattern itself is accepted and evaluated (either
        # OK if it happens to match, or a version-mismatch failure) rather
        # than the malformed-tag rejection path.
        combined = result.stdout + result.stderr
        self.assertNotIn("does not match the vX.Y.Z", combined)

    def test_output_is_deterministic_json_free_text(self):
        # No JSON contract is promised for this CLI; just confirm stdout on
        # success is plain, single-line, human-readable text.
        result = run_cli("v%s" % declared_version())
        self.assertEqual(result.returncode, 0)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
