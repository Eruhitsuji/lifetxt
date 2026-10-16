"""Static contract test for release.yml's PyPI publish step.

Regression guard for a real bug found by the first real tag-triggered run
of release.yml: gh-action-pypi-publish validates every file in its
packages-dir, not only wheels/sdists, so pointing it at the combined
evidence directory (which also holds SHA256SUMS/sbom.cdx.json/
provenance.json) fails with "InvalidDistribution: Unknown distribution
format: 'SHA256SUMS'" before uploading anything.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


class ReleasePyPIPackagingContractTests(unittest.TestCase):
    def setUp(self):
        self.text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    def test_pypi_publish_step_points_at_a_wheel_and_sdist_only_directory(self):
        self.assertIn("packages-dir: dist-pypi", self.text)
        self.assertNotIn("packages-dir: dist-evidence", self.text)

    def test_only_missing_verified_distributions_are_published(self):
        self.assertIn("if: steps.primary.outputs.pypi_pending == 'true'", self.text)
        self.assertIn("skip-existing: false", self.text)
        self.assertIn("release_orchestrate.py start", self.text)


if __name__ == "__main__":
    unittest.main()
