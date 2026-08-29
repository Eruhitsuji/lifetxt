import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_evidence  # noqa: E402


class RunErrorSurfacingTests(unittest.TestCase):
    """Regression guard for a real CI diagnosability gap.

    The first real tag-triggered run of release.yml failed with a bare
    CalledProcessError and no indication of what the underlying `python -m
    build` subprocess actually reported, because _run() captured but never
    printed stdout/stderr before re-raising -- diagnosing the actual cause
    (a missing setuptools in the fresh runner's environment) required a
    local reproduction rather than reading the CI log directly.
    """

    def test_stdout_and_stderr_are_printed_before_raising(self):
        # The failing inner command's own stdout/stderr get *captured* by
        # _run() (stdout=PIPE, stderr=PIPE), then _run() re-emits both onto
        # this calling process's stderr before raising -- so both markers
        # must appear on the outer process's stderr, not split across
        # stdout/stderr of the outer process.
        inner_script = (
            "import sys; "
            "print('stdout-marker'); "
            "print('stderr-marker', file=sys.stderr); "
            "sys.exit(1)"
        )
        with tempfile.TemporaryDirectory() as tmp:
            inner_path = Path(tmp) / "inner.py"
            inner_path.write_text(inner_script, encoding="utf-8")
            driver_path = Path(tmp) / "driver.py"
            driver_path.write_text(
                dedent(
                    """
                    import sys
                    sys.path.insert(0, {scripts_dir!r})
                    import release_evidence
                    release_evidence._run(
                        [{python!r}, {inner_path!r}], {cwd!r}
                    )
                    """
                ).format(
                    scripts_dir=str(REPO_ROOT / "scripts"),
                    python=sys.executable,
                    inner_path=str(inner_path),
                    cwd=str(REPO_ROOT),
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(driver_path)],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stdout-marker", result.stderr)
        self.assertIn("stderr-marker", result.stderr)
        self.assertIn("CalledProcessError", result.stderr)

    def test_a_successful_command_still_returns_its_result(self):
        result = release_evidence._run(
            [sys.executable, "-c", "print('ok')"], str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
