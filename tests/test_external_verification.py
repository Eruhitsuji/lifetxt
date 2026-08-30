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
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_external_verification.py"
spec = importlib.util.spec_from_file_location("external_verification", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

REPO_ROOT = SCRIPT.parents[1]
BASH_EXECUTABLE = shutil.which("bash")


def _bash_handles_native_windows_paths(bash_executable):
    """Confirm ``bash_executable`` can address a native Windows-style path
    (e.g. ``"D:\\project\\..."``) passed as a positional argument, not only
    run a trivial inline command (#445).

    A trivial ``bash -c "echo ..."`` probe passes for *both* Git Bash/MSYS/
    Cygwin bash *and* WSL's ``bash.exe`` -- but WSL's own filesystem view
    has no concept of a backslash-separated, drive-letter-prefixed path; it
    treats the whole native path string as a single, nonexistent literal
    filename rather than translating it, so a real Windows host with WSL
    bash discoverable on PATH cannot invoke the repository's POSIX wrapper
    by its native Windows checkout path even though the trivial probe
    passed. Git Bash/MSYS/Cygwin bash translate native Windows paths
    transparently and pass this probe. Not meaningful on POSIX hosts, where
    the discovered bash is already a native POSIX bash with no such
    translation concern -- returns True immediately there without spawning
    a subprocess.
    """
    if os.name != "nt":
        return True
    if not bash_executable:
        return False
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    try:
        handle.write("lifetxt-native-path-probe")
        handle.close()
        try:
            probe = subprocess.run(
                [bash_executable, "-c", 'cat "$1"', "bash", handle.name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except OSError:
            return False
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
    return probe.returncode == 0 and "lifetxt-native-path-probe" in probe.stdout


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
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except OSError as exc:
        return f"{BASH_EXECUTABLE} could not be executed: {exc}"
    if probe.returncode != 0 or "lifetxt-bash-probe" not in probe.stdout:
        return (
            f"{BASH_EXECUTABLE} does not behave as a usable POSIX shell here; "
            "run this test on Linux/macOS or with Git Bash ahead of it on PATH."
        )
    if not _bash_handles_native_windows_paths(BASH_EXECUTABLE):
        return (
            f"{BASH_EXECUTABLE} runs trivial inline commands but cannot "
            "address a native Windows-style path passed as an argument "
            "(#445) -- likely WSL's bash.exe, whose own filesystem view "
            "does not translate backslash-separated drive-letter paths. "
            "The POSIX-wrapper integration test needs a shell that can "
            "consume this repository's native Windows checkout path "
            "directly, such as Git Bash/MSYS/Cygwin bash ahead of it on "
            "PATH, or run this test on WSL/Linux/macOS directly."
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


class MacosFilesystemTypeTests(unittest.TestCase):
    """#439: a real macOS run recorded metadata.filesystem_type as "/" --
    the mount path, not a filesystem type/class. The previous
    implementation used `stat -f "%T" root`, which does not reliably yield
    the filesystem type on BSD/macOS stat (whose "-f FORMAT" conversions
    describe *file* attributes, not filesystem attributes, unlike GNU
    coreutils' stat). Replaced with `mount` output parsing, which is
    well-documented and portable across BSD/macOS mount implementations.
    """

    SAMPLE_MOUNT_OUTPUT = (
        "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
        "devfs on /dev (devfs, local, nobrowse)\n"
        "/dev/disk3s5 on /System/Volumes/Data (apfs, local, journaled, nobrowse)\n"
        "map auto_home on /System/Volumes/Data/home (autofs, automounted, nobrowse)\n"
        "/dev/disk4s1 on /Volumes/MyExternalDrive (exfat, local, nodev, nosuid, noowners)\n"
    )

    def test_parse_returns_type_not_the_mount_path(self):
        result = module._parse_macos_mount_type(
            self.SAMPLE_MOUNT_OUTPUT, "/Users/tester/project"
        )
        self.assertEqual("apfs", result)
        self.assertNotEqual("/", result)

    def test_parse_picks_the_longest_matching_mountpoint(self):
        # A nested mount (here, /System/Volumes/Data under the root "/")
        # must win over its shorter parent -- mirroring
        # _linux_filesystem_type's /proc/mounts algorithm.
        result = module._parse_macos_mount_type(
            self.SAMPLE_MOUNT_OUTPUT, "/System/Volumes/Data/checkout/lifetxt"
        )
        self.assertEqual("apfs", result)

    def test_parse_finds_a_non_apfs_external_volume_type(self):
        result = module._parse_macos_mount_type(
            self.SAMPLE_MOUNT_OUTPUT, "/Volumes/MyExternalDrive/work"
        )
        self.assertEqual("exfat", result)

    def test_parse_handles_a_device_name_containing_the_word_on(self):
        # "map auto_home on ..." -- the device name itself is two words;
        # the parser must not require the device to be a single token.
        result = module._parse_macos_mount_type(
            self.SAMPLE_MOUNT_OUTPUT, "/System/Volumes/Data/home/tester"
        )
        self.assertEqual("autofs", result)

    def test_parse_returns_none_when_no_line_matches(self):
        self.assertIsNone(
            module._parse_macos_mount_type("garbage with no mount lines", "/tmp/x")
        )
        self.assertIsNone(module._parse_macos_mount_type("", "/tmp/x"))

    def test_filesystem_type_returns_none_when_mount_binary_is_unavailable(self):
        with mock.patch.object(module.shutil, "which", return_value=None):
            self.assertIsNone(module._macos_filesystem_type("/tmp/x"))

    def test_filesystem_type_returns_none_on_nonzero_exit_not_a_path_value(self):
        with (
            mock.patch.object(module.shutil, "which", return_value="/sbin/mount"),
            mock.patch.object(
                module.subprocess,
                "run",
                return_value=mock.Mock(returncode=1, stdout=""),
            ),
        ):
            result = module._macos_filesystem_type("/tmp/x")
        self.assertIsNone(result)
        self.assertNotEqual("/", result)

    def test_filesystem_type_returns_none_on_subprocess_error(self):
        for side_effect in (
            OSError("mount not executable"),
            subprocess.TimeoutExpired(cmd=["mount"], timeout=10),
        ):
            with (
                mock.patch.object(module.shutil, "which", return_value="/sbin/mount"),
                mock.patch.object(module.subprocess, "run", side_effect=side_effect),
            ):
                self.assertIsNone(module._macos_filesystem_type("/tmp/x"))

    def test_filesystem_type_success_end_to_end_through_subprocess(self):
        with (
            mock.patch.object(module.shutil, "which", return_value="/sbin/mount"),
            mock.patch.object(
                module.subprocess,
                "run",
                return_value=mock.Mock(returncode=0, stdout=self.SAMPLE_MOUNT_OUTPUT),
            ),
            mock.patch.object(module.os.path, "realpath", return_value="/"),
        ):
            result = module._macos_filesystem_type("/")
        self.assertEqual("apfs", result)

    def test_dispatch_routes_macos_to_the_mount_based_detector(self):
        with mock.patch.object(
            module, "_macos_filesystem_type", return_value="apfs"
        ) as detector:
            result = module._filesystem_type("/some/root", "macos")
        self.assertEqual("apfs", result)
        detector.assert_called_once_with("/some/root")

    def test_dispatch_does_not_regress_linux_wsl_or_windows(self):
        # #439 is scoped to macOS only; the other host classes must keep
        # calling their own existing detectors unchanged.
        with mock.patch.object(
            module, "_linux_filesystem_type", return_value="ext4"
        ) as linux_detector:
            self.assertEqual("ext4", module._filesystem_type("/root", "linux"))
            self.assertEqual("ext4", module._filesystem_type("/root", "wsl"))
        self.assertEqual(2, linux_detector.call_count)
        with mock.patch.object(
            module, "_windows_filesystem_type", return_value="NTFS"
        ) as windows_detector:
            result = module._filesystem_type("C:\\root", "windows")
        self.assertEqual("NTFS", result)
        windows_detector.assert_called_once_with("C:\\root")


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

    def test_short_temp_candidate_does_not_match_inside_component(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
            result = redact(r"unclosed file name='C:\Users\alice\AppData\Local\Temp\tmpXXXX\file.txt'")
        self.assertIn(r"<temp>\tmpXXXX\file.txt", result)
        self.assertNotIn(r"<temp>XXXX", result)

    def test_short_temp_candidate_still_matches_true_posix_and_windows_roots(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
            posix_result = redact(r"/tmp/work")
        self.assertEqual(r"<temp>/work", posix_result)

        with mock.patch.object(module.tempfile, "gettempdir", return_value=r"C:\tmp"):
            redact = module.make_redactor(
                repo_root=None, env={"USERPROFILE": r"C:\Users\alice", "USERNAME": "alice"}
            )
            windows_result = redact(r"C:\tmp\work")
        self.assertEqual(r"<temp>\work", windows_result)

    def test_short_temp_persistence_scan_uses_the_same_boundary(self):
        with mock.patch.object(module.tempfile, "gettempdir", return_value="/tmp"):
            candidates = module._categorized_redaction_candidates(
                repo_root=None, env={"HOME": "/home/alice", "USER": "alice"}
            )
        self.assertNotIn(
            "temp",
            module._unredacted_candidate_count(
                r'{"stderr": "C:\\Users\\alice\\AppData\\Local\\Temp\\tmpXXXX"}',
                candidates,
            ),
        )
        self.assertIn(
            "temp",
            module._unredacted_candidate_count(
                r'{"stderr": "/tmp/work"}', candidates
            ),
        )


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

    def test_windows_repr_escaped_backslash_username_only_match_collapses(self):
        # Reopened #438: a real Windows full-profile run found this exact
        # gap in a ResourceWarning message's text, which is a Python
        # repr() of a file object -- repr() escapes each backslash as two
        # literal backslash characters, so the real separator there is
        # "\\\\" (two backslash characters), not "\\" (one). The username
        # lookaround in username_patterns only checks the single adjacent
        # character, so it still matches and the account name is redacted
        # either way, but the structural collapse pattern originally
        # required exactly one separator character and missed the doubled
        # form, leaving "Users\\\\<redacted-user>\\\\AppData\\\\..."
        # unredacted.
        sep = "\\\\"  # two literal backslash characters (repr()-escaped)
        raw = (
            "unclosed file <_io.TextIOWrapper name='C:"
            + sep
            + "Users"
            + sep
            + "bob"
            + sep
            + "AppData"
            + sep
            + "Local"
            + sep
            + "Temp"
            + sep
            + "tmpXXXX"
            + sep
            + "file.txt'>"
        )
        # Mock gettempdir() to a value sharing no substring with "tmp" --
        # temp="/tmp" would otherwise register a "\tmp" backslash-variant
        # path_pattern candidate that coincidentally matches inside the
        # "tmpXXXX" mkdtemp()-style directory name below, which is a real
        # but separate interaction unrelated to what this test covers.
        with mock.patch.object(
            module.tempfile, "gettempdir", return_value="/nonexistent-temp-root"
        ):
            redact = module.make_redactor(
                repo_root=None, env={"HOME": "/home/bob", "USER": "bob"}
            )
            result = redact(raw)
        expected = (
            "unclosed file <_io.TextIOWrapper name='<temp>"
            + sep
            + "tmpXXXX"
            + sep
            + "file.txt'>"
        )
        self.assertEqual(expected, result)
        self.assertNotIn("bob", result)
        self.assertNotIn("<redacted-user>", result)
        self.assertNotIn("AppData", result)

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

    def test_run_command_replaces_undecodable_child_output(self):
        record = module.run_command(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'prefix\\x80suffix')",
            ],
            Path.cwd(),
            lambda value: str(value),
            10,
        )
        self.assertEqual("passed", record["status"])
        self.assertEqual("prefix\ufffdsuffix", record["stdout"])

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


# #453: a grandchild that inherits its parent's stdout/stderr pipe (by not
# redirecting them itself, exactly like run_ci_like.py's own
# `subprocess.check_call(["python", "-m", "unittest", "discover"])` call)
# keeps that pipe open even after the direct parent process is killed, so a
# caller that only kills the immediate process ends up blocked draining
# output until the grandchild exits naturally. `_GRANDCHILD_SLEEP_SECONDS`
# is chosen to comfortably outlast every timeout used below while staying
# short enough that a broken fix does not make the suite hang for long.
_GRANDCHILD_SLEEP_SECONDS = 12


def _parent_with_inheriting_grandchild_script(marker_path):
    """Synthesize a `-c` script spawning a grandchild that inherits the
    parent's own stdout/stderr and records its own PID to `marker_path`."""
    grandchild_code = (
        "import os, sys, time;"
        f"open({str(marker_path)!r}, 'w', encoding='utf-8').write(str(os.getpid()));"
        "print('grandchild-up', flush=True);"
        f"time.sleep({_GRANDCHILD_SLEEP_SECONDS})"
    )
    return (
        "import subprocess, sys;"
        f"gc = subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]);"
        "print('parent-up', flush=True);"
        "gc.wait()"
    )


def _pid_is_alive(pid):
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % pid],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_marker(marker_path, bound_seconds=5):
    deadline = time.monotonic() + bound_seconds
    while time.monotonic() < deadline:
        if marker_path.exists() and marker_path.read_text(encoding="utf-8").strip():
            return True
        time.sleep(0.1)
    return marker_path.exists() and bool(
        marker_path.read_text(encoding="utf-8").strip()
    )


def _wait_until_dead(pid, bound_seconds=5):
    """Poll ``_pid_is_alive(pid)`` until it reports dead or the bound elapses.

    A SIGKILL/taskkill is delivered promptly, but the OS reaping the
    process out of the process table (so `_pid_is_alive` actually reports
    False) is not instantaneous -- reproduced live as a flaky failure on a
    shared, loaded GitHub Actions Linux runner even though the identical
    assertion passed reliably in this repository's own local sandboxes.
    Bounding this to a few seconds still fails loudly on a genuine "the
    process was never actually killed" regression; it only tolerates the
    OS's own brief reap delay under load.
    """
    deadline = time.monotonic() + bound_seconds
    alive = _pid_is_alive(pid)
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = _pid_is_alive(pid)
    return alive


class ProcessTreeKillPlatformDispatchTests(unittest.TestCase):
    """Unit coverage of the per-platform kill strategy, independent of the
    real-process reproduction below -- exercises the POSIX branch even when
    this suite itself runs on Windows."""

    def test_windows_kill_uses_taskkill_with_the_tree_flag(self):
        fake_process = mock.Mock(pid=4321)
        with (
            mock.patch.object(module.os, "name", "nt"),
            mock.patch.object(module.subprocess, "run") as run,
        ):
            module._kill_process_tree(fake_process)
        run.assert_called_once_with(
            ["taskkill", "/F", "/T", "/PID", "4321"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        fake_process.kill.assert_not_called()

    def test_posix_kill_signals_the_whole_process_group(self):
        # os.getpgid/os.killpg/signal.SIGKILL do not exist at all on this
        # module's own os/signal objects when the suite itself runs on
        # Windows, so patching them here needs create=True regardless of
        # which host actually runs the test.
        fake_process = mock.Mock(pid=4321)
        with (
            mock.patch.object(module.os, "name", "posix"),
            mock.patch.object(module.signal, "SIGKILL", 9, create=True),
            mock.patch.object(
                module.os, "getpgid", return_value=4321, create=True
            ) as getpgid,
            mock.patch.object(module.os, "killpg", create=True) as killpg,
        ):
            module._kill_process_tree(fake_process)
            getpgid.assert_called_once_with(4321)
            killpg.assert_called_once_with(4321, module.signal.SIGKILL)
        # The direct handle is also killed defensively, in case the child
        # never actually joined a killable session.
        fake_process.kill.assert_called_once_with()

    def test_posix_kill_tolerates_a_process_group_that_already_exited(self):
        fake_process = mock.Mock(pid=4321)
        with (
            mock.patch.object(module.os, "name", "posix"),
            mock.patch.object(module.signal, "SIGKILL", 9, create=True),
            mock.patch.object(module.os, "getpgid", return_value=4321, create=True),
            mock.patch.object(
                module.os,
                "killpg",
                side_effect=ProcessLookupError,
                create=True,
            ),
        ):
            module._kill_process_tree(fake_process)  # must not raise
        fake_process.kill.assert_called_once_with()

    def test_popen_kwargs_start_a_new_session_on_posix(self):
        with mock.patch.object(module.os, "name", "posix"):
            self.assertEqual(
                module._process_tree_popen_kwargs(), {"start_new_session": True}
            )

    def test_popen_kwargs_are_empty_on_windows(self):
        with mock.patch.object(module.os, "name", "nt"):
            self.assertEqual(module._process_tree_popen_kwargs(), {})


class ProcessTreeTimeoutTests(unittest.TestCase):
    """Real-process reproduction of #453: a grandchild inheriting the pipe
    must not keep the collector blocked past a bounded cleanup window, and
    must actually be terminated, not merely orphaned."""

    def test_killing_only_the_direct_process_leaves_the_grandchild_alive(self):
        # Demonstrates the underlying platform behavior this issue depends
        # on: killing only the immediate process -- exactly what
        # subprocess.run()'s own built-in timeout handling does -- is not
        # enough to free a pipe a grandchild inherited, so a caller must
        # terminate the whole tree instead. This does not call
        # module.run_command() (which already contains the fix); it
        # replicates the pre-fix pattern directly.
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "grandchild.pid"
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _parent_with_inheriting_grandchild_script(marker),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # Isolated into its own session/process group on POSIX --
                # exactly like module.run_command()'s own Popen call --
                # purely so this test's own cleanup (module._kill_process_tree,
                # which calls os.killpg on POSIX) cannot reach outside this
                # synthetic tree. Without this, the synthetic parent shares
                # this test *runner's own* process group (the POSIX default
                # for an unqualified Popen call), so cleanup's os.killpg
                # would signal the test runner itself -- reproduced live via
                # a real Linux container, where it silently killed the whole
                # unittest process before any result could be reported. Does
                # not affect what this test demonstrates: the grandchild
                # still inherits the direct process's own stdout/stderr pipe
                # regardless of which session/process group either is in.
                **module._process_tree_popen_kwargs(),
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=1)
                self.assertTrue(_wait_for_marker(marker), "grandchild never started")
                grandchild_pid = int(marker.read_text(encoding="utf-8"))
                # Kill only the direct process, mirroring what
                # subprocess.run()'s own TimeoutExpired handling does.
                process.kill()
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=1)
                self.assertTrue(
                    _pid_is_alive(grandchild_pid),
                    "expected the grandchild to survive an immediate-parent-only kill",
                )
            finally:
                # Clean up with the real fix regardless of the outcome
                # above, so this test never leaves a lingering process. Use
                # wait(), not communicate(): the output already collected
                # above is enough for the assertions, and wait() reliably
                # clears Popen's own "still running" bookkeeping (avoiding a
                # ResourceWarning at garbage-collection time) without
                # depending on draining a pipe that a slow-to-die grandchild
                # under load could still momentarily hold open.
                module._kill_process_tree(process)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def test_run_command_terminates_the_whole_tree_and_returns_promptly(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "grandchild.pid"
            redact = lambda value: str(value)
            record = module.run_command(
                [
                    sys.executable,
                    "-c",
                    _parent_with_inheriting_grandchild_script(marker),
                ],
                Path.cwd(),
                redact,
                2,
            )
            self.assertEqual(record["status"], "timeout")
            self.assertEqual(record["timeout_seconds"], 2)
            # Returned well before the grandchild's own sleep would have
            # completed naturally -- the collector regained control instead
            # of waiting on the still-open inherited pipe.
            self.assertLess(record["duration_seconds"], _GRANDCHILD_SLEEP_SECONDS - 2)
            self.assertTrue(
                _wait_for_marker(marker, bound_seconds=1),
                "grandchild never started",
            )
            grandchild_pid = int(marker.read_text(encoding="utf-8"))
            self.assertFalse(
                _wait_until_dead(grandchild_pid),
                "grandchild survived process-tree termination",
            )


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
    """#437 (reopened twice): real supported-host runs showed each of two
    successive fixed release-profile timeouts too tight for slower hosts.
    The first fix (7200s -> 14400s) was itself reopened when a subsequent
    real run showed macOS finishing at ~14225s (barely inside the 14400s
    boundary) and native Linux again hitting the collector's timeout while
    still inside the test run, with WSL's own duration varying from ~4959s
    to ~7427s between runs of the same host class."""

    def test_default_release_timeout_has_headroom_over_observed_real_host_durations(
        self,
    ):
        args = module.build_parser().parse_args([])
        self.assertEqual(args.release_timeout, module.DEFAULT_RELEASE_TIMEOUT_SECONDS)
        # Highest confirmed real-host near-miss duration was ~14225s
        # (macOS, on the reopened run). The default must retain real
        # headroom above it, not just nominally exceed it, while still
        # bounding a hung process.
        self.assertGreaterEqual(module.DEFAULT_RELEASE_TIMEOUT_SECONDS, 14225 * 2)
        # Must also strictly exceed the prior (reopened, insufficient)
        # 14400s default -- a regression guard specific to this reopening.
        self.assertGreater(module.DEFAULT_RELEASE_TIMEOUT_SECONDS, 14400)

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


class BashNativeWindowsPathCompatibilityTests(unittest.TestCase):
    """#445: a real Windows full-verification run found the discovered bash
    resolved to WSL's bash.exe, which passes the trivial inline-command
    probe in _bash_skip_reason() but cannot address the repository's native
    Windows checkout path -- causing VerifyExternalShWrapperTests to fail
    with exit 127, a test-portability failure, not a lifetxt runtime
    incompatibility. Covered here with synthetic subprocess results only,
    no real checkout path.
    """

    def test_returns_true_immediately_on_posix_without_probing(self):
        with mock.patch.object(os, "name", "posix"):
            with mock.patch.object(subprocess, "run") as run:
                result = _bash_handles_native_windows_paths("bash")
        self.assertTrue(result)
        run.assert_not_called()

    def test_returns_false_when_no_executable_is_given_on_windows(self):
        with mock.patch.object(os, "name", "nt"):
            self.assertFalse(_bash_handles_native_windows_paths(None))

    def test_returns_true_when_the_shell_translates_the_native_path(self):
        # Mimics Git Bash/MSYS/Cygwin bash: translates the native Windows
        # path transparently and reads the probe file's real content.
        with mock.patch.object(os, "name", "nt"):
            with mock.patch.object(
                subprocess,
                "run",
                return_value=mock.Mock(
                    returncode=0, stdout="lifetxt-native-path-probe"
                ),
            ):
                self.assertTrue(_bash_handles_native_windows_paths("bash"))

    def test_returns_false_when_the_shell_cannot_resolve_the_native_path(self):
        # Mimics the real observed WSL bash.exe failure: the native
        # Windows path is treated as a nonexistent literal filename.
        with mock.patch.object(os, "name", "nt"):
            with mock.patch.object(
                subprocess,
                "run",
                return_value=mock.Mock(returncode=127, stdout=""),
            ):
                self.assertFalse(_bash_handles_native_windows_paths("bash"))

    def test_returns_false_on_a_subprocess_error_rather_than_raising(self):
        with mock.patch.object(os, "name", "nt"):
            with mock.patch.object(subprocess, "run", side_effect=OSError("boom")):
                self.assertFalse(_bash_handles_native_windows_paths("bash"))

    def test_skip_reason_names_the_path_model_problem_not_bash_absence(self):
        # A shell that passes the trivial probe but fails the native-path
        # probe must produce a skip reason that says so explicitly (#445),
        # not one implying bash itself is missing or generally unusable.
        trivial_probe = mock.Mock(returncode=0, stdout="lifetxt-bash-probe\n")
        native_path_probe = mock.Mock(returncode=127, stdout="")
        with (
            mock.patch(f"{__name__}.BASH_EXECUTABLE", "fake-bash"),
            mock.patch.object(os, "name", "nt"),
            mock.patch.object(
                subprocess, "run", side_effect=[trivial_probe, native_path_probe]
            ),
        ):
            reason = _bash_skip_reason()
        self.assertIsNotNone(reason)
        self.assertIn("native Windows-style path", reason)
        self.assertNotIn("was not found on PATH", reason)
        self.assertNotIn("does not behave as a usable POSIX shell", reason)

    def test_skip_reason_is_none_when_both_probes_succeed(self):
        trivial_probe = mock.Mock(returncode=0, stdout="lifetxt-bash-probe\n")
        native_path_probe = mock.Mock(returncode=0, stdout="lifetxt-native-path-probe")
        with (
            mock.patch(f"{__name__}.BASH_EXECUTABLE", "fake-bash"),
            mock.patch.object(os, "name", "nt"),
            mock.patch.object(
                subprocess, "run", side_effect=[trivial_probe, native_path_probe]
            ),
        ):
            reason = _bash_skip_reason()
        self.assertIsNone(reason)


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
                encoding="utf-8",
                errors="replace",
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


class UsernameLeakPatternTests(unittest.TestCase):
    """#443: the persistence-time scan's username matching must agree with
    make_redactor()'s own username_patterns -- the same two bounded
    contexts, not an unconditional substring search."""

    def test_matches_a_labeled_user_field(self):
        pattern = module._username_leak_pattern("alice")
        self.assertTrue(pattern.search("user=alice"))
        self.assertTrue(pattern.search("owner: Alice"))

    def test_matches_a_path_segment_boundary(self):
        pattern = module._username_leak_pattern("alice")
        self.assertTrue(pattern.search("/Users/alice/file"))
        self.assertTrue(pattern.search(r"C:\Users\alice\file"))

    def test_does_not_match_a_coincidental_substring_inside_an_unrelated_word(self):
        pattern = module._username_leak_pattern("an")
        self.assertFalse(pattern.search("handle plan scan"))
        self.assertFalse(pattern.search("banana"))


class PersistenceCategoryLeakScanTests(unittest.TestCase):
    """#443: a real Windows full-profile run refused to persist evidence
    that make_redactor() had already fully sanitized. Root cause: the
    persistence-time scan used an unconditional substring check for every
    candidate, including usernames as short as two characters, while
    make_redactor()'s own username_patterns only redact a username in a
    bounded context (a labeled "user=" field, or a path segment). Across a
    full release profile's large stdout/stderr, a short username
    coincidentally appears as a substring of ordinary words -- a false
    positive, not a true redaction miss.
    """

    def test_false_positive_reproduced_and_fixed_for_a_short_username_in_large_text(
        self,
    ):
        env = {"USERNAME": "an", "USERPROFILE": r"C:\Users\an"}
        redact = module.make_redactor(repo_root=r"C:\repo", env=env)
        large_text = " ".join(["test_handle_plan_scan passed"] * 5000)
        sanitized = redact(large_text)
        # redact() correctly found nothing to redact: "an" never occurs as
        # a real username here, only as a coincidental substring.
        self.assertNotIn("<redacted-user>", sanitized)
        candidates = module._categorized_redaction_candidates(
            repo_root=r"C:\repo", env=env
        )
        hits = module._unredacted_candidate_count(sanitized, candidates)
        self.assertEqual({}, hits)

    def test_write_bundle_succeeds_for_a_sanitized_full_profile_shaped_bundle(self):
        env = {"USERNAME": "an", "USERPROFILE": r"C:\Users\an"}
        redact = module.make_redactor(repo_root=r"C:\repo", env=env)
        large_stdout = "\n".join(
            f"test_case_{i} PASSED handle plan scan" for i in range(20000)
        )
        bundle = {
            "checks": [
                {
                    "scenario": "release-profile",
                    "status": "passed",
                    "stdout": redact(large_stdout),
                    "stderr": "",
                }
            ]
        }
        candidates = module._categorized_redaction_candidates(
            repo_root=r"C:\repo", env=env
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            module.write_bundle(bundle, output, redaction_candidates=candidates)
            self.assertTrue(output.exists())

    def test_genuine_boundary_matched_username_leak_is_still_refused(self):
        env = {"USERNAME": "an", "USERPROFILE": r"C:\Users\an"}
        candidates = module._categorized_redaction_candidates(
            repo_root=r"C:\repo", env=env
        )
        bundle = {"note": "leaked path /Users/an/secret-file.txt"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            with self.assertRaises(RuntimeError) as caught:
                module.write_bundle(bundle, output, redaction_candidates=candidates)
            self.assertIn("username", str(caught.exception))
            self.assertNotIn("/Users/an/", str(caught.exception))
            self.assertFalse(output.exists())

    def test_genuine_repo_leak_is_still_refused_unchanged(self):
        candidates = module._categorized_redaction_candidates(
            repo_root=r"C:\repo", env={"HOME": "/home/alice"}
        )
        bundle = {"note": r"C:\repo\leaked-file.txt"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            with self.assertRaises(RuntimeError) as caught:
                module.write_bundle(bundle, output, redaction_candidates=candidates)
            self.assertIn("repo", str(caught.exception))
            self.assertNotIn(r"C:\repo", str(caught.exception))

    def test_refusal_message_names_categories_not_the_raw_value(self):
        candidates = [(r"C:\Users\tester", "home"), ("an", "username")]
        bundle = {"note": r"leaked C:\Users\tester\path"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            with self.assertRaises(RuntimeError) as caught:
                module.write_bundle(bundle, output, redaction_candidates=candidates)
        message = str(caught.exception)
        self.assertIn("home", message)
        self.assertNotIn("tester", message)

    def test_json_escaped_backslash_categorized_candidate_is_still_detected(self):
        candidates = [(r"C:\Users\tester", "home")]
        bundle = {"note": r"C:\Users\tester\secret-looking-path"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            with self.assertRaises(RuntimeError):
                module.write_bundle(bundle, output, redaction_candidates=candidates)

    def test_backward_compatible_flat_string_candidates_keep_strict_matching(self):
        # A bare string (no category, as every pre-#443 caller passes)
        # keeps the original unconditional substring check -- including for
        # a short value -- since that strictness is relied on elsewhere
        # (#430). Only the new categorized "username" form gets bounded
        # matching.
        bundle = {"note": "word containing an inside plan"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            with self.assertRaises(RuntimeError):
                module.write_bundle(bundle, output, redaction_candidates=["an"])


class ProgressRecorderTests(unittest.TestCase):
    """#443: incrementally-flushed, sanitized progress evidence so an
    interrupted run, a timeout, or a persistence refusal does not discard
    all diagnostic context the way relying solely on the final JSON does.
    """

    def _redact(self, value):
        return module.make_redactor(
            repo_root=r"C:\repo", env={"HOME": "/home/alice", "USER": "alice"}
        )(value)

    def test_record_writes_a_sanitized_jsonl_line_and_a_human_readable_log_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.log"
            jsonl_path = Path(tmp) / "run.progress.jsonl"
            recorder = module.ProgressRecorder(
                log_path, jsonl_path, self._redact, run_id="run-1"
            )
            recorder.record("collector_start", "started")
            recorder.record("release_profile", "passed", exit_code=0, note="fine")

            jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(jsonl_lines))
            first = json.loads(jsonl_lines[0])
            self.assertEqual("collector_start", first["event"])
            self.assertEqual("started", first["status"])
            self.assertEqual("run-1", first["run_id"])
            self.assertIn("timestamp", first)
            second = json.loads(jsonl_lines[1])
            self.assertEqual(0, second["exit_code"])

            log_lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(log_lines))
            self.assertIn("collector_start", log_lines[0])
            self.assertIn("started", log_lines[0])
            self.assertIn("release_profile", log_lines[1])
            self.assertIn("passed", log_lines[1])

    def test_record_sanitizes_every_field_before_writing_never_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.log"
            jsonl_path = Path(tmp) / "run.progress.jsonl"
            recorder = module.ProgressRecorder(
                log_path, jsonl_path, self._redact, run_id="run-1"
            )
            recorder.record(
                "release_profile",
                "failed",
                reason=r"C:\repo\file failed for /home/alice/thing",
                nested={"path": r"C:\repo\nested"},
                items=[r"C:\repo\item-a", "clean"],
            )
            jsonl_text = jsonl_path.read_text(encoding="utf-8")
            log_text = log_path.read_text(encoding="utf-8")
            for raw in (r"C:\repo", "/home/alice"):
                self.assertNotIn(raw, jsonl_text)
                self.assertNotIn(raw, log_text)
            self.assertIn("<repo>", jsonl_text)

    def test_comprehensive_scan_finds_no_raw_repo_home_temp_username_or_secret_value(
        self,
    ):
        env = {
            "HOME": "/home/alice",
            "USER": "alice",
            "MY_API_TOKEN": "super-secret-token-value",
        }
        redact = module.make_redactor(repo_root="/repo/checkout", env=env)
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.log"
            jsonl_path = Path(tmp) / "run.progress.jsonl"
            recorder = module.ProgressRecorder(
                log_path, jsonl_path, redact, run_id="run-1"
            )
            recorder.record(
                "release_profile",
                "failed",
                stdout="/repo/checkout/tests ran as alice with token=super-secret-token-value",
                stderr="/home/alice/.cache trouble user=alice",
            )
            combined = log_path.read_text(encoding="utf-8") + jsonl_path.read_text(
                encoding="utf-8"
            )
            for raw in ("/repo/checkout", "/home/alice", "super-secret-token-value"):
                self.assertNotIn(raw, combined)
            self.assertNotIn("user=alice", combined)

    def test_records_persist_across_calls_without_any_special_close(self):
        # Every record() call flushes and fsyncs independently (#443), so
        # reading the files back after N calls with no explicit recorder
        # shutdown proves durability against an interruption between calls.
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.log"
            jsonl_path = Path(tmp) / "run.progress.jsonl"
            recorder = module.ProgressRecorder(
                log_path, jsonl_path, self._redact, run_id="run-1"
            )
            for i in range(5):
                recorder.record(f"event_{i}", "completed")
            jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(5, len(jsonl_lines))
            for i, line in enumerate(jsonl_lines):
                self.assertEqual(f"event_{i}", json.loads(line)["event"])

    def test_null_progress_recorder_is_a_safe_no_op(self):
        module._NULL_PROGRESS.record("anything", "anything", field="value")

    def test_progress_artifact_paths_share_the_evidence_json_stem(self):
        output = (
            Path("some")
            / "root"
            / ".cache"
            / "external-verification-windows-20260101T000000Z.json"
        )
        log_path, jsonl_path = module._progress_artifact_paths(output)
        self.assertEqual(
            Path("some")
            / "root"
            / ".cache"
            / "external-verification-windows-20260101T000000Z.log",
            log_path,
        )
        self.assertEqual(
            Path("some")
            / "root"
            / ".cache"
            / "external-verification-windows-20260101T000000Z.progress.jsonl",
            jsonl_path,
        )


class MainProgressAndRefusalIntegrationTests(unittest.TestCase):
    """#443 end-to-end wiring. main() always runs against the real
    repository root (skip-release keeps it fast/offline), matching the
    established pattern in ReleaseTimeoutConfigurationTests."""

    def test_skip_release_run_writes_all_three_artifacts_with_expected_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = module.main(
                    ["--skip-release", "--probe-timeout", "1", "--output", str(output)]
                )
            self.assertEqual(0, code)
            log_path, jsonl_path = module._progress_artifact_paths(output)
            self.assertTrue(output.exists())
            self.assertTrue(log_path.exists())
            self.assertTrue(jsonl_path.exists())
            events = [
                json.loads(line)["event"]
                for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            ]
            for expected in (
                "collector_start",
                "host_classification",
                "git_identity",
                "tool_probes",
                "final_evidence_persistence",
                "collector_complete",
            ):
                self.assertIn(expected, events)
            stdout = buffer.getvalue()
            self.assertIn(f"progress_log={log_path}", stdout)
            self.assertIn(f"progress_events={jsonl_path}", stdout)

    def test_final_json_refusal_preserves_progress_artifacts_and_exits_nonzero_without_a_crash(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            log_path, jsonl_path = module._progress_artifact_paths(output)
            buffer = io.StringIO()
            with (
                contextlib.redirect_stdout(buffer),
                mock.patch.object(
                    module,
                    "_categorized_redaction_candidates",
                    return_value=[("schema_version", "repo")],
                ),
            ):
                code = module.main(
                    ["--skip-release", "--probe-timeout", "1", "--output", str(output)]
                )
            self.assertEqual(1, code)
            self.assertFalse(output.exists())
            self.assertTrue(log_path.exists())
            self.assertTrue(jsonl_path.exists())
            events = [
                json.loads(line)
                for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            ]
            refusal = next(
                item
                for item in events
                if item["event"] == "final_evidence_persistence"
                and item["status"] == "refused"
            )
            self.assertIn("repo", refusal["candidate_categories"])
            completion = next(
                item for item in events if item["event"] == "collector_complete"
            )
            self.assertEqual("failed", completion["status"])
            stdout = buffer.getvalue()
            self.assertIn(f"progress_log={log_path}", stdout)
            self.assertIn(f"progress_events={jsonl_path}", stdout)


if __name__ == "__main__":
    unittest.main()
