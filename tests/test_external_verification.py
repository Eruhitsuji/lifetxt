import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_external_verification.py"
spec = importlib.util.spec_from_file_location("external_verification", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

REPO_ROOT = SCRIPT.parents[1]
BASH_EXECUTABLE = shutil.which("bash")


def _bash_skip_reason():
    """Probe bash the same way tests.test_roundtrip_golden does: some launchers
    found on PATH (e.g. the WSL wrapper at C:\\Windows\\System32\\bash.exe) do
    not behave as a usable POSIX shell for a plain subprocess invocation."""
    if not BASH_EXECUTABLE:
        return "bash was not found on PATH"
    try:
        probe = subprocess.run(
            [BASH_EXECUTABLE, "--noprofile", "--norc", "-c", "echo lifetxt-bash-probe"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return f"{BASH_EXECUTABLE} could not be executed: {exc}"
    if probe.returncode != 0 or "lifetxt-bash-probe" not in probe.stdout:
        return (
            f"{BASH_EXECUTABLE} does not behave as a usable POSIX shell here; "
            "run this test on Linux/macOS or with Git Bash ahead of it on PATH."
        )
    return None


BASH_SKIP_REASON = _bash_skip_reason()


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


class TempPathCanonicalizationTests(unittest.TestCase):
    """#438: end-to-end canonicalization was not idempotent when a raw
    candidate value recurs adjacent to itself, or when a subprocess reports
    an OS-specific alias/mount view #430's exact-value matching never
    textually equals. Reproduced with synthetic paths only.
    """

    def test_adjacent_raw_temp_occurrences_collapse_to_one_marker(self):
        # A temp directory containing another directory literally named
        # "tmp" (a real, plausible shape -- Python's own tempfile.mkdtemp()
        # default prefix is "tmp") makes the raw temp value recur as a
        # substring immediately next to itself in the raw text.
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
            result = redact("/tmp/tmp/subdir/file.txt")
        self.assertEqual("<temp>/subdir/file.txt", result)
        self.assertNotIn("<temp><temp>", result)

    def test_three_adjacent_raw_temp_occurrences_still_collapse_to_one(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
            result = redact("before /tmp/tmp/tmp/nested after")
        self.assertEqual("before <temp>/nested after", result)

    def test_resanitizing_already_canonical_or_nested_marker_text_stays_one_root(self):
        # AC: re-sanitizing a string containing <temp>/..., <temp>\\..., or
        # another already-canonical placeholder leaves exactly one root.
        redact = module.make_redactor(
            repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
        )
        for already_sanitized in (
            "<temp><temp>/subdir",
            "<temp>/<temp>\\subdir",
            "prefix <temp><temp><temp> suffix",
            "<repo><repo>/file",
            "<home><home>\\file",
        ):
            result = redact(already_sanitized)
            for marker in ("<temp>", "<repo>", "<home>"):
                self.assertNotIn(marker + marker, result, msg=already_sanitized)

    def test_macos_private_temp_alias_canonicalizes_without_a_malformed_prefix(self):
        # macOS resolves tempfile.gettempdir()'s "/var/folders/..." result
        # through a "/private" symlink; a tool reporting the resolved form
        # must not leave a "/private<temp>" remnant.
        temp = "/var/folders/xx/yyyyzzzz/T"
        with mock.patch.object(module.tempfile, "gettempdir", return_value=temp):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/Users/alice", "USER": "alice"}
            )
            result = redact("/private" + temp + "/subdir/file.txt")
        self.assertEqual("<temp>/subdir/file.txt", result)
        self.assertNotIn("/private", result)
        self.assertNotIn("private<temp>", result)

    def test_macos_private_tmp_alias_canonicalizes(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/Users/alice", "USER": "alice"}
            )
            result = redact("/private/tmp/subdir/file.txt")
        self.assertEqual("<temp>/subdir/file.txt", result)
        self.assertNotIn("private", result)

    def test_windows_username_only_match_collapses_known_temp_suffix(self):
        # WSL's own HOME (a POSIX path) never textually matches a captured
        # Windows-side path reported through WSL's "/mnt/c" mount view --
        # only the generic username pattern catches the account name,
        # leaving a structurally-recognizable temp path around it.
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/bob", "USER": "bob"}
            )
            result = redact(
                "/mnt/c/Users/bob/AppData/Local/Temp/pip-build-xyz/file.txt"
            )
        self.assertEqual("<temp>/pip-build-xyz/file.txt", result)
        self.assertNotIn("bob", result)
        self.assertNotIn("<redacted-user>", result)

    def test_windows_backslash_username_only_match_collapses_known_temp_suffix(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/bob", "USER": "bob"}
            )
            result = redact(r"C:\Users\bob\AppData\Local\Temp\pip-build-xyz\file.txt")
        self.assertEqual(r"<temp>\pip-build-xyz\file.txt", result)
        self.assertNotIn("bob", result)
        self.assertNotIn("<redacted-user>", result)

    def test_repeated_recursive_passes_stay_canonical(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
            once = redact("/tmp/tmp/subdir/file.txt")
            twice = redact(once)
            thrice = redact(twice)
        self.assertEqual(once, twice)
        self.assertEqual(twice, thrice)
        self.assertEqual("<temp>/subdir/file.txt", thrice)

    def test_overlap_with_repo_and_home_paths_still_canonicalizes(self):
        # repo nested inside home, itself nested inside temp -- the
        # longest-match-wins ordering (#430) plus the new collapse pass
        # (#438) must still pick the correct, most specific marker for
        # each segment rather than merging genuinely distinct roots.
        home = "/home/alice"
        temp = home + "/tmp"
        repo = temp + "/checkout/lifetxt"
        with mock.patch.object(module.tempfile, "gettempdir", return_value=temp):
            redact = module.make_redactor(
                repo_root=repo, env={"HOME": home, "USER": "alice"}
            )
            result = redact(repo + "/tests/fixture.txt " + home + "/notes.txt")
        self.assertEqual("<repo>/tests/fixture.txt <home>/notes.txt", result)
        self.assertNotIn(repo, result)
        self.assertNotIn(home, result)
        self.assertNotIn("<repo><repo>", result)
        self.assertNotIn("<home><home>", result)

        # A genuinely repeated repo occurrence (e.g. the same checkout path
        # mentioned twice back to back) is exactly the #438 case and must
        # still canonicalize to one marker, not double up.
        with mock.patch.object(module.tempfile, "gettempdir", return_value=temp):
            redact = module.make_redactor(
                repo_root=repo, env={"HOME": home, "USER": "alice"}
            )
            doubled = redact(repo + "/" + repo + "/tests/fixture.txt")
        self.assertEqual("<repo>/tests/fixture.txt", doubled)
        self.assertNotIn("<repo><repo>", doubled)

    def test_write_bundle_safety_net_catches_the_macos_private_alias_too(self):
        # The persistence-time leak scan (#430) must know about the
        # macOS-alias variant registered for redaction, or a bundle that
        # somehow still carried the raw "/private/..." form would silently
        # pass the safety net that #430 built specifically to catch this
        # class of gap.
        temp = "/var/folders/xx/yyyyzzzz/T"
        with mock.patch.object(module.tempfile, "gettempdir", return_value=temp):
            candidates = module._redaction_candidates(
                repo_root=None, env={"HOME": "/Users/alice", "USER": "alice"}
            )
        self.assertIn("/private" + temp, candidates)


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

    def test_timeout_is_a_distinct_status_from_failed_with_retained_partial_output(
        self,
    ):
        # #437: a timeout must be distinguishable from a command that ran and
        # returned a non-zero exit code, must record the configured limit,
        # and must retain whatever output was already produced.
        redact = lambda value: str(value)
        record = module.run_command(
            [
                sys.executable,
                "-c",
                "import time; print('partial-output', flush=True); time.sleep(5)",
            ],
            Path.cwd(),
            redact,
            1,
        )
        self.assertEqual(record["status"], "timeout")
        self.assertNotEqual(record["status"], "failed")
        self.assertIsNone(record["exit_code"])
        self.assertEqual(record["timeout_seconds"], 1)
        self.assertIn("timeout after 1 seconds", record["error"])
        self.assertIn("partial-output", record["stdout"])


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

    def test_bootstrap_venv_creation_failure_is_blocked_not_a_crash(self):
        # Found live on a real WSL host (#435): an interpreter can be
        # discovered successfully but its own `-m venv` can still fail
        # (e.g. missing ensurepip support). That must degrade to a blocked
        # release-profile check with the evidence bundle still written,
        # never an uncaught exception that loses the whole run.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "lifetxt"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            args = argparse.Namespace(
                skip_release=False,
                artifact=[],
                probe_timeout=1,
                release_timeout=1,
            )
            with (
                mock.patch.object(
                    module.verification_python_bootstrap,
                    "ensure_verification_python",
                    return_value={
                        "status": "passed",
                        "category": "existing",
                        "executable": "/usr/bin/python3.10",
                        "version": "3.10",
                    },
                ),
                mock.patch.object(
                    module.verification_python_bootstrap,
                    "create_verification_venv",
                    side_effect=module.subprocess.CalledProcessError(
                        1, ["python3.10", "-m", "venv"]
                    ),
                ),
            ):
                bundle = module.build_bundle(root, args)

        release = next(
            item for item in bundle["checks"] if item["scenario"] == "release-profile"
        )
        self.assertEqual("blocked", release["status"])
        self.assertIn("isolated verification environment", release["reason"])

    def test_bootstrap_failure_blocks_release_profile_without_a_fabricated_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "lifetxt"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            args = argparse.Namespace(
                skip_release=False,
                artifact=[],
                probe_timeout=1,
                release_timeout=1,
            )
            with mock.patch.object(
                module.verification_python_bootstrap,
                "ensure_verification_python",
                return_value={
                    "status": "blocked",
                    "category": "managed",
                    "reason": "No network access to provision a managed Python runtime.",
                },
            ):
                bundle = module.build_bundle(root, args)

        bootstrap = next(
            item for item in bundle["checks"] if item["scenario"] == "python-bootstrap"
        )
        release = next(
            item for item in bundle["checks"] if item["scenario"] == "release-profile"
        )
        self.assertEqual("blocked", bootstrap["status"])
        self.assertEqual("blocked", release["status"])
        self.assertNotEqual("passed", release["status"])

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

    def test_bundle_exit_code_fails_on_release_profile_timeout_not_a_pass(self):
        # #437: a timeout must fail the collector's own exit code exactly
        # like "failed" -- it is never mistaken for a pass.
        self.assertEqual(
            module.bundle_exit_code(
                {
                    "checks": [
                        {"scenario": "git-identity", "status": "passed"},
                        {"scenario": "release-profile", "status": "timeout"},
                    ]
                }
            ),
            1,
        )

    def test_bundle_exit_code_fails_on_git_identity_timeout(self):
        self.assertEqual(
            module.bundle_exit_code(
                {
                    "checks": [
                        {"scenario": "git-identity", "status": "timeout"},
                        {"scenario": "release-profile", "status": "skipped"},
                    ]
                }
            ),
            1,
        )


class ReleaseTimeoutConfigurationTests(unittest.TestCase):
    """#437: real supported-host runs at commit b57aa84 showed the previous
    fixed 7200-second release-profile timeout was too tight for slower hosts,
    and Linux/macOS reached the full test run without demonstrating an actual
    incompatibility before the collector cut them off."""

    def test_default_release_timeout_has_headroom_over_observed_real_host_durations(
        self,
    ):
        args = module.build_parser().parse_args([])
        self.assertEqual(args.release_timeout, module.DEFAULT_RELEASE_TIMEOUT_SECONDS)
        # Highest confirmed real-host release-profile duration was ~5316s
        # (Windows). The default must retain real headroom above it, not
        # just nominally exceed it, while still bounding a hung process.
        self.assertGreaterEqual(module.DEFAULT_RELEASE_TIMEOUT_SECONDS, 5316 * 2)

    def test_probe_timeout_stays_independently_short_by_default(self):
        args = module.build_parser().parse_args([])
        self.assertEqual(args.probe_timeout, 30)
        self.assertLess(args.probe_timeout, module.DEFAULT_RELEASE_TIMEOUT_SECONDS)

    def test_release_timeout_cli_override_propagates_to_parsed_args(self):
        args = module.build_parser().parse_args(["--release-timeout", "1234"])
        self.assertEqual(args.release_timeout, 1234)

    def test_probe_timeout_cli_override_is_independent_of_release_timeout(self):
        args = module.build_parser().parse_args(
            ["--release-timeout", "1234", "--probe-timeout", "5"]
        )
        self.assertEqual(args.release_timeout, 1234)
        self.assertEqual(args.probe_timeout, 5)

    def test_summary_line_reports_the_configured_release_timeout(self):
        # main() always runs against the real repository root, so this exercises
        # the actual collector end to end (skip-release keeps it fast/offline)
        # rather than a synthetic fixture -- proving the CLI value that was
        # parsed is the value actually used and surfaced as evidence.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = module.main(
                    [
                        "--skip-release",
                        "--probe-timeout",
                        "1",
                        "--release-timeout",
                        "9999",
                        "--output",
                        str(output),
                    ]
                )
        self.assertEqual(0, code)
        self.assertIn("release_timeout=9999", buffer.getvalue())


@unittest.skipIf(BASH_SKIP_REASON is not None, BASH_SKIP_REASON or "")
class VerifyExternalShWrapperTests(unittest.TestCase):
    """#437 acceptance criterion: verify-external.sh must be able to pass an
    explicit release-profile timeout without requiring direct invocation of
    scripts/run_external_verification.py."""

    def test_release_timeout_flag_propagates_through_the_wrapper(self):
        wrapper = REPO_ROOT / "scripts" / "verify-external.sh"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            result = subprocess.run(
                [
                    BASH_EXECUTABLE,
                    str(wrapper),
                    "--skip-release",
                    "--probe-timeout",
                    "1",
                    "--release-timeout",
                    "4321",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
            self.assertIn("release_timeout=4321", result.stdout)
            self.assertTrue(output.exists())
            bundle = json.loads(output.read_text(encoding="utf-8"))
        release = next(
            item for item in bundle["checks"] if item["scenario"] == "release-profile"
        )
        self.assertEqual("skipped", release["status"])


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
