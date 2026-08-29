"""Standalone PyInstaller binary contract tests (#570).

Static checks always run. The real build+run tier is gated on PyInstaller
being importable and skips with a diagnostic reason otherwise (matching this
project's established pattern for environment-dependent suites) rather than
failing or silently passing — the dedicated
.github/workflows/standalone-binaries.yml workflow is the actual per-platform
build/smoke-test path; this local tier exists to catch a spec regression
quickly during development.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = REPO_ROOT / "packaging" / "pyinstaller" / "lifetxt.spec"
LAUNCHER = REPO_ROOT / "packaging" / "pyinstaller" / "lifetxt_launcher.py"


def _pyinstaller_available():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        return False, "PyInstaller is not installed in this environment"
    return True, ""


class PyInstallerSpecStaticContractTests(unittest.TestCase):
    def setUp(self):
        self.spec_text = SPEC_FILE.read_text(encoding="utf-8")
        self.launcher_text = LAUNCHER.read_text(encoding="utf-8")

    def test_launcher_calls_the_same_entry_point_as_the_console_script(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("lifetxt.entrypoint:main", pyproject)
        self.assertIn("from lifetxt.entrypoint import main", self.launcher_text)

    def test_spec_bundles_lifetxt_package_data(self):
        self.assertIn('collect_data_files("lifetxt")', self.spec_text)

    def test_spec_bundles_windows_timezone_data(self):
        self.assertIn('collect_data_files("tzdata")', self.spec_text)

    def test_spec_names_the_output_binary_lifetxt(self):
        self.assertIn('name="lifetxt"', self.spec_text)

    def test_spec_produces_a_console_executable(self):
        self.assertIn("console=True", self.spec_text)


@unittest.skipUnless(*_pyinstaller_available())
class PyInstallerBuildAndRunTests(unittest.TestCase):
    """Slow (~1-2 minute) real build. Runs only when PyInstaller is present."""

    @classmethod
    def setUpClass(cls):
        cls.build_dir = tempfile.mkdtemp(prefix="lifetxt-pyinstaller-test-")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                str(SPEC_FILE),
                "--distpath",
                str(Path(cls.build_dir) / "dist"),
                "--workpath",
                str(Path(cls.build_dir) / "work"),
                "--clean",
                "--noconfirm",
            ],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("PyInstaller build failed:\n%s" % result.stdout[-4000:])
        binary_name = "lifetxt.exe" if sys.platform == "win32" else "lifetxt"
        cls.binary = Path(cls.build_dir) / "dist" / binary_name
        if not cls.binary.exists():
            raise RuntimeError("Expected built binary not found: %s" % cls.binary)

    def test_version_flag(self):
        result = subprocess.run(
            [str(self.binary), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip().startswith("lifetxt "))

    def test_check_against_a_real_example(self):
        result = subprocess.run(
            [str(self.binary), "check", "examples/minimal_life.txt"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_init_and_doctor_in_a_clean_scratch_directory(self):
        scratch = tempfile.mkdtemp(prefix="lifetxt-pyinstaller-scratch-")
        init_result = subprocess.run(
            [str(self.binary), "init", "--yes"],
            cwd=scratch,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(init_result.returncode, 0, init_result.stderr)
        doctor_result = subprocess.run(
            [str(self.binary), "doctor"],
            cwd=scratch,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)

    def test_windows_timezone_resolution(self):
        scratch = Path(tempfile.mkdtemp(prefix="lifetxt-pyinstaller-tz-"))
        (scratch / "life.txt").write_text(
            "#!timezone: Asia/Tokyo\n[ ] T Sample_Task due:2026-09-01\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(self.binary), "check", "life.txt"],
            cwd=str(scratch),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundled_web_assets_are_served(self):
        scratch = Path(tempfile.mkdtemp(prefix="lifetxt-pyinstaller-web-"))
        (scratch / "life.txt").write_text(
            "[ ] T Sample_Task due:2026-09-01\n", encoding="utf-8"
        )
        process = subprocess.Popen(
            [
                str(self.binary),
                "serve",
                "life.txt",
                "--host",
                "127.0.0.1",
                "--port",
                "18324",
                "--read-only",
            ],
            cwd=str(scratch),
            # DEVNULL, not PIPE: a PyInstaller onefile bootloader forks a
            # worker child on Windows that inherits the pipe's write end,
            # so killing only the direct (bootloader) Popen handle still
            # leaves that worker holding the pipe open -- an unbounded
            # process.communicate() call afterward then hangs forever
            # waiting for EOF that never comes. Reproduced live: this
            # class's own PyInstaller build hung for over an hour before
            # this fix, confirmed via the real orphaned lifetxt.exe still
            # listening on this test's port after the Popen handle it came
            # from had already been killed.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            body = None
            # Bounded to 30s (60 x 0.5s), matching the same widened window
            # in tests/test_docker_image.py's equivalent poll -- a shared/
            # throttled CI runner can be slower to make a freshly started
            # process's port reachable than a local dev machine.
            for _ in range(60):
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:18324/api/health", timeout=1
                    ) as response:
                        body = response.read()
                        break
                except (urllib.error.URLError, ConnectionError):
                    time.sleep(0.5)
            self.assertIsNotNone(body, "server never answered /api/health")
        finally:
            if sys.platform == "win32":
                # Kills the whole process tree (/T), not just the direct
                # Popen handle, so the onefile bootloader's forked worker
                # does not survive as an orphan holding the port.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
