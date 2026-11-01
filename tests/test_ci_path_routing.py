import os
import subprocess
import sys
import tempfile
import unittest

import yaml
from pathlib import Path

from scripts.classify_ci_paths import classify, compatibility_checks, python310_focused


class CiPathRoutingTests(unittest.TestCase):
    def test_datetime_regression_and_shared_setup_select_python310(self):
        self.assertTrue(
            python310_focused(
                [
                    "lifetxt/agenda.py",
                    "lifetxt/recurrence.py",
                    "lifetxt/timeutil.py",
                    "tests/test_offset_recurrence.py",
                ]
            )
        )
        for path in (
            "./lifetxt/timezone_policy.py",
            "tests/test_offset_recurrence.py",
            "scripts/classify_ci_paths.py",
            ".github/workflows/ci.yml",
            "pyproject.toml",
            "setup.cfg",
            "setup.py",
            "requirements-web.txt",
        ):
            self.assertTrue(python310_focused([path]), path)
        self.assertTrue(python310_focused([]))
        for path in ("docs/en/cli.md", "lifetxt/parser.py", "tests/test_new_test.py"):
            self.assertFalse(python310_focused([path]), path)

    def test_docs_only_is_the_only_lightweight_category(self):
        self.assertEqual("docs-only", classify(["docs/en/web.md", "docs/ja/web.md"]))

    def test_python_web_and_tui_categories_are_explicit(self):
        self.assertEqual(
            "python-core", classify(["lifetxt/parser.py", "tests/test_lifetxt.py"])
        )
        self.assertEqual(
            "web", classify(["lifetxt/webapp.py", "tests/test_web_assets.py"])
        )
        self.assertEqual(
            "tui", classify(["lifetxt/tui.py", "tests/test_cui_extensions.py"])
        )

    def test_unknown_shared_mixed_and_empty_changes_fail_safe(self):
        for paths in (
            ["pyproject.toml"],
            [".github/workflows/ci.yml"],
            ["lifetxt/webapp.py", "lifetxt/tui.py"],
            [],
        ):
            self.assertEqual("full", classify(paths), paths)

    def test_project_control_files_are_not_treated_as_docs(self):
        self.assertEqual("full", classify([".ai/project/RULES.md"]))
        self.assertEqual("full", classify(["AGENTS.md"]))

    def test_sensitive_changes_select_dependency_contract_checks(self):
        for path in (
            "tests/test_quick_input.py",
            "lifetxt/webapp.py",
            "lifetxt/parser.py",
            "scripts/classify_ci_paths.py",
        ):
            self.assertEqual((True, False), compatibility_checks([path]), path)
        for path in (
            "pyproject.toml",
            "setup.cfg",
            "requirements-web.txt",
            ".github/workflows/ci.yml",
            "scripts/coverage-baseline.json",
            "tests/test_coverage_regression.py",
        ):
            self.assertEqual((True, True), compatibility_checks([path]), path)
        self.assertEqual((True, True), compatibility_checks([]))
        self.assertEqual((False, False), compatibility_checks(["docs/en/web.md"]))
        self.assertEqual(
            (True, False),
            compatibility_checks(["docs/en/web.md", "tests/test_quick_input.py"]),
        )

    def test_new_product_python_module_triggers_pr_coverage(self):
        # Regression: PR #1127 added modules but skipped coverage; main then failed.
        self.assertEqual(
            (True, True),
            compatibility_checks(
                [
                    ".ai/project/CAPABILITIES.yml",
                    "lifetxt/resource_reference_policy.py",
                    "lifetxt/resource_reference_resolution.py",
                    "tests/test_resource_reference_resolution.py",
                ],
                added_paths=[
                    "lifetxt/resource_reference_resolution.py",
                    "tests/test_resource_reference_resolution.py",
                ],
            ),
        )
        self.assertEqual(
            (True, True),
            compatibility_checks(
                ["lifetxt/web/new_endpoint.py"],
                added_paths=["./lifetxt/web/new_endpoint.py"],
            ),
        )

    def test_existing_edits_and_test_only_additions_do_not_force_coverage(self):
        self.assertEqual(
            (True, False),
            compatibility_checks(
                ["lifetxt/recurrence.py", "tests/test_offset_recurrence.py"],
                added_paths=[],
            ),
        )
        self.assertEqual(
            (True, False),
            compatibility_checks(
                ["tests/test_new_test.py"], added_paths=["tests/test_new_test.py"]
            ),
        )
        self.assertEqual(
            (True, False),
            compatibility_checks(
                ["lifetxt/docs/new_guide.md"],
                added_paths=["lifetxt/docs/new_guide.md"],
            ),
        )
        self.assertEqual(
            (False, False),
            compatibility_checks(
                ["docs/en/new_document.md"], added_paths=["docs/en/new_document.md"]
            ),
        )
        # An unknown/empty diff continues to trigger all compatibility checks.
        self.assertEqual((True, True), compatibility_checks([], added_paths=[]))

    def test_cli_passes_added_paths_to_coverage_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed-paths.txt"
            added = Path(directory) / "added-paths.txt"
            changed.write_text(
                "lifetxt/resource_reference_resolution.py\ntests/test_resource_reference_resolution.py\n",
                encoding="utf-8",
            )
            added.write_text(
                "lifetxt/resource_reference_resolution.py\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/classify_ci_paths.py",
                    str(changed),
                    "--added-paths-file",
                    str(added),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("run-no-web=true\n", result.stdout)
            self.assertIn("run-coverage=true\n", result.stdout)
            self.assertIn("run-python310-focused=false\n", result.stdout)

    def test_cli_exports_datetime_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = Path(directory) / "paths.txt"
            output = Path(directory) / "github-output.txt"
            paths.write_text("lifetxt/timeutil.py\n", encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "scripts/classify_ci_paths.py",
                    str(paths),
                    "--github-output",
                    str(output),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
            )
            self.assertIn("run-python310-focused=true\n", output.read_text())


class CiWorkflowDiffFallbackTests(unittest.TestCase):
    def test_actual_workflow_diff_routes_real_git_history_conservatively(self):
        root = Path(__file__).resolve().parent.parent
        workflow = yaml.load(
            (root / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
        )
        step = next(
            step
            for step in workflow["jobs"]["classify-changes"]["steps"]
            if step.get("id") == "classify"
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=repo, text=True, stderr=subprocess.STDOUT
                ).strip()

            git("init")
            git("config", "user.email", "ci-test@example.invalid")
            git("config", "user.name", "CI test")
            (repo / "docs").mkdir()
            doc = repo / "docs" / "guide.md"
            doc.write_text("base")
            git("add", ".")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD")
            doc.write_text("updated")
            git("add", ".")
            git("commit", "-m", "docs")
            docs_head = git("rev-parse", "HEAD")
            (repo / "lifetxt").mkdir()
            (repo / "lifetxt" / "new_module.py").write_text("VALUE = 1\n")
            git("add", ".")
            git("commit", "-m", "module")
            module_head = git("rev-parse", "HEAD")
            (repo / "scripts").mkdir()
            (repo / "scripts" / "classify_ci_paths.py").write_text(
                (root / "scripts" / "classify_ci_paths.py").read_text()
            )
            missing = "f" * 40
            cases = [
                ("push", base, docs_head, "docs-only", "false", "false"),
                ("pull_request", docs_head, module_head, "python-core", "true", "true"),
                ("push", missing, docs_head, "full", "true", "true"),
                ("pull_request", base, missing, "full", "true", "true"),
                ("push", "0" * 40, docs_head, "full", "true", "true"),
                ("push", "", docs_head, "full", "true", "true"),
                ("workflow_dispatch", base, docs_head, "full", "true", "true"),
            ]
            for event, before, head, category, no_web, coverage in cases:
                with self.subTest(event=event, base=before, head=head):
                    output = repo / "outputs.txt"
                    output.write_text("")
                    result = subprocess.run(
                        [
                            "bash",
                            "-e",
                            "-c",
                            step["run"].replace("${{ github.event_name }}", event),
                        ],
                        cwd=repo,
                        env=dict(
                            os.environ,
                            BASE_SHA=before,
                            HEAD_SHA=head,
                            GITHUB_OUTPUT=str(output),
                        ),
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    values = dict(
                        line.split("=", 1) for line in output.read_text().splitlines()
                    )
                    self.assertEqual(category, values["category"])
                    self.assertEqual(no_web, values["run-no-web"])
                    self.assertEqual(coverage, values["run-coverage"])
                    self.assertEqual(
                        "false" if category == "docs-only" else "true",
                        values["run-heavy"],
                    )
                    if category == "full":
                        self.assertEqual("true", values["run-python310-focused"])
                        self.assertEqual("", (repo / "changed-paths.txt").read_text())
                        self.assertEqual("", (repo / "added-paths.txt").read_text())


if __name__ == "__main__":
    unittest.main()
