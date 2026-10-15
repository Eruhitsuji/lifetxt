"""Actions API identity, pagination, expiry and ZIP trust-boundary faults."""

import copy
import hashlib
import io
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_actions as actions  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


class FakeActions:
    """Synthetic trusted API, not evidence of a real Actions run."""

    def __init__(self, candidate):
        self.candidate = candidate
        identity = {
            "repository": {"full_name": actions.REPOSITORY},
            "head_repository": {"full_name": actions.REPOSITORY},
            "head_branch": "main",
        }
        self.run = {
            **identity,
            "id": candidate["run_id"],
            "run_attempt": candidate["run_attempt"],
            "head_sha": candidate["controller_sha"],
            "path": actions.WORKFLOW,
            "event": "workflow_dispatch",
            "status": "in_progress",
            "referenced_workflows": [
                {
                    "path": actions.REPOSITORY
                    + "/.github/workflows/release-preflight-%s.yml@refs/heads/main"
                    % family,
                    "sha": candidate["controller_sha"],
                }
                for family in actions.FAMILIES
            ],
        }
        self.ci = {
            **identity,
            "id": 900,
            "run_attempt": 1,
            "head_sha": candidate["source_sha"],
            "path": ".github/workflows/ci.yml",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        }
        self.gate = {
            "id": 901,
            "run_id": 900,
            "name": "Main compatibility gate",
            "head_sha": candidate["source_sha"],
            "status": "completed",
            "conclusion": "success",
        }
        self.jobs, self.artifacts, self.archives = [], [], {}
        for index, target in enumerate(proof.TARGETS):
            family = target.split("-", 1)[0]
            self.jobs.append(
                {
                    "id": 1000 + index,
                    "run_id": candidate["run_id"],
                    "name": actions.TITLES[family]
                    + " / "
                    + ("core" if family == "core" else "Preflight (%s)" % target),
                    "head_sha": candidate["controller_sha"],
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2020-01-01T00:00:00Z",
                    "completed_at": "2020-01-01T00:20:00Z",
                    "steps": [
                        {"name": name, "status": "completed", "conclusion": "success"}
                        for name in actions.STEPS[family]
                    ],
                }
            )
            for kind in ("payload", "proof"):
                self.artifacts.append(
                    {
                        "id": 2000 + len(self.artifacts),
                        "name": actions.artifact_name(candidate, target, kind),
                        "size_in_bytes": 1,
                        "digest": "sha256:" + "e" * 64,
                        "expired": False,
                        "created_at": "2020-01-01T00:10:00Z",
                        "expires_at": "2099-01-01T00:00:00Z",
                        "workflow_run": {
                            "id": candidate["run_id"],
                            "head_sha": candidate["controller_sha"],
                            "head_branch": "main",
                            "repository_id": 1,
                            "head_repository_id": 1,
                        },
                    }
                )

    def get(self, path):
        return copy.deepcopy(self.ci if path == "/actions/runs/900" else self.run)

    def listing(self, path, key):
        return copy.deepcopy(
            self.artifacts
            if key == "artifacts"
            else [self.gate]
            if "/900/" in path
            else self.jobs
        )

    def pack(self, row, root):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.iterdir()):
                archive.write(path, path.name)
        data = stream.getvalue()
        self.archives[row["id"]] = data
        row.update(
            size_in_bytes=len(data), digest="sha256:" + hashlib.sha256(data).hexdigest()
        )

    def download(self, row, destination):
        data = self.archives[row["id"]]
        proof.require(
            len(data) == row["size_in_bytes"]
            and "sha256:" + hashlib.sha256(data).hexdigest() == row["digest"],
            "fixture archive tampered",
        )
        destination.write_bytes(data)


class PreflightActionsTests(unittest.TestCase):
    def setUp(self):
        self.candidate = proof.candidate(
            actions.REPOSITORY, "1.0.4.2", "a" * 40, "b" * 40, 123, 1
        )
        self.api = FakeActions(self.candidate)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_all_api_identities_and_main_gate(self):
        ci = actions.main_ci(self.api, self.candidate["source_sha"], 900)
        self.assertEqual(ci["gate_job_id"], 901)
        actions.current_run(self.api, self.candidate)
        jobs = actions.producer_jobs(self.api, self.candidate)
        self.assertEqual(
            len(actions.select_artifacts(self.api, self.candidate, jobs)), 26
        )

    def test_main_ci_fork_source_ref_event_conclusion_and_gate_faults(self):
        for field, value in (
            ("head_sha", "c" * 40),
            ("head_branch", "other"),
            ("event", "pull_request"),
            ("path", ".github/workflows/other.yml"),
            ("conclusion", "failure"),
            ("status", "in_progress"),
            ("head_repository", {"full_name": "fork/lifetxt"}),
        ):
            api = copy.deepcopy(self.api)
            api.ci[field] = value
            with self.assertRaises(ValueError):
                actions.main_ci(api, self.candidate["source_sha"], 900)
        self.api.gate["conclusion"] = "skipped"
        with self.assertRaises(ValueError):
            actions.main_ci(self.api, self.candidate["source_sha"], 900)

    def test_current_run_attempt_and_reusable_sha_must_match(self):
        for field, value in (
            ("run_attempt", 2),
            ("head_sha", "c" * 40),
            ("status", "completed"),
            ("referenced_workflows", []),
        ):
            api = copy.deepcopy(self.api)
            api.run[field] = value
            with self.assertRaises(ValueError):
                actions.current_run(api, self.candidate)
        self.api.run["referenced_workflows"][0]["sha"] = "c" * 40
        with self.assertRaises(ValueError):
            actions.current_run(self.api, self.candidate)

    def test_failed_skipped_missing_duplicate_producer_or_step(self):
        for fault in ("failed", "skipped", "missing", "duplicate", "step"):
            api = copy.deepcopy(self.api)
            if fault == "missing":
                api.jobs.pop()
            elif fault == "duplicate":
                api.jobs.append(copy.deepcopy(api.jobs[0]))
            elif fault == "step":
                api.jobs[0]["steps"][0]["conclusion"] = "skipped"
            else:
                api.jobs[0]["conclusion"] = fault
            with self.assertRaises(ValueError):
                actions.producer_jobs(api, self.candidate)

    def test_expiry_stale_attempt_foreign_run_digest_missing_duplicate(self):
        for field, value in (
            ("expired", True),
            ("expires_at", "2020-01-01T00:00:00Z"),
            ("created_at", "2019-01-01T00:00:00Z"),
            ("size_in_bytes", 0),
            ("digest", None),
            (
                "workflow_run",
                {
                    "id": 124,
                    "head_sha": "b" * 40,
                    "head_branch": "main",
                    "repository_id": 1,
                    "head_repository_id": 2,
                },
            ),
        ):
            api = copy.deepcopy(self.api)
            api.artifacts[0][field] = value
            with self.assertRaises(ValueError):
                actions.select_artifacts(
                    api, self.candidate, actions.producer_jobs(api, self.candidate)
                )
        for mode in ("missing", "duplicate", "id-reuse"):
            api = copy.deepcopy(self.api)
            if mode == "missing":
                api.artifacts.pop()
            elif mode == "duplicate":
                api.artifacts.append(copy.deepcopy(api.artifacts[0]))
            else:
                api.artifacts[1]["id"] = api.artifacts[0]["id"]
            with self.assertRaises(ValueError):
                actions.select_artifacts(
                    api, self.candidate, actions.producer_jobs(api, self.candidate)
                )

    def test_api_lists_all_pages_and_rejects_partial_or_duplicate_pages(self):
        api = actions.Actions()
        result = subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                [
                    {"total_count": 2, "jobs": [{"id": 1}]},
                    {"total_count": 2, "jobs": [{"id": 2}]},
                ]
            ),
        )
        with patch.object(actions.subprocess, "run", return_value=result) as run:
            self.assertEqual(len(api.listing("/actions/runs/123/jobs", "jobs")), 2)
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])
        for rows in (
            [{"total_count": 2, "jobs": [{"id": 1}]}],
            [{"total_count": 2, "jobs": [{"id": 1}, {"id": 1}]}],
        ):
            result.stdout = json.dumps(rows)
            with (
                patch.object(actions.subprocess, "run", return_value=result),
                self.assertRaises(ValueError),
            ):
                api.listing("/actions/runs/123/jobs", "jobs")

    def test_authenticated_download_verifies_zip_size_and_digest(self):
        row = {
            "id": 7,
            "size_in_bytes": 4,
            "digest": "sha256:" + hashlib.sha256(b"data").hexdigest(),
        }

        def download(command, **kwargs):
            kwargs["stdout"].write(b"data")

        with patch.object(actions.subprocess, "run", side_effect=download):
            actions.Actions().download(row, self.root / "zip")
            row["digest"] = "sha256:" + "a" * 64
            with self.assertRaises(ValueError):
                actions.Actions().download(row, self.root / "bad")

    def test_safe_zip_and_path_link_alias_size_faults(self):
        for index, names in enumerate(
            (
                ["ok.json"],
                ["../escape"],
                ["/absolute"],
                ["a\\b"],
                ["dir/file"],
                ["CON.txt"],
                ["one.json", "ONE.json"],
                ["link"],
            )
        ):
            archive = self.root / (str(index) + ".zip")
            with zipfile.ZipFile(archive, "w") as stream:
                for name in names:
                    info = zipfile.ZipInfo(name)
                    if name == "link":
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    stream.writestr(info, b"data")
            if index == 0:
                actions.extract_zip(archive, self.root / "valid")
                self.assertEqual((self.root / "valid/ok.json").read_bytes(), b"data")
                with self.assertRaises(ValueError):
                    actions.extract_zip(archive, self.root / "oversized", max_bytes=3)
            else:
                with self.assertRaises(ValueError):
                    actions.extract_zip(archive, self.root / ("out" + str(index)))
        self.assertFalse((self.root / "escape").exists())

    def test_required_step_names_match_actual_producer_workflows(self):
        for family in actions.FAMILIES:
            path = ROOT / (".github/workflows/release-preflight-%s.yml" % family)
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            names = {step.get("name") for step in workflow["jobs"][family]["steps"]}
            self.assertTrue(set(actions.STEPS[family]) <= names, family)


if __name__ == "__main__":
    unittest.main()
