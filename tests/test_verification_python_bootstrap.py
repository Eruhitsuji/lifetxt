import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "verification_python_bootstrap.py"
)
spec = importlib.util.spec_from_file_location("verification_python_bootstrap", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

EXT_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "run_external_verification.py"
)
ext_spec = importlib.util.spec_from_file_location("external_verification", EXT_SCRIPT)
ext_module = importlib.util.module_from_spec(ext_spec)
ext_spec.loader.exec_module(ext_module)


def _fake_archive(member_name="python/bin/python3", content=b"fake interpreter"):
    """Build a small, real, valid tar.gz mirroring the python-build-standalone
    "python/..." wrapper layout, small enough for a fast unit test."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo(name=member_name)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class HostKeyTests(unittest.TestCase):
    def test_normalizes_known_platforms(self):
        self.assertEqual(("windows", "x86_64"), module.host_key("Windows", "AMD64"))
        self.assertEqual(("linux", "x86_64"), module.host_key("Linux", "x86_64"))
        self.assertEqual(("macos", "aarch64"), module.host_key("Darwin", "arm64"))

    def test_unknown_platform_or_arch_is_none(self):
        self.assertEqual((None, "x86_64"), module.host_key("FreeBSD", "x86_64"))
        self.assertEqual(("linux", None), module.host_key("Linux", "sparc"))


class FindExistingInterpreterTests(unittest.TestCase):
    def test_prefers_newest_supported_version_when_multiple_present(self):
        available = {
            "python3.10": "/usr/bin/python3.10",
            "python3.12": "/usr/bin/python3.12",
        }

        def fake_which(name):
            return available.get(name)

        def fake_probe(executable, run=None):
            return {"/usr/bin/python3.10": "3.10", "/usr/bin/python3.12": "3.12"}.get(
                executable
            )

        with mock.patch.object(module.os, "name", "posix"):
            result = module.find_existing_interpreter(
                env={}, which=fake_which, probe=fake_probe
            )

        self.assertIsNotNone(result)
        self.assertEqual("3.12", result["version"])
        self.assertEqual("existing", result["category"])

    def test_unsupported_only_versions_are_rejected(self):
        available = {"python3": "/usr/bin/python3"}

        def fake_which(name):
            return available.get(name)

        def fake_probe(executable, run=None):
            return "3.9"  # unsupported

        with mock.patch.object(module.os, "name", "posix"):
            result = module.find_existing_interpreter(
                env={}, which=fake_which, probe=fake_probe
            )

        self.assertIsNone(result)

    def test_no_interpreter_on_path_returns_none(self):
        with mock.patch.object(module.os, "name", "posix"):
            result = module.find_existing_interpreter(
                env={}, which=lambda name: None, probe=lambda exe, run=None: None
            )
        self.assertIsNone(result)

    def test_windows_py_launcher_is_tried_first(self):
        def fake_which(name):
            return "C:\\Windows\\py.exe" if name == "py" else None

        def fake_run(command, **kwargs):
            result = mock.Mock()
            if command[:2] == ["py", "-3.12"]:
                result.returncode = 0
                result.stdout = "3.12\n"
            else:
                result.returncode = 1
                result.stdout = ""
            return result

        with mock.patch.object(module.subprocess, "run", fake_run):
            result = module.find_existing_interpreter(
                env={"OS": "Windows_NT"}, which=fake_which
            )

        self.assertIsNotNone(result)
        self.assertEqual("py -3.12", result["executable"])
        self.assertEqual("3.12", result["version"])


class ProvisionManagedPythonTests(unittest.TestCase):
    FAKE_KEY = ("3.12", "linux", "x86_64")

    def _patched_manifest(
        self, filename="fake-cpython.tar.gz", content=b"fake interpreter"
    ):
        archive_bytes = _fake_archive(content=content)
        sha256 = hashlib.sha256(archive_bytes).hexdigest()
        entry = {"filename": filename, "sha256": sha256}
        return archive_bytes, entry

    def test_successful_download_verify_extract(self):
        archive_bytes, entry = self._patched_manifest()
        downloader = mock.Mock(return_value=archive_bytes)

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(module.MANIFEST, {self.FAKE_KEY: entry}),
        ):
            result = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=downloader
            )
            executable_exists = Path(result["executable"]).exists()

        self.assertEqual("passed", result["status"])
        self.assertEqual("managed", result["category"])
        self.assertEqual("3.12", result["version"])
        self.assertFalse(result["reused"])
        self.assertTrue(executable_exists)
        downloader.assert_called_once()

    def test_second_call_reuses_without_downloading_again(self):
        archive_bytes, entry = self._patched_manifest()
        downloader = mock.Mock(return_value=archive_bytes)

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(module.MANIFEST, {self.FAKE_KEY: entry}),
        ):
            first = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=downloader
            )
            second = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=downloader
            )

        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["executable"], second["executable"])
        downloader.assert_called_once()  # not called a second time

    def test_checksum_mismatch_is_rejected_before_extraction(self):
        archive_bytes, entry = self._patched_manifest()
        # Downloader returns bytes that don't match the manifest's sha256.
        downloader = mock.Mock(return_value=b"corrupted, does not match")

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(module.MANIFEST, {self.FAKE_KEY: entry}),
        ):
            result = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=downloader
            )
            install_dir_exists = (Path(tmp) / "python" / "3.12").exists()

        self.assertEqual("blocked", result["status"])
        self.assertIn("Checksum verification failed", result["reason"])
        self.assertFalse(install_dir_exists)

    def test_unsupported_host_returns_blocked_without_downloading(self):
        downloader = mock.Mock()

        with tempfile.TemporaryDirectory() as tmp:
            result = module.provision_managed_python(
                tmp, host=(None, "x86_64"), downloader=downloader
            )

        self.assertEqual("blocked", result["status"])
        downloader.assert_not_called()

    def test_no_manifest_entry_for_host_returns_blocked_without_downloading(self):
        downloader = mock.Mock()

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(module.MANIFEST, {}, clear=True),
        ):
            result = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=downloader
            )

        self.assertEqual("blocked", result["status"])
        downloader.assert_not_called()

    def test_download_failure_returns_blocked_not_a_crash(self):
        _archive_bytes, entry = self._patched_manifest()

        def failing_downloader(url):
            raise OSError("network unreachable")

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(module.MANIFEST, {self.FAKE_KEY: entry}),
        ):
            result = module.provision_managed_python(
                tmp, host=("linux", "x86_64"), downloader=failing_downloader
            )

        self.assertEqual("blocked", result["status"])
        self.assertIn("Download failed", result["reason"])


class EnsureVerificationPythonTests(unittest.TestCase):
    def test_prefers_existing_interpreter_over_managed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    module,
                    "find_existing_interpreter",
                    return_value={
                        "executable": "/usr/bin/python3.12",
                        "launcher": None,
                        "version": "3.12",
                        "category": "existing",
                    },
                ),
                mock.patch.object(module, "provision_managed_python") as managed,
            ):
                result = module.ensure_verification_python(tmp)

        self.assertEqual("existing", result["category"])
        managed.assert_not_called()

    def test_falls_back_to_managed_when_nothing_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    module, "find_existing_interpreter", return_value=None
                ),
                mock.patch.object(
                    module,
                    "provision_managed_python",
                    return_value={
                        "status": "passed",
                        "category": "managed",
                        "version": "3.12",
                    },
                ) as managed,
            ):
                result = module.ensure_verification_python(tmp)

        self.assertEqual("managed", result["category"])
        managed.assert_called_once()

    def test_blocked_when_neither_existing_nor_managed_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    module, "find_existing_interpreter", return_value=None
                ),
                mock.patch.object(
                    module,
                    "provision_managed_python",
                    return_value={
                        "status": "blocked",
                        "category": "managed",
                        "reason": "no network",
                    },
                ),
            ):
                result = module.ensure_verification_python(tmp)

        self.assertEqual("blocked", result["status"])
        self.assertIn("reason", result)


class CreateVerificationVenvTests(unittest.TestCase):
    def test_creates_once_and_reuses_on_second_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module.subprocess, "check_call") as check_call:

                def fake_check_call(command, **kwargs):
                    venv_dir = Path(command[-1])
                    venv_python = module._venv_python_path(venv_dir)
                    venv_python.parent.mkdir(parents=True, exist_ok=True)
                    venv_python.write_text("", encoding="utf-8")

                check_call.side_effect = fake_check_call

                first = module.create_verification_venv("/usr/bin/python3.12", tmp)
                second = module.create_verification_venv("/usr/bin/python3.12", tmp)

            self.assertEqual(first, second)
            check_call.assert_called_once()

    def test_recreates_when_source_interpreter_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module.subprocess, "check_call") as check_call:

                def fake_check_call(command, **kwargs):
                    venv_dir = Path(command[-1])
                    venv_python = module._venv_python_path(venv_dir)
                    venv_python.parent.mkdir(parents=True, exist_ok=True)
                    venv_python.write_text("", encoding="utf-8")

                check_call.side_effect = fake_check_call

                module.create_verification_venv("/usr/bin/python3.12", tmp)
                module.create_verification_venv("/usr/bin/python3.11", tmp)

            self.assertEqual(2, check_call.call_count)


class BootstrapRedactionTests(unittest.TestCase):
    """Bootstrap provenance (cache-dir/managed-runtime paths) must be
    covered by the existing #430 redaction guarantees without needing a
    new redaction category, since .cache/ lives inside repo_root."""

    def test_managed_runtime_path_under_repo_root_is_redacted_as_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir()
            cache_dir = repo_root / ".cache" / "lifetxt-verify"
            managed_python_path = str(
                cache_dir / "python" / "3.12" / "python" / "bin" / "python3"
            )

            redact = ext_module.make_redactor(repo_root, env={})
            result = redact(managed_python_path)

        self.assertNotIn(str(repo_root), result)
        self.assertIn("<repo>", result)


if __name__ == "__main__":
    unittest.main()
