import os
import unittest

from scripts.classify_ci_paths import classify


class CiPathRoutingTests(unittest.TestCase):
    def test_docs_only_is_the_only_lightweight_category(self):
        self.assertEqual("docs-only", classify(["docs/en/web.md", "docs/ja/web.md"]))

    def test_python_web_and_tui_categories_are_explicit(self):
        self.assertEqual("python-core", classify(["lifetxt/parser.py", "tests/test_lifetxt.py"]))
        self.assertEqual("web", classify(["lifetxt/webapp.py", "tests/test_web_assets.py"]))
        self.assertEqual("tui", classify(["lifetxt/tui.py", "tests/test_cui_extensions.py"]))

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


if __name__ == "__main__":
    unittest.main()
