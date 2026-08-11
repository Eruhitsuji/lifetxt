"""Tests for lifetxt.server_update and the `server-update` CLI command.

Git operations are exercised through a fake injected via
server_update._git_helpers rather than a real git working tree (mirroring
the existing `LifeTxtUpdateCommandCliTests` pattern for `lifetxt update`,
which additionally has live, unmocked verification against a real
disposable clone recorded in the PR/traceability record -- this module's
orchestration logic reuses those exact git helpers unmodified, so that
coverage already applies to the git mechanics themselves). systemctl/pip/
sanity-check/integrity-check/health-check calls are exercised through a
fake `subprocess.run` for the same reason: this test suite is about the
orchestration logic (locking, backup, failure-state handling, hash
verification), not about git or systemd themselves.
"""

import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from lifetxt import cli, server_update


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeGit:
    """Deterministic stand-in for the real git plumbing lifetxt.cli
    exposes, injected via server_update._git_helpers."""

    def __init__(
        self,
        current="aaa111aaa111aaa111aaa111aaa111aaa111aaaa",
        target="bbb222bbb222bbb222bbb222bbb222bbb222bbbb",
        dirty=False,
        detached=False,
        branch="main",
        not_git_repo=False,
        fetch_fails=False,
        merge_fails=False,
        ancestor=False,
        no_release=False,
    ):
        self.current = current
        self.target = target
        self.dirty = dirty
        self.detached = detached
        self.branch = branch
        self.not_git_repo = not_git_repo
        self.fetch_fails = fetch_fails
        self.merge_fails = merge_fails
        self.ancestor = ancestor
        self.no_release = no_release
        self.calls = []

    def install_root(self):
        return "/opt/lifetxt/src"

    def run_git(self, args, cwd=None, timeout=None):
        self.calls.append(list(args))
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            if self.not_git_repo:
                return _FakeCompletedProcess(1, "", "not a git repository")
            return _FakeCompletedProcess(0, "/opt/lifetxt/src\n", "")
        if args[:2] == ["status", "--porcelain"]:
            return _FakeCompletedProcess(0, " M foo\n" if self.dirty else "", "")
        if args[:3] == ["symbolic-ref", "-q", "--short"]:
            if self.detached:
                return _FakeCompletedProcess(1, "", "not a branch")
            return _FakeCompletedProcess(0, self.branch + "\n", "")
        if args[:1] == ["fetch"]:
            if self.fetch_fails:
                return _FakeCompletedProcess(1, "", "fetch failed")
            return _FakeCompletedProcess(0, "", "")
        if args[:2] == ["rev-parse", "HEAD"]:
            return _FakeCompletedProcess(0, self.current + "\n", "")
        if args[:2] == ["rev-parse", "FETCH_HEAD"]:
            return _FakeCompletedProcess(0, self.target + "\n", "")
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return _FakeCompletedProcess(0 if self.ancestor else 1, "", "")
        if args[:2] == ["merge", "--ff-only"]:
            if self.merge_fails:
                return _FakeCompletedProcess(1, "", "not a fast-forward")
            self.current = self.target
            return _FakeCompletedProcess(0, "", "")
        raise AssertionError("unexpected git args: %r" % (args,))

    def reject_option_like_git_arg(self, value, label):
        if str(value or "").startswith("-"):
            raise ValueError("Refusing %s %r" % (label, value))
        return value

    def git_commit_summary(self, repo_root, current, target, timeout):
        return (["%s one commit" % target[:7]], 1)

    def github_latest_release_or_tag(self, repo, timeout=10):
        if self.no_release:
            return (None, None, None)
        return ("v1.2.3", "release", "https://example.invalid/release")

    def helpers(self):
        return (
            self.install_root,
            self.run_git,
            self.reject_option_like_git_arg,
            self.git_commit_summary,
            self.github_latest_release_or_tag,
        )


def _patch_git(fake):
    return mock.patch.object(server_update, "_git_helpers", fake.helpers)


def _infer_check_name(argv_tail):
    if argv_tail[:1] == ["check"]:
        return "check"
    if argv_tail[:2] == ["workspace", "validate"]:
        return "workspace_validate"
    if argv_tail[:1] == ["ids"]:
        return "ids"
    if argv_tail[:2] == ["ticket", "validate-history"]:
        return "ticket_validate_history"
    raise AssertionError("unrecognized integrity-check argv: %r" % (argv_tail,))


class _FakeSubprocess:
    """Stand-in for subprocess.run covering systemctl/pip/sanity/integrity."""

    def __init__(
        self,
        service_failures=None,
        pip_fails=False,
        sanity_fails=False,
        check_failures=None,
    ):
        self.service_failures = service_failures or set()
        self.pip_fails = pip_fails
        self.sanity_fails = sanity_fails
        self.check_failures = check_failures or set()
        self.calls = []

    def run(self, cmd, cwd=None, timeout=None, **kwargs):
        self.calls.append(list(cmd))
        if cmd[0] == "systemctl":
            action, unit = cmd[1], cmd[2]
            if (action, unit) in self.service_failures:
                return _FakeCompletedProcess(1, "", "failed to %s %s" % (action, unit))
            return _FakeCompletedProcess(0, "", "")
        if len(cmd) >= 3 and cmd[1] == "-m" and cmd[2] == "pip":
            if self.pip_fails:
                return _FakeCompletedProcess(1, "", "pip install failed")
            return _FakeCompletedProcess(0, "installed", "")
        if len(cmd) >= 2 and cmd[1] == "-c":
            if self.sanity_fails:
                return _FakeCompletedProcess(1, "", "ImportError")
            return _FakeCompletedProcess(0, "", "")
        if len(cmd) >= 3 and cmd[1] == "-m" and cmd[2] == "lifetxt":
            name = _infer_check_name(cmd[3:])
            if name in self.check_failures:
                return _FakeCompletedProcess(1, "", "%s failed" % name)
            return _FakeCompletedProcess(0, "%s ok" % name, "")
        raise AssertionError("unexpected subprocess cmd: %r" % (cmd,))


def _patch_subprocess(fake):
    return mock.patch.object(server_update.subprocess, "run", fake.run)


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, data):
        path = os.path.join(self.tmp, "server-update.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_minimal_config_fills_defaults(self):
        path = self._write({"python": "/opt/lifetxt/venv/bin/python"})
        config = server_update.load_config(path)
        self.assertEqual("/opt/lifetxt/venv/bin/python", config["python"])
        self.assertEqual("origin", config["remote"])
        self.assertEqual("systemctl", config["service_manager"])
        self.assertEqual(["check"], config["integrity_checks"])

    def test_missing_python_key_is_rejected(self):
        path = self._write({})
        with self.assertRaises(server_update.ServerUpdateError) as ctx:
            server_update.load_config(path)
        self.assertEqual("load_config", ctx.exception.step)
        self.assertIn("python", str(ctx.exception))

    def test_invalid_json_is_rejected(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertRaises(server_update.ServerUpdateError):
            server_update.load_config(path)

    def test_non_object_json_is_rejected(self):
        path = self._write_raw("[1, 2, 3]")
        with self.assertRaises(server_update.ServerUpdateError):
            server_update.load_config(path)

    def _write_raw(self, text):
        path = os.path.join(self.tmp, "raw.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_unknown_integrity_check_is_rejected(self):
        path = self._write(
            {"python": "python3", "integrity_checks": ["check", "bogus"]}
        )
        with self.assertRaises(server_update.ServerUpdateError) as ctx:
            server_update.load_config(path)
        self.assertIn("bogus", str(ctx.exception))

    def test_invalid_service_manager_is_rejected(self):
        path = self._write({"python": "python3", "service_manager": "docker"})
        with self.assertRaises(server_update.ServerUpdateError):
            server_update.load_config(path)


class HashAndBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_hash_paths_hashes_existing_and_nones_missing(self):
        present = os.path.join(self.tmp, "life.txt")
        with open(present, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Buy_Milk\n")
        missing = os.path.join(self.tmp, "does-not-exist.txt")

        hashes = server_update.hash_paths([present, missing])

        self.assertIsNotNone(hashes[present])
        self.assertEqual(64, len(hashes[present]))
        self.assertIsNone(hashes[missing])

    def test_hash_paths_changes_when_content_changes(self):
        path = os.path.join(self.tmp, "life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("original")
        before = server_update.hash_paths([path])[path]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("changed")
        after = server_update.hash_paths([path])[path]
        self.assertNotEqual(before, after)

    def test_create_backup_copies_existing_files_and_skips_missing(self):
        present = os.path.join(self.tmp, "life.txt")
        with open(present, "w", encoding="utf-8") as handle:
            handle.write("data")
        missing = os.path.join(self.tmp, "gone.txt")
        backup_dir = os.path.join(self.tmp, "backups")

        destination = server_update.create_backup(
            [present, missing], backup_dir, "20260101T000000Z"
        )

        self.assertTrue(os.path.isdir(destination))
        copied = os.listdir(destination)
        self.assertEqual(1, len(copied))
        with open(os.path.join(destination, copied[0]), encoding="utf-8") as handle:
            self.assertEqual("data", handle.read())

    def test_create_backup_without_backup_dir_is_a_no_op(self):
        self.assertIsNone(server_update.create_backup(["/tmp/x"], None, "ts"))


class UpdateLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_no_path_is_a_no_op(self):
        lock = server_update.UpdateLock(None)
        lock.acquire()
        lock.release()  # must not raise

    def test_acquire_creates_and_release_removes_the_lock_file(self):
        path = os.path.join(self.tmp, "server-update.lock")
        lock = server_update.UpdateLock(path)
        lock.acquire()
        self.assertTrue(os.path.exists(path))
        lock.release()
        self.assertFalse(os.path.exists(path))

    def test_double_acquire_is_refused(self):
        path = os.path.join(self.tmp, "server-update.lock")
        first = server_update.UpdateLock(path)
        first.acquire()
        second = server_update.UpdateLock(path)
        with self.assertRaises(server_update.ServerUpdateError) as ctx:
            second.acquire()
        self.assertEqual("acquire_lock", ctx.exception.step)
        first.release()


class CheckHealthTests(unittest.TestCase):
    def test_no_url_returns_none(self):
        self.assertIsNone(server_update.check_health(None, 5))

    def test_success_reports_ok(self):
        response = mock.MagicMock()
        response.read.return_value = b'{"ok": true}'
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch("urllib.request.urlopen", return_value=response):
            result = server_update.check_health("http://127.0.0.1:8765/api/health", 5)
        self.assertTrue(result["ok"])
        self.assertEqual(200, result["status_code"])

    def test_http_error_reports_failure(self):
        from urllib.error import HTTPError

        def _raise(*_args, **_kwargs):
            raise HTTPError("http://x", 503, "Service Unavailable", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=_raise):
            result = server_update.check_health("http://127.0.0.1:8765/api/health", 5)
        self.assertFalse(result["ok"])
        self.assertIn("503", result["error"])


class RunServerUpdateDryRunTests(unittest.TestCase):
    def test_dry_run_reports_pending_update_without_mutating_anything(self):
        git = _FakeGit()
        sub = _FakeSubprocess()
        config = dict(
            server_update.DEFAULT_CONFIG,
            python="python3",
            services=["lifetxt.service"],
            backup_paths=["/srv/lifetxt/life.txt"],
            backup_dir="/srv/lifetxt/backups",
            lock_path="/srv/lifetxt/server-update.lock",
        )
        with _patch_git(git), _patch_subprocess(sub):
            report = server_update.run_server_update(config, yes=False)

        self.assertEqual("update_available_dry_run", report["status"])
        self.assertEqual([], sub.calls)  # no systemctl/pip/health calls at all
        self.assertNotIn("backup_dir", report)
        self.assertEqual(["lifetxt.service"], report["would_stop_services"])

    def test_up_to_date_short_circuits(self):
        git = _FakeGit(current="same", target="same")
        config = dict(server_update.DEFAULT_CONFIG, python="python3")
        with _patch_git(git):
            report = server_update.run_server_update(config, yes=False)
        self.assertEqual("up_to_date", report["status"])

    def test_target_behind_current_is_up_to_date(self):
        git = _FakeGit(ancestor=True)
        config = dict(server_update.DEFAULT_CONFIG, python="python3")
        with _patch_git(git):
            report = server_update.run_server_update(config, yes=False)
        self.assertEqual("up_to_date", report["status"])

    def test_no_ref_and_no_release_found_fails_loudly(self):
        git = _FakeGit(no_release=True)
        config = dict(server_update.DEFAULT_CONFIG, python="python3")
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(config, yes=False)
        self.assertEqual("preflight", ctx.exception.step)


class RunServerUpdatePreflightTests(unittest.TestCase):
    def _config(self, **overrides):
        config = dict(server_update.DEFAULT_CONFIG, python="python3")
        config.update(overrides)
        return config

    def test_dirty_working_tree_is_refused(self):
        git = _FakeGit(dirty=True)
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        self.assertEqual("preflight", ctx.exception.step)

    def test_detached_head_is_refused(self):
        git = _FakeGit(detached=True)
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=False)
        self.assertEqual("preflight", ctx.exception.step)

    def test_non_git_install_is_refused(self):
        git = _FakeGit(not_git_repo=True)
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=False)
        self.assertEqual("preflight", ctx.exception.step)

    def test_branch_mismatch_is_refused(self):
        git = _FakeGit(branch="feature")
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(branch="main"), yes=False)
        self.assertEqual("preflight", ctx.exception.step)

    def test_fetch_failure_is_refused(self):
        git = _FakeGit(fetch_fails=True)
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=False)
        self.assertEqual("fetch", ctx.exception.step)


class RunServerUpdateApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.life_txt = os.path.join(self.tmp, "life.txt")
        with open(self.life_txt, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Buy_Milk\n")
        self.backup_dir = os.path.join(self.tmp, "backups")
        self.lock_path = os.path.join(self.tmp, "server-update.lock")

    def _config(self, **overrides):
        config = dict(
            server_update.DEFAULT_CONFIG,
            python="python3",
            services=["lifetxt.service"],
            backup_paths=[self.life_txt],
            backup_dir=self.backup_dir,
            lock_path=self.lock_path,
            life_txt_path=self.life_txt,
            integrity_checks=["check", "ids"],
            health_url="http://127.0.0.1:8765/api/health",
        )
        config.update(overrides)
        return config

    def test_successful_update_backs_up_stops_updates_restarts_and_checks_health(self):
        git = _FakeGit()
        sub = _FakeSubprocess()
        response = mock.MagicMock()
        response.read.return_value = b"ok"
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with (
            _patch_git(git),
            _patch_subprocess(sub),
            mock.patch("urllib.request.urlopen", return_value=response),
        ):
            report = server_update.run_server_update(self._config(), yes=True)

        self.assertEqual("updated", report["status"])
        self.assertTrue(os.path.isdir(report["backup_dir"]))
        self.assertEqual(["lifetxt.service"], report["services_stopped"])
        self.assertEqual(["lifetxt.service"], report["services_restarted"])
        self.assertTrue(report["integrity_checks"]["check"]["ok"])
        self.assertTrue(report["integrity_checks"]["ids"]["ok"])
        self.assertTrue(report["health_check"]["ok"])
        self.assertFalse(os.path.exists(self.lock_path))
        self.assertEqual(["systemctl", "stop", "lifetxt.service"], sub.calls[0])
        self.assertEqual(["systemctl", "start", "lifetxt.service"], sub.calls[-1])

    def test_service_manager_none_never_calls_systemctl(self):
        git = _FakeGit()
        sub = _FakeSubprocess()
        with (
            _patch_git(git),
            _patch_subprocess(sub),
            mock.patch("urllib.request.urlopen") as urlopen_mock,
        ):
            urlopen_mock.side_effect = AssertionError("health url unset")
            report = server_update.run_server_update(
                self._config(
                    service_manager="none",
                    services=["lifetxt.service"],
                    health_url=None,
                ),
                yes=True,
            )
        self.assertEqual("updated", report["status"])
        self.assertFalse(any(call[0] == "systemctl" for call in sub.calls))

    def test_dirty_tree_via_yes_leaves_no_lock_behind(self):
        git = _FakeGit(dirty=True)
        with _patch_git(git):
            with self.assertRaises(server_update.ServerUpdateError):
                server_update.run_server_update(self._config(), yes=True)
        self.assertFalse(os.path.exists(self.lock_path))

    def test_second_concurrent_run_is_refused_by_the_lock(self):
        lock = server_update.UpdateLock(self.lock_path)
        lock.acquire()
        try:
            git = _FakeGit()
            with _patch_git(git):
                with self.assertRaises(server_update.ServerUpdateError) as ctx:
                    server_update.run_server_update(self._config(), yes=True)
            self.assertEqual("acquire_lock", ctx.exception.step)
        finally:
            lock.release()

    def test_service_stop_failure_restarts_already_stopped_services_and_leaves_code_untouched(
        self,
    ):
        git = _FakeGit()
        sub = _FakeSubprocess(service_failures={("stop", "b.service")})
        config = self._config(services=["a.service", "b.service"])

        with _patch_git(git), _patch_subprocess(sub):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(config, yes=True)

        self.assertEqual("failed_before_code_update", ctx.exception.report["status"])
        # a.service was stopped before b.service failed, then restarted.
        stop_calls = [c for c in sub.calls if c[:2] == ["systemctl", "stop"]]
        start_calls = [c for c in sub.calls if c[:2] == ["systemctl", "start"]]
        self.assertEqual(
            [["systemctl", "stop", "a.service"], ["systemctl", "stop", "b.service"]],
            stop_calls,
        )
        self.assertEqual([["systemctl", "start", "a.service"]], start_calls)
        self.assertEqual(
            [], git.calls and [c for c in git.calls if c[:2] == ["merge", "--ff-only"]]
        )
        self.assertFalse(os.path.exists(self.lock_path))

    def test_merge_failure_restarts_stopped_services_and_reports_before_code_update(
        self,
    ):
        git = _FakeGit(merge_fails=True)
        sub = _FakeSubprocess()
        with _patch_git(git), _patch_subprocess(sub):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        self.assertEqual("failed_before_code_update", ctx.exception.report["status"])
        start_calls = [c for c in sub.calls if c[:2] == ["systemctl", "start"]]
        self.assertEqual([["systemctl", "start", "lifetxt.service"]], start_calls)

    def test_pip_install_failure_leaves_services_stopped(self):
        git = _FakeGit()
        sub = _FakeSubprocess(pip_fails=True)
        with _patch_git(git), _patch_subprocess(sub):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        report = ctx.exception.report
        self.assertEqual("failed_after_code_update", report["status"])
        start_calls = [c for c in sub.calls if c[:2] == ["systemctl", "start"]]
        self.assertEqual([], start_calls)
        self.assertIn(report["backup_dir"], report["message"])

    def test_sanity_import_failure_leaves_services_stopped(self):
        git = _FakeGit()
        sub = _FakeSubprocess(sanity_fails=True)
        with _patch_git(git), _patch_subprocess(sub):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        self.assertEqual("failed_after_code_update", ctx.exception.report["status"])

    def test_integrity_check_failure_leaves_services_stopped_and_reports_per_check_results(
        self,
    ):
        git = _FakeGit()
        sub = _FakeSubprocess(check_failures={"ids"})
        with _patch_git(git), _patch_subprocess(sub):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        report = ctx.exception.report
        self.assertEqual("failed_after_code_update", report["status"])
        self.assertTrue(report["integrity_checks"]["check"]["ok"])
        self.assertFalse(report["integrity_checks"]["ids"]["ok"])
        start_calls = [c for c in sub.calls if c[:2] == ["systemctl", "start"]]
        self.assertEqual([], start_calls)

    def test_data_hash_change_during_update_fails_loudly_without_restarting(self):
        git = _FakeGit()
        sub = _FakeSubprocess()
        real_run = sub.run

        def mutate_then_run(cmd, cwd=None, timeout=None, **kwargs):
            # Simulate the file changing between the pre- and post-update
            # hash snapshots -- exactly the defect class this check exists
            # to catch.
            if len(cmd) >= 3 and cmd[1] == "-m" and cmd[2] == "pip":
                with open(self.life_txt, "a", encoding="utf-8") as handle:
                    handle.write("[ ] T Unexpected_Write\n")
            return real_run(cmd, cwd=cwd, timeout=timeout, **kwargs)

        with (
            _patch_git(git),
            mock.patch.object(server_update.subprocess, "run", mutate_then_run),
        ):
            with self.assertRaises(server_update.ServerUpdateError) as ctx:
                server_update.run_server_update(self._config(), yes=True)
        self.assertEqual("failed_after_code_update", ctx.exception.report["status"])
        self.assertEqual("hash_verification", ctx.exception.step)

    def test_restart_failure_after_validation_is_reported_but_does_not_raise(self):
        git = _FakeGit()
        sub = _FakeSubprocess(service_failures={("start", "lifetxt.service")})
        with (
            _patch_git(git),
            _patch_subprocess(sub),
            mock.patch("urllib.request.urlopen") as urlopen_mock,
        ):
            urlopen_mock.side_effect = AssertionError("should not be reached")
            report = server_update.run_server_update(
                self._config(health_url=None), yes=True
            )
        self.assertEqual("validated_restart_incomplete", report["status"])
        self.assertIn("lifetxt.service", report["service_restart_failures"])

    def test_health_check_failure_after_restart_is_reported_but_does_not_raise(self):
        git = _FakeGit()
        sub = _FakeSubprocess()

        def _raise(*_args, **_kwargs):
            from urllib.error import URLError

            raise URLError("connection refused")

        with (
            _patch_git(git),
            _patch_subprocess(sub),
            mock.patch("urllib.request.urlopen", side_effect=_raise),
        ):
            report = server_update.run_server_update(self._config(), yes=True)
        self.assertEqual("validated_health_check_failed", report["status"])
        self.assertFalse(os.path.exists(self.lock_path))


class CommandServerUpdateCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _config_path(self, data):
        path = os.path.join(self.tmp, "server-update.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_missing_server_config_flag_raises_value_error(self):
        args = argparse.Namespace(server_config=None, yes=False, format="text")
        with self.assertRaises(ValueError):
            cli.command_server_update(args)

    def test_invalid_config_file_is_reported_and_exits_nonzero(self):
        path = self._config_path({})  # missing required "python" key
        args = argparse.Namespace(server_config=path, yes=False, format="json")
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = cli.command_server_update(args)
        self.assertEqual(1, code)
        payload = json.loads(buf.getvalue())
        self.assertEqual("failed", payload["status"])
        self.assertEqual("load_config", payload["step"])

    def test_successful_dry_run_exits_zero(self):
        path = self._config_path({"python": "python3"})
        args = argparse.Namespace(server_config=path, yes=False, format="json")
        git = _FakeGit()
        buf = io.StringIO()
        with _patch_git(git), mock.patch("sys.stdout", buf):
            code = cli.command_server_update(args)
        self.assertEqual(0, code)
        payload = json.loads(buf.getvalue())
        self.assertEqual("update_available_dry_run", payload["status"])

    def test_server_update_is_registered_on_the_argument_parser(self):
        parser = cli.build_parser()
        args = parser.parse_args(
            ["server-update", "--server-config", "/tmp/does-not-matter.json"]
        )
        self.assertIs(cli.command_server_update, args.func)
        self.assertFalse(args.yes)


if __name__ == "__main__":
    unittest.main()
