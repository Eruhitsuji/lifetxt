import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
