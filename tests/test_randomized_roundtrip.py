import random
import unittest
from collections import OrderedDict

from lifetxt.model import Item
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line


class DeterministicRandomizedRoundTripTests(unittest.TestCase):
    def test_generated_items_reparse_to_the_same_canonical_line(self):
        generator = random.Random(358)
        # Keep the generated records within the parser's intentionally strict
        # semantic rules without weakening validation just for this test.
        statuses = ("[ ]", "[N]")
        kinds = ("T", "N")
        detail_keys = ("id", "project", "tag", "note", "recipient", "body")
        title_parts = (
            "plain",
            "two words",
            'quoted "title"',
            r"path\segment",
            "日本語",
        )
        value_parts = ("alpha", "two words", 'quoted "value"', r"path\value", "生活")

        for index in range(128):
            details = OrderedDict()
            for key in generator.sample(detail_keys, generator.randint(1, 4)):
                values = [generator.choice(value_parts)]
                if generator.random() < 0.25 and key not in ("body", "id"):
                    values.append(generator.choice(value_parts))
                details[key] = values
            item = Item(
                generator.choice(statuses),
                generator.choice(kinds),
                "record %s %s" % (index, generator.choice(title_parts)),
                details,
                indent=generator.choice((0, 0, 2)),
            )

            with self.subTest(index=index):
                canonical = item_to_line(item) + "\n"
                parsed, diagnostics = parse_text(canonical)
                errors = [
                    diagnostic
                    for diagnostic in diagnostics
                    if diagnostic.severity == "error"
                ]
                self.assertEqual([], errors)
                self.assertEqual(1, len(parsed))
                reparsed_canonical = item_to_line(parsed[0]) + "\n"
                self.assertEqual(canonical, reparsed_canonical)


if __name__ == "__main__":
    unittest.main()
