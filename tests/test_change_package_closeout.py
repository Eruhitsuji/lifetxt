"""A change package must not still say `proposed` once its work has been merged.

The first change package, `windows-atomic-replace-retry`, sat at
`change.yml: status: proposed` with all five `verification.yml` entries reading
`planned` after five pull requests had merged. Nothing reported it. The issue
produced the package, the pull requests did the work, and no step owned the
transition to done (#117).

`.ai/project/changes/README.md` requires closing or archiving a package after
merge, and `ASSURANCE_LEVELS.md` expects retained evidence at High assurance --
which the package is the artifact for. A package left at `proposed` records what
was intended, not what happened.

The check is deliberately offline. Whether a pull request actually merged is not
knowable from the repository, so this uses the package's own contradiction
instead: its `traceability.yml` claiming `status: implemented`, or naming a pull
request, while `change.yml` still says the change is only proposed. That state is
self-inconsistent regardless of what GitHub says, which makes it both checkable
here and true independently of network access.

This mirrors `tests/test_traceability_gate.py` from #88: the policy is ordinary
unittest code so it can be read, tested, and argued with.
"""

from __future__ import unicode_literals

import glob
import io
import os
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only where PyYAML is absent
    yaml = None


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGES_DIR = os.path.join(ROOT, ".ai", "project", "changes")

#: A package at one of these has not claimed to be finished yet.
UNSTARTED_STATUSES = frozenset(("draft", "proposed"))

#: Statuses in a package's own traceability links that mean work has landed.
LANDED_STATUSES = frozenset(("implemented", "verified", "released"))


def _load(path):
    with io.open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _packages():
    """Every change package directory, excluding the template."""
    found = []
    for entry in sorted(glob.glob(os.path.join(CHANGES_DIR, "*"))):
        if not os.path.isdir(entry) or os.path.basename(entry) == "_template":
            continue
        found.append(entry)
    return found


class ChangePackageCloseoutTests(unittest.TestCase):
    def setUp(self):
        if yaml is None:
            self.skipTest(
                "PyYAML is unavailable, so the package records cannot be parsed"
            )

    def landed_links(self, package):
        """Links whose own record says the work landed."""
        path = os.path.join(package, "traceability.yml")
        if not os.path.exists(path):
            return []
        links = _load(path).get("links") or []
        return [
            link
            for link in links
            if str(link.get("status") or "") in LANDED_STATUSES
            or link.get("pull_request")
        ]

    def test_a_package_with_landed_work_is_not_still_proposed(self):
        for package in _packages():
            name = os.path.basename(package)
            landed = self.landed_links(package)
            if not landed:
                continue
            status = str(
                (_load(os.path.join(package, "change.yml")).get("change") or {}).get(
                    "status"
                )
                or ""
            )
            self.assertNotIn(
                status,
                UNSTARTED_STATUSES,
                "change package %r has %d traceability link(s) reporting landed work, but "
                "change.yml still says status: %s. Close the package: see "
                ".ai/project/changes/README.md and .ai/project/RULES.md."
                % (name, len(landed), status or "<missing>"),
            )

    def test_a_package_with_landed_work_has_no_planned_verification_left(self):
        for package in _packages():
            name = os.path.basename(package)
            if not self.landed_links(package):
                continue
            path = os.path.join(package, "verification.yml")
            if not os.path.exists(path):
                continue
            verification = _load(path).get("verification") or {}
            stale = [
                entry
                for group in verification.values()
                if isinstance(group, list)
                for entry in group
                if isinstance(entry, dict)
                and str(entry.get("status") or "") == "planned"
            ]
            self.assertEqual(
                [],
                stale,
                "change package %r has landed work but %d verification entr(y/ies) still read "
                "'planned'. Record what actually ran, or record the gap. A plan is not evidence."
                % (name, len(stale)),
            )

    def test_every_package_carries_the_files_the_template_defines(self):
        """A half-built package cannot be closed, and should fail before it is."""
        expected = {
            os.path.basename(p)
            for p in glob.glob(os.path.join(CHANGES_DIR, "_template", "*"))
        }
        self.assertTrue(expected, "the change package template is missing")
        for package in _packages():
            present = {
                os.path.basename(p) for p in glob.glob(os.path.join(package, "*"))
            }
            self.assertEqual(
                set(),
                expected - present,
                "change package %r is missing %s"
                % (os.path.basename(package), sorted(expected - present)),
            )


if __name__ == "__main__":
    unittest.main()
