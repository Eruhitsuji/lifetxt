"""Execute the workflow gate and GitHub scripts against isolated API fixtures."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
JOBS = yaml.load(
    (ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
)["jobs"]


class RecoveryGateTests(unittest.TestCase):
    def test_web_lane_cannot_silently_skip_quick_web_guarantees(self):
        install = next(
            step
            for step in JOBS["test"]["steps"]
            if step["name"].startswith("Install package")
        )
        self.assertIn("assert WEB_AVAILABLE", install["run"])
        self.assertEqual("write", JOBS["ci-visibility"]["permissions"]["issues"])

    def test_selective_jobs_remain_required_only_when_selected(self):
        for job, flag in [
            ("no-web-extras", "run-no-web"),
            ("coverage-baseline", "run-coverage"),
        ]:
            condition = JOBS[job]["if"]
            self.assertIn("github.event_name != 'pull_request' ||", condition)
            self.assertIn(flag, condition)
        self.assertEqual(
            "${{ github.event_name == 'pull_request' }}", JOBS["main-health"]["if"]
        )

    def test_aggregate_rejects_failed_cancelled_and_unexpected_skipped_checks(self):
        script = (
            JOBS["pr-gate"]["steps"][0]["run"]
            .split("python - <<'PY'\n", 1)[1]
            .rsplit("\nPY", 1)[0]
        )
        defaults = dict(
            TEST_RESULT="success",
            TYPE_RESULT="success",
            DOCS_RESULT="success",
            TRACEABILITY_RESULT="success",
            HEALTH_RESULT="success",
            PATH_CATEGORY="python-core",
            NO_WEB_RESULT="success",
            COVERAGE_RESULT="skipped",
            NO_WEB_SELECTED="true",
            COVERAGE_SELECTED="false",
        )
        for changes, expected in [
            ({}, 0),
            ({"NO_WEB_RESULT": "failure"}, 1),
            ({"NO_WEB_RESULT": "cancelled"}, 1),
            ({"NO_WEB_RESULT": "skipped"}, 1),
            ({"COVERAGE_SELECTED": "true"}, 1),
            ({"COVERAGE_SELECTED": "true", "COVERAGE_RESULT": "success"}, 0),
            (
                {
                    "PATH_CATEGORY": "docs-only",
                    "TEST_RESULT": "skipped",
                    "TYPE_RESULT": "skipped",
                    "NO_WEB_SELECTED": "false",
                    "NO_WEB_RESULT": "skipped",
                },
                0,
            ),
        ]:
            with self.subTest(changes=changes):
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    env=dict(os.environ, **(defaults | changes)),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    expected, result.returncode, result.stdout + result.stderr
                )


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class RecoveryGithubScriptTests(unittest.TestCase):
    def run_script(self, job, fixture):
        script = JOBS[job]["steps"][0]["with"]["script"]
        harness = r"""
const [script, f] = JSON.parse(process.argv[1]);
const calls = [];
const context = {repo: {owner: 'owner', repo: 'repo'}, serverUrl: 'https://github.com', runId: 10, sha: 'merge-sha'};
const core = {warning: s => calls.push(['warning', s]), notice: s => calls.push(['notice', s]), summary: {addHeading() {return this}, addRaw(s) {calls.push(['summary', s]); return this}, async write() {}}};
const github = {rest: {issues: {}, actions: {}, repos: {}}};
github.rest.issues.listForRepo = 'issues';
github.rest.actions.listJobsForWorkflowRun = 'jobs';
github.rest.repos.listPullRequestsAssociatedWithCommit = 'pulls';
github.paginate = async (method, args) => {
  if (f.apiError || (method === 'pulls' && f.prError)) throw Error('unavailable');
  return f[method] || [];
};
github.rest.actions.listWorkflowRuns = async () => ({data: {workflow_runs: f.runs || [{id: 10, status: 'completed', conclusion: 'failure', html_url: 'run-url'}]}});
for (const method of ['create', 'update', 'createComment']) github.rest.issues[method] = async args => calls.push([method, args]);
process.env.MAIN_GATE_RESULT = f.result || 'failure';
process.env.FULL_COMPATIBILITY = f.full === false ? 'false' : 'true';
(async () => {await new (Object.getPrototypeOf(async function(){}).constructor)('github', 'context', 'core', script)(github, context, core); console.log(JSON.stringify(calls));})().catch(e => {console.error(e); process.exit(1)});
"""
        result = subprocess.run(
            ["node", "-e", harness, json.dumps([script, fixture])],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def incident(self):
        return {"number": 4, "title": "CI failure on main", "html_url": "incident-url"}

    def failure(self):
        return {
            "jobs": [
                {
                    "name": "no-Web",
                    "conclusion": "failure",
                    "html_url": "job-log-url",
                    "steps": [{"name": "unit tests", "conclusion": "failure"}],
                }
            ],
            "pulls": [
                {
                    "merged_at": "now",
                    "base": {"ref": "main"},
                    "merge_commit_sha": "merge-sha",
                    "html_url": "source-pr-url",
                }
            ],
        }

    def test_new_incident_has_actionable_evidence(self):
        calls = self.run_script("ci-visibility", self.failure())
        body = next(args["body"] for name, args in calls if name == "create")
        for evidence in (
            "source-pr-url",
            "/commit/merge-sha",
            "job-log-url",
            "no-Web",
            "unit tests",
            "#artifacts",
            "Recovery-first",
            "Main compatibility gate",
        ):
            self.assertIn(evidence, body)

    def test_repeated_failure_updates_latest_body_and_preserves_history(self):
        calls = self.run_script(
            "ci-visibility", dict(self.failure(), issues=[self.incident()])
        )
        self.assertEqual(["createComment", "update"], [name for name, _ in calls])
        self.assertEqual(calls[0][1]["body"], calls[1][1]["body"])

    def test_pr_lookup_failure_still_records_incident(self):
        calls = self.run_script("ci-visibility", dict(self.failure(), prError=True))
        body = next(args["body"] for name, args in calls if name == "create")
        self.assertIn("not resolved", body)
        self.assertIn("job-log-url", body)

    def test_only_latest_full_success_closes_incident(self):
        calls = self.run_script(
            "ci-visibility", {"result": "success", "issues": [self.incident()]}
        )
        self.assertEqual("closed", calls[-1][1]["state"])
        for fixture in ({"result": "success", "full": False}, {"runs": [{"id": 11}]}):
            calls = self.run_script(
                "ci-visibility", dict(fixture, issues=[self.incident()])
            )
            self.assertFalse(
                any(name in ("update", "create", "createComment") for name, _ in calls)
            )

    def test_red_pending_unknown_and_healthy_health_are_advisory(self):
        for fixture, expected in [
            ({"issues": [self.incident()]}, "Recovery-first"),
            ({"apiError": True}, "could not be verified"),
            ({"runs": []}, "unverified"),
            ({"runs": [{"status": "in_progress"}]}, "pending"),
            (
                {
                    "runs": [
                        {
                            "status": "completed",
                            "conclusion": "success",
                            "html_url": "green-url",
                        }
                    ]
                },
                "Main is healthy",
            ),
        ]:
            with self.subTest(fixture=fixture):
                calls = self.run_script("main-health", fixture)
                summary = next(message for name, message in calls if name == "summary")
                self.assertIn(expected, summary)
                self.assertFalse(
                    any(
                        name in ("create", "update", "createComment")
                        for name, _ in calls
                    )
                )


if __name__ == "__main__":
    unittest.main()
