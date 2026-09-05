"""Unit tests for the bounded E009/E010 cascade grouping helper (#642)."""

import unittest

from lifetxt.diagnostic_cascade import classify_cascade_roles
from lifetxt.model import Diagnostic


def _d(code, line, column, source="life.txt"):
    return Diagnostic("error", code, "x", line=line, column=column, source=source)


class ClassifyCascadeRolesTests(unittest.TestCase):
    def test_two_e010_on_the_same_line_form_a_root_and_secondary(self):
        root = _d("E010", 1, 13)
        secondary = _d("E010", 1, 20)
        roles = classify_cascade_roles([root, secondary])
        self.assertEqual(("root", [secondary]), roles[id(root)])
        self.assertEqual(("secondary", root), roles[id(secondary)])

    def test_e009_then_e010_on_the_same_line_are_grouped_together(self):
        root = _d("E009", 1, 13)
        secondary = _d("E010", 1, 20)
        roles = classify_cascade_roles([root, secondary])
        self.assertEqual(("root", [secondary]), roles[id(root)])
        self.assertEqual(("secondary", root), roles[id(secondary)])

    def test_three_e010_on_one_line_produce_one_root_and_two_secondaries(self):
        d1, d2, d3 = _d("E010", 1, 13), _d("E010", 1, 20), _d("E010", 1, 24)
        roles = classify_cascade_roles([d1, d2, d3])
        self.assertEqual(("root", [d2, d3]), roles[id(d1)])
        self.assertEqual(("secondary", d1), roles[id(d2)])
        self.assertEqual(("secondary", d1), roles[id(d3)])

    def test_lone_e010_on_its_line_forms_no_group(self):
        solo = _d("E010", 1, 13)
        roles = classify_cascade_roles([solo])
        self.assertNotIn(id(solo), roles)

    def test_e010_on_different_lines_are_not_grouped(self):
        first = _d("E010", 1, 13)
        second = _d("E010", 2, 13)
        roles = classify_cascade_roles([first, second])
        self.assertEqual({}, roles)

    def test_e010_on_the_same_line_in_different_source_files_are_not_grouped(self):
        first = _d("E010", 1, 13, source="a.life.txt")
        second = _d("E010", 1, 13, source="b.life.txt")
        roles = classify_cascade_roles([first, second])
        self.assertEqual({}, roles)

    def test_unrelated_codes_on_the_same_line_are_never_grouped(self):
        # A genuinely independent tab-separator error and an invalid-status
        # error can legitimately share one line; neither is a consequence
        # of the other, and this family must not claim otherwise.
        tab_error = _d("E001", 1, 4)
        status_error = _d("E003", 1, 1)
        roles = classify_cascade_roles([tab_error, status_error])
        self.assertEqual({}, roles)

    def test_mixed_family_and_unrelated_codes_only_groups_the_family_members(self):
        tab_error = _d("E001", 1, 4)
        detail_error_1 = _d("E010", 1, 13)
        detail_error_2 = _d("E010", 1, 20)
        roles = classify_cascade_roles([tab_error, detail_error_1, detail_error_2])
        self.assertNotIn(id(tab_error), roles)
        self.assertEqual(("root", [detail_error_2]), roles[id(detail_error_1)])
        self.assertEqual(("secondary", detail_error_1), roles[id(detail_error_2)])

    def test_empty_list_returns_empty_dict(self):
        self.assertEqual({}, classify_cascade_roles([]))


if __name__ == "__main__":
    unittest.main()
