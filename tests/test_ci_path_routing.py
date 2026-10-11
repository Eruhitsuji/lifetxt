import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.classify_ci_paths import classify, compatibility_checks


class CiPathRoutingTests(unittest.TestCase):
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
                ["lifetxt/web/new_endpoint.py"], added_paths=["./lifetxt/web/new_endpoint.py"]
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


if __name__ == "__main__":
    unittest.main()
