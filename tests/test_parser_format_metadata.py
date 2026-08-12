import unittest

from lifetxt.parser import FORMAT_VERSION, ParseResult, parse_text


class ParserFormatMetadataTests(unittest.TestCase):
    def test_result_remains_tuple_compatible(self):
        result = parse_text("[ ] T Task\n")

        self.assertIsInstance(result, ParseResult)
        items, diagnostics = result
        self.assertEqual("Task", items[0].title)
        self.assertEqual([], diagnostics)

    def test_current_format_metadata_is_explicit(self):
        result = parse_text("#! format_version: 1\n[ ] T Task\n")

        self.assertEqual(FORMAT_VERSION, result.format_version)
        self.assertEqual("current", result.format_version_state)
        self.assertEqual("1", result.directives["format_version"])

    def test_unversioned_documents_are_marked_for_compatibility_mode(self):
        result = parse_text("#! timezone: UTC\n[ ] T Task\n")

        self.assertIsNone(result.format_version)
        self.assertEqual("unversioned", result.format_version_state)
        self.assertEqual("UTC", result.directives["timezone"])

    def test_unsupported_format_metadata_is_available_before_mutation(self):
        result = parse_text("#! format_version: 2\n[ ] T Future\n")

        self.assertEqual("2", result.format_version)
        self.assertEqual("unsupported", result.format_version_state)
        self.assertEqual("Future", result[0][0].title)


if __name__ == "__main__":
    unittest.main()
