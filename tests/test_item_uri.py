"""Tests for the host-independent lifetxt://item/<id> logical record link
(#840): lifetxt/item_uri.py's format/parse/round-trip contract.
"""

import unittest

from lifetxt.item_uri import (
    ItemUriError,
    format_item_uri,
    is_item_uri,
    parse_item_uri,
    web_deep_link,
)


class FormatItemUriTests(unittest.TestCase):
    def test_formats_a_plain_id(self):
        self.assertEqual("lifetxt://item/task-001", format_item_uri("task-001"))

    def test_encodes_special_characters(self):
        self.assertEqual("lifetxt://item/a%20b", format_item_uri("a b"))
        self.assertEqual("lifetxt://item/a%2Fb", format_item_uri("a/b"))
        self.assertEqual("lifetxt://item/a%3Fb", format_item_uri("a?b"))
        self.assertEqual("lifetxt://item/a%23b", format_item_uri("a#b"))

    def test_empty_id_is_rejected(self):
        with self.assertRaises(ItemUriError):
            format_item_uri("")
        with self.assertRaises(ItemUriError):
            format_item_uri(None)

    def test_accepts_a_non_string_id_by_stringifying_it(self):
        self.assertEqual("lifetxt://item/42", format_item_uri(42))


class ParseItemUriTests(unittest.TestCase):
    def test_parses_a_plain_id(self):
        self.assertEqual("task-001", parse_item_uri("lifetxt://item/task-001"))

    def test_round_trips_ids_requiring_encoding(self):
        for raw_id in ["a b", "a/b", "a?b", "a#b", "日本語", "a+b", "100%"]:
            uri = format_item_uri(raw_id)
            self.assertEqual(raw_id, parse_item_uri(uri))

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(
            "task-001", parse_item_uri("  lifetxt://item/task-001  ")
        )

    def test_wrong_scheme_is_malformed(self):
        with self.assertRaises(ItemUriError):
            parse_item_uri("https://example.invalid/item/task-001")
        with self.assertRaises(ItemUriError):
            parse_item_uri("lifetxt://source/task-001")

    def test_empty_id_segment_is_malformed(self):
        with self.assertRaises(ItemUriError):
            parse_item_uri("lifetxt://item/")

    def test_non_string_input_is_malformed(self):
        with self.assertRaises(ItemUriError):
            parse_item_uri(None)
        with self.assertRaises(ItemUriError):
            parse_item_uri(123)

    def test_unencoded_slash_in_id_segment_is_malformed(self):
        # A literal, unencoded "/" would introduce a second path segment;
        # a real id containing "/" must be percent-encoded (see
        # test_round_trips_ids_requiring_encoding).
        with self.assertRaises(ItemUriError):
            parse_item_uri("lifetxt://item/a/b")

    def test_unencoded_query_or_fragment_delimiter_is_malformed(self):
        with self.assertRaises(ItemUriError):
            parse_item_uri("lifetxt://item/task?x=1")
        with self.assertRaises(ItemUriError):
            parse_item_uri("lifetxt://item/task#frag")

    def test_malformed_uri_is_distinguishable_from_an_unresolved_id(self):
        # parse_item_uri only validates shape; it never claims an id
        # exists. A well-formed URI for an id nothing has is a completely
        # different, later failure than a malformed URI -- confirmed here
        # by parse_item_uri succeeding for an id that is not "known" to
        # this module at all (it has no concept of existence).
        self.assertEqual(
            "definitely-does-not-exist",
            parse_item_uri("lifetxt://item/definitely-does-not-exist"),
        )
        with self.assertRaises(ItemUriError):
            parse_item_uri("not-a-lifetxt-uri-at-all")


class IsItemUriTests(unittest.TestCase):
    def test_recognizes_the_prefix(self):
        self.assertTrue(is_item_uri("lifetxt://item/task-001"))
        self.assertTrue(is_item_uri("  lifetxt://item/task-001"))

    def test_rejects_other_strings(self):
        self.assertFalse(is_item_uri("https://example.invalid/"))
        self.assertFalse(is_item_uri(""))
        self.assertFalse(is_item_uri(None))
        self.assertFalse(is_item_uri(123))


class WebDeepLinkTests(unittest.TestCase):
    def test_root_relative_without_a_base_url(self):
        self.assertEqual("/?id=task-001", web_deep_link("task-001"))

    def test_absolute_with_a_base_url(self):
        self.assertEqual(
            "https://lifetxt.example.invalid/?id=task-001",
            web_deep_link("task-001", base_url="https://lifetxt.example.invalid"),
        )

    def test_base_url_trailing_slash_is_normalized(self):
        self.assertEqual(
            "https://lifetxt.example.invalid/?id=task-001",
            web_deep_link("task-001", base_url="https://lifetxt.example.invalid/"),
        )

    def test_encodes_the_id(self):
        self.assertEqual("/?id=a%20b", web_deep_link("a b"))

    def test_empty_id_is_rejected(self):
        with self.assertRaises(ItemUriError):
            web_deep_link("")

    def test_never_changes_the_underlying_id(self):
        # Translating to a deep link and parsing the deep link's id=
        # query value back out must agree with the original id.
        from urllib.parse import urlparse, parse_qs

        link = web_deep_link("task-001", base_url="https://lifetxt.example.invalid")
        parsed = urlparse(link)
        self.assertEqual(["task-001"], parse_qs(parsed.query)["id"])


if __name__ == "__main__":
    unittest.main()
