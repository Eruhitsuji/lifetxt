import os
import tempfile
import unittest

from lifetxt.paths import expand_paths


class ExpandPathsTests(unittest.TestCase):
    def test_directory_expansion_uses_documented_pattern_then_name_order(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            names = ("z.life.txt", "a.life.txt", "life.txt", "notes.txt")
            for name in names:
                open(os.path.join(root, name), "w", encoding="utf-8").close()

            result = expand_paths([root])

        self.assertEqual(
            [
                os.path.join(root, "life.txt"),
                os.path.join(root, "a.life.txt"),
                os.path.join(root, "z.life.txt"),
                os.path.join(root, "notes.txt"),
            ],
            result,
        )

    def test_glob_results_are_sorted_and_explicit_input_order_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            paths = [os.path.join(root, name) for name in ("c.txt", "a.txt", "b.txt")]
            for path in paths:
                open(path, "w", encoding="utf-8").close()

            glob_result = expand_paths([os.path.join(root, "*.txt")])
            explicit_result = expand_paths([paths[2], paths[0], paths[1]])

        self.assertEqual(sorted(paths), glob_result)
        self.assertEqual([paths[2], paths[0], paths[1]], explicit_result)

    def test_duplicate_paths_are_removed_by_absolute_identity(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            path = os.path.join(root, "life.txt")
            open(path, "w", encoding="utf-8").close()
            result = expand_paths([path, os.path.join(root, ".", "life.txt")])

        self.assertEqual([path], result)


if __name__ == "__main__":
    unittest.main()
