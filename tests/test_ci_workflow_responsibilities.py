import os
import unittest

import yaml


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_PATH = os.path.join(ROOT, ".github", "workflows", "ci.yml")
RELEASE_PATH = os.path.join(ROOT, ".github", "workflows", "release.yml")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml.BaseLoader)


class CiWorkflowResponsibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = _load(CI_PATH)
        cls.jobs = cls.workflow["jobs"]
        with open(CI_PATH, encoding="utf-8") as handle:
            cls.text = handle.read()

    def test_pr_runs_one_python_version_and_cancels_superseded_runs(self):
        concurrency = self.workflow["concurrency"]
        self.assertIn("pull_request.number", concurrency["group"])
        self.assertIn("github.run_id", concurrency["group"])
        self.assertEqual(
            "${{ github.event_name == 'pull_request' }}",
            concurrency["cancel-in-progress"],
        )
        versions = self.jobs["test"]["strategy"]["matrix"]["python-version"]
        self.assertIn("'[\"3.12\"]'", versions)
        self.assertIn('\'["3.10", "3.11", "3.12"]\'', versions)

    def test_compatibility_jobs_are_main_or_dispatch_only(self):
        expected = {
            "resource-warning-gate",
            "no-web-extras",
            "windows-core-smoke",
            "macos-core-smoke",
            "coverage-baseline",
            "optional-dependency-compatibility",
        }
        for name in expected:
            self.assertEqual(
                "${{ github.event_name != 'pull_request' }}",
                self.jobs[name]["if"],
                name,
            )

    def test_pr_gate_aggregates_fast_merge_responsibilities(self):
        gate = self.jobs["pr-gate"]
        self.assertEqual(
            {"test", "type-check", "release-document-validation", "traceability-gate"},
            set(gate["needs"]),
        )
        self.assertIn("always()", gate["if"])
        self.assertIn('value != "success"', self.text)

    def test_main_gate_aggregates_all_compatibility_responsibilities(self):
        gate = self.jobs["main-gate"]
        self.assertEqual(
            {
                "test",
                "resource-warning-gate",
                "no-web-extras",
                "windows-core-smoke",
                "macos-core-smoke",
                "coverage-baseline",
                "type-check",
                "optional-dependency-compatibility",
                "release-document-validation",
            },
            set(gate["needs"]),
        )
        self.assertEqual(["main-gate"], self.jobs["ci-visibility"]["needs"])
        visibility_env = self.jobs["ci-visibility"]["env"]
        self.assertEqual({"MAIN_GATE_RESULT"}, set(visibility_env))

    def test_release_artifact_work_stays_in_release_workflow(self):
        self.assertNotIn("release-gate", self.jobs)
        with open(RELEASE_PATH, encoding="utf-8") as handle:
            release = handle.read()
        self.assertIn("run_ci_like.py --profile release", release)
        self.assertIn("python -m twine check", release)
        self.assertIn("pip install dist-evidence/*.whl", release)


if __name__ == "__main__":
    unittest.main()
