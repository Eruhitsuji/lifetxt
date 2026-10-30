"""Persistent native labels for Focus, Review and Graph (#1477)."""

from html.parser import HTMLParser
import unittest
from lifetxt.web_assets import HTML_PAGE


class LabelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels = {}
        self.active = None
        self.inputs = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "label":
            self.active = attrs.get("for")
            if self.active:
                self.labels[self.active] = ""
        if tag == "input" and "id" in attrs:
            self.inputs[attrs["id"]] = (self.active, attrs)

    def handle_endtag(self, tag):
        if tag == "label":
            self.active = None

    def handle_data(self, data):
        if self.active:
            self.labels[self.active] += data


class PersistentLabelTests(unittest.TestCase):
    def test_labels_are_visible_associated_and_inputs_keep_their_contract(self):
        parser = LabelParser()
        parser.feed(HTML_PAGE)
        expected = {
            "focus-quick-title": "Title",
            "review-project": "Project",
            "review-from": "From",
            "review-to": "To",
            "graph-root": "Root id (optional)",
            "graph-depth": "Depth",
        }
        for key, label in expected.items():
            with self.subTest(key=key):
                self.assertEqual(1, parser.ids.count(key))
                self.assertEqual(label, parser.labels[key].strip())
                owner, attrs = parser.inputs[key]
                self.assertEqual(key, owner)
                self.assertNotIn("hidden", attrs)
                self.assertNotIn("disabled", attrs)
        self.assertIn(
            "focusQuickAdd()", parser.inputs["focus-quick-title"][1]["onkeydown"]
        )
        for key in ["review-from", "review-to"]:
            self.assertEqual("date", parser.inputs[key][1]["type"])
        self.assertEqual("numeric", parser.inputs["graph-depth"][1]["inputmode"])
