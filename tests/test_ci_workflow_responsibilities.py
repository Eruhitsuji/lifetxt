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
            "windows-core-smoke",
            "macos-core-smoke",
            "optional-dependency-compatibility",
        }
        for name in expected:
            self.assertEqual(
                "${{ github.event_name != 'pull_request' && needs['classify-changes'].outputs['run-heavy'] == 'true' }}",
                self.jobs[name]["if"],
                name,
            )

    def test_new_product_modules_are_passed_to_pr_coverage_classifier(self):
        classify = self.jobs["classify-changes"]["steps"][-1]["run"]
        self.assertIn(": > added-paths.txt", classify)
        self.assertIn(
            'git diff --diff-filter=A --name-only "$BASE_SHA" "$HEAD_SHA" > added-paths.txt',
            classify,
        )
        self.assertIn(
            "python scripts/classify_ci_paths.py changed-paths.txt "
            "--added-paths-file added-paths.txt --github-output",
            classify,
        )
        self.assertIn(
            "outputs['run-coverage']", self.jobs["coverage-baseline"]["if"]
        )

    def test_python_312_reports_slowest_tests_without_new_suite_runs(self):
        web = next(
            step for step in self.jobs["test"]["steps"]
            if step["name"] == "Run unit tests"
        )["run"]
        self.assertIn('if [[ "${{ matrix.python-version }}" == "3.12" ]]; then', web)
        self.assertIn("duration_args=()", web)
        self.assertIn("duration_args=(--durations=20)", web)
        self.assertIn('python -m unittest discover "${duration_args[@]}"', web)
        self.assertIn("set -o pipefail", web)
        self.assertIn("| tee unit-tests-${{ matrix.python-version }}.log", web)

        no_web = next(
            step for step in self.jobs["no-web-extras"]["steps"]
            if step["name"] == "Run unit tests without extras"
        )["run"]
        self.assertIn(
            "python -m unittest discover --durations=20 2>&1 | tee unit-tests-no-web.log",
            no_web,
        )
        self.assertIn("set -o pipefail", no_web)

        coverage = next(
            step for step in self.jobs["coverage-baseline"]["steps"]
            if step["name"] == "Run tests and write coverage evidence"
        )["run"]
        self.assertIn(
            "coverage run --branch -m unittest discover --durations=20 "
            "2>&1 | tee coverage-tests.log",
            coverage,
        )
        self.assertIn("set -o pipefail", coverage)
        self.assertIn("python scripts/check_coverage_regression.py", coverage)

    def test_no_web_lane_installs_yaml_without_web_extras(self):
        job = self.jobs["no-web-extras"]
        install = next(
            step
            for step in job["steps"]
            if step["name"].startswith("Install dependency-free")
        )
        self.assertIn("python -m pip install -e .", install["run"])
        self.assertIn("python -m pip install PyYAML", install["run"])
        absent_check = next(
            step
            for step in job["steps"]
            if step["name"].startswith("Assert optional Web")
        )
        for package in ("fastapi", "uvicorn", "httpx", "httpx2"):
            self.assertIn(package, absent_check["run"])

    def test_pr_gate_aggregates_fast_merge_responsibilities(self):
        gate = self.jobs["pr-gate"]
        self.assertEqual(
            {
                "classify-changes",
                "test",
                "revision-browser",
                "type-check",
                "release-document-validation",
                "traceability-gate",
                "no-web-extras",
                "coverage-baseline",
                "main-health",
                "python310-focused",
            },
            set(gate["needs"]),
        )
        self.assertIn("always()", gate["if"])
        self.assertIn("PATH_CATEGORY", self.text)
        self.assertEqual(
            "Optional dependency compatibility",
            self.jobs["optional-dependency-compatibility"]["name"],
        )

    def test_python310_datetime_check_is_pr_only_and_core_only(self):
        job = self.jobs["python310-focused"]
        self.assertEqual(
            "${{ github.event_name == 'pull_request' && needs['classify-changes'].outputs['run-python310-focused'] == 'true' }}",
            job["if"],
        )
        self.assertEqual(["classify-changes"], job["needs"])
        self.assertEqual("3.10", job["steps"][1]["with"]["python-version"])
        self.assertEqual("python -m pip install -e .", job["steps"][2]["run"])
        self.assertIn("tests.test_offset_recurrence", job["steps"][3]["run"])
        self.assertIn("set -o pipefail", job["steps"][3]["run"])
        self.assertNotIn("python310-focused", self.jobs["main-gate"]["needs"])
        env = self.jobs["pr-gate"]["steps"][0]["env"]
        self.assertIn("run-python310-focused", env["PYTHON310_SELECTED"])
        self.assertIn("python310-focused", env["PYTHON310_RESULT"])

    def test_main_gate_aggregates_all_compatibility_responsibilities(self):
        gate = self.jobs["main-gate"]
        self.assertEqual(
            {
                "test",
                "revision-browser",
                "classify-changes",
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
        self.assertEqual(
            ["main-gate", "classify-changes"], self.jobs["ci-visibility"]["needs"]
        )
        visibility_env = self.jobs["ci-visibility"]["env"]
        self.assertEqual(
            {"MAIN_GATE_RESULT", "FULL_COMPATIBILITY"}, set(visibility_env)
        )

    def test_release_artifact_work_stays_in_release_workflow(self):
        self.assertNotIn("release-gate", self.jobs)
        with open(RELEASE_PATH, encoding="utf-8") as handle:
            release = handle.read()
        self.assertIn("run_ci_like.py --profile release", release)
        self.assertIn("python -m twine check", release)
        self.assertIn("pip install dist-evidence/*.whl", release)


if __name__ == "__main__":
    unittest.main()
