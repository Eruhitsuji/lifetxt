import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_external_verification.py"
spec = importlib.util.spec_from_file_location("external_verification", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PlatformClassificationTests(unittest.TestCase):
    def test_classifies_supported_hosts(self):
        self.assertEqual(module.classify_platform("Windows", "10", {}), "windows")
        self.assertEqual(module.classify_platform("Darwin", "25", {}), "macos")
        self.assertEqual(module.classify_platform("Linux", "6.8", {}), "linux")
        self.assertEqual(
            module.classify_platform("Linux", "6.6.0-microsoft-standard", {}),
            "wsl",
        )
        self.assertEqual(
            module.classify_platform("Linux", "6.8", {"WSL_DISTRO_NAME": "Ubuntu"}),
            "wsl",
        )


class RedactionTests(unittest.TestCase):
    def test_redacts_repo_home_temp_usernames_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            env = {
                "HOME": "/home/alice",
                "USER": "alice",
                "MY_API_TOKEN": "super-secret-token",
            }
            redact = module.make_redactor(repo, env=env)
            text = (
                f"{repo}/file /home/alice/x {tempfile.gettempdir()}/work "
                "user=alice C:\\Users\\alice\\work "
                "Authorization: Bearer xyz token=abc super-secret-token"
            )
            result = redact(text)
            self.assertNotIn(str(repo), result)
            self.assertNotIn("/home/alice", result)
            self.assertNotIn("user=alice", result)
            self.assertNotIn("\\alice\\", result)
            self.assertNotIn("super-secret-token", result)
            self.assertNotIn("Bearer xyz", result)
            self.assertNotIn("token=abc", result)
            self.assertIn("<repo>", result)
            self.assertIn("<home>", result)
            self.assertIn("<redacted-user>", result)
            self.assertIn("<redacted-secret>", result)


class RedactionHardeningTests(unittest.TestCase):
    """Case-insensitivity, overlap ordering, and idempotency (#430).

    Reproduced two real defects before fixing them: a case-sensitive
    str.replace() never matched a differently-cased path a child tool (e.g.
    pip) emitted, and a fixed repo/home/temp processing order let a shorter
    path (home) consume a longer, more specific one's shared prefix (%TEMP%
    nested inside %USERPROFILE% on a normal Windows host) before the longer
    one's own marker had a chance to apply.
    """

    def _windows_redactor(self):
        env = {"USERPROFILE": r"C:\Users\tester", "USERNAME": "tester"}
        return module.make_redactor(repo_root=r"C:\repo", env=env)

    def test_windows_path_redaction_is_case_insensitive(self):
        redact = self._windows_redactor()
        for text in (
            r"C:\Users\tester\file.txt",
            r"c:\users\tester\file.txt",
            r"C:\USERS\TESTER\file.txt",
            r"c:/users/tester/file.txt",
        ):
            result = redact(text)
            self.assertNotIn("tester", result.lower(), msg=text)
            self.assertIn("<home>", result, msg=text)

    def test_longer_nested_path_wins_over_a_shorter_containing_one(self):
        # %TEMP% is nested inside %USERPROFILE% on a normal Windows host --
        # the longer, more specific temp path must win, not be silently
        # absorbed into a bare <home>\AppData\Local\Temp\... remnant.
        home = r"C:\Users\tester"
        temp = home + r"\AppData\Local\Temp"
        with mock.patch.object(module.tempfile, "gettempdir", return_value=temp):
            redact = module.make_redactor(
                repo_root=r"C:\repo",
                env={"USERPROFILE": home, "USERNAME": "tester"},
            )
            result = redact(temp + r"\pip-req-build-0")
        self.assertEqual(r"<temp>\pip-req-build-0", result)
        self.assertNotIn("AppData", result)
        self.assertNotIn("<home>", result)

    def test_redaction_is_idempotent(self):
        redact = self._windows_redactor()
        inputs = (
            r"C:\Users\tester\AppData\Local\Temp\pip-req-build-0",
            "user=tester token=abc123 Authorization: Bearer xyz",
            "already <home>\\AppData\\Local\\Temp\\<repo> plain text",
            r"c:/users/TESTER/mixed/Case/Path",
        )
        for text in inputs:
            once = redact(text)
            twice = redact(once)
            self.assertEqual(once, twice, msg=text)


class CommandCaptureTests(unittest.TestCase):
    def test_captures_stdout_stderr_and_exit_code(self):
        redact = lambda value: str(value)
        record = module.run_command(
            [
                os.sys.executable,
                "-c",
                "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(3)",
            ],
            Path.cwd(),
            redact,
            10,
        )
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["exit_code"], 3)
        self.assertIn("out", record["stdout"])
        self.assertIn("err", record["stderr"])
        self.assertGreaterEqual(record["duration_seconds"], 0)


class BundleTests(unittest.TestCase):
    def test_skip_release_is_explicit_and_bundle_writes_one_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "lifetxt"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            args = argparse.Namespace(
                skip_release=True,
                artifact=[],
                probe_timeout=1,
                release_timeout=1,
            )
            bundle = module.build_bundle(root, args)
            release = next(
                item for item in bundle["checks"] if item["scenario"] == "release-profile"
            )
            self.assertEqual(release["status"], "skipped")
            self.assertEqual(bundle["schema_version"], 1)
            self.assertIn("manual_or_external_scenarios", bundle)
            self.assertTrue(
                all(
                    item["status"] in {"manual_required", "blocked"}
                    for item in bundle["manual_or_external_scenarios"]
                )
            )
            output = root / "bundle.json"
            module.write_bundle(bundle, output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], 1)
            self.assertEqual(loaded["metadata"]["package_version"], "0.1.0")

    def test_source_pyproject_version_precedes_installed_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "lifetxt"\nversion = "9.9.9"\n',
                encoding="utf-8",
            )
            self.assertEqual(module._package_version(root), "9.9.9")

    def test_bundle_exit_code_fails_required_automated_check(self):
        self.assertEqual(
            module.bundle_exit_code(
                {
                    "checks": [
                        {"scenario": "git-identity", "status": "passed"},
                        {"scenario": "release-profile", "status": "failed"},
                    ]
                }
            ),
            1,
        )
        self.assertEqual(
            module.bundle_exit_code(
                {
                    "checks": [
                        {"scenario": "git-identity", "status": "passed"},
                        {"scenario": "release-profile", "status": "skipped"},
                    ]
                }
            ),
            0,
        )


class WriteBundleSafetyNetTests(unittest.TestCase):
    """Persistence-time rescan-and-refuse defense in depth (#430).

    Even if a future redaction-rule change misses a case, write_bundle must
    refuse to persist a bundle where a raw candidate value survived, rather
    than silently writing partially-redacted evidence.
    """

    def test_refuses_to_write_a_bundle_still_containing_a_raw_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            bundle = {"note": "leaked C:\\Users\\tester\\secret-looking-path"}

            with self.assertRaises(RuntimeError) as caught:
                module.write_bundle(
                    bundle, output, redaction_candidates=[r"C:\Users\tester"]
                )

            self.assertNotIn("tester", str(caught.exception))
            self.assertFalse(output.exists())

    def test_json_escaped_backslash_form_of_a_candidate_is_also_detected(self):
        # json.dumps() escapes "\" as "\\", so a raw Windows path candidate
        # would never match the serialized text unless the rescan also
        # checks the JSON-escaped form -- this is the exact bug found and
        # fixed while implementing the safety net.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            bundle = {"note": r"C:\Users\tester\secret-looking-path"}

            with self.assertRaises(RuntimeError):
                module.write_bundle(
                    bundle, output, redaction_candidates=[r"C:\Users\tester"]
                )

    def test_a_properly_redacted_bundle_writes_normally(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            bundle = {"note": "<home>\\secret-looking-path"}

            module.write_bundle(
                bundle, output, redaction_candidates=[r"C:\Users\tester"]
            )

            self.assertTrue(output.exists())
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(bundle, loaded)

    def test_no_redaction_candidates_preserves_prior_behavior(self):
        # Backward compatible default: existing callers that don't pass
        # redaction_candidates (e.g. tests.test_external_verification's own
        # pre-#430 BundleTests) still write unconditionally.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            module.write_bundle({"note": "anything at all"}, output)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
