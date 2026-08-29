"""Static contract test for standalone-binaries.yml's macOS Intel runner.

Regression guard for a real bug found by the v1.0.1 release: GitHub retired
the plain `macos-13` runner label on 2025-12-04, so a build job requesting
it queues forever with no runner ever assigned. `macos-15-intel` is
GitHub's documented replacement label for Intel-macOS builds.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "standalone-binaries.yml"


class StandaloneBinariesRunnerLabelTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_macos_x86_64_build_uses_the_retired_labels_replacement(self):
        self.assertIn("os: macos-15-intel", self.text)

    def test_the_retired_bare_macos_13_label_is_not_used_as_a_runner(self):
        self.assertNotIn("os: macos-13\n", self.text)


if __name__ == "__main__":
    unittest.main()
