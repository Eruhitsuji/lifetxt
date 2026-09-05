"""Unit tests for the shared `progress:` semantic helper (#646)."""

import unittest

from lifetxt.progress import ProgressValueError, is_valid_progress, parse_progress


class ValidPercentageTests(unittest.TestCase):
    def test_zero_percent(self):
        value = parse_progress("0%")
        self.assertEqual("0%", value.raw)
        self.assertEqual("percentage", value.kind)
        self.assertIsNone(value.current)
        self.assertIsNone(value.total)
        self.assertEqual(0.0, value.percent)
        self.assertEqual(0.0, value.ratio)

    def test_hundred_percent(self):
        value = parse_progress("100%")
        self.assertEqual(100.0, value.percent)
        self.assertEqual(1.0, value.ratio)

    def test_integer_percent(self):
        value = parse_progress("75%")
        self.assertEqual(75.0, value.percent)
        self.assertEqual(0.75, value.ratio)

    def test_decimal_percent(self):
        value = parse_progress("33.3%")
        self.assertAlmostEqual(33.3, value.percent)
        self.assertAlmostEqual(0.333, value.ratio, places=3)


class ValidFractionTests(unittest.TestCase):
    def test_zero_of_ten(self):
        value = parse_progress("0/10")
        self.assertEqual("fraction", value.kind)
        self.assertEqual(0, value.current)
        self.assertEqual(10, value.total)
        self.assertEqual(0.0, value.ratio)

    def test_three_of_ten(self):
        value = parse_progress("3/10")
        self.assertEqual(3, value.current)
        self.assertEqual(10, value.total)
        self.assertAlmostEqual(0.3, value.ratio)
        self.assertAlmostEqual(30.0, value.percent)

    def test_ten_of_ten_is_complete(self):
        value = parse_progress("10/10")
        self.assertEqual(1.0, value.ratio)

    def test_raw_representation_is_preserved_verbatim(self):
        # 3/5 and 60% are the same ratio but must never be silently
        # converted into each other.
        fraction = parse_progress("3/5")
        percent = parse_progress("60%")
        self.assertEqual("3/5", fraction.raw)
        self.assertEqual("60%", percent.raw)
        self.assertEqual(fraction.ratio, percent.ratio)


class InvalidPercentageTests(unittest.TestCase):
    def test_negative_percent_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("-1%")
        self.assertIn("out of range", ctx.exception.reason)

    def test_over_100_percent_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("101%")
        self.assertIn("out of range", ctx.exception.reason)


class InvalidFractionTests(unittest.TestCase):
    def test_zero_total_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("5/0")
        self.assertIn("greater than 0", ctx.exception.reason)

    def test_current_exceeding_total_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("12/10")
        self.assertIn("must not exceed", ctx.exception.reason)

    def test_negative_current_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("-1/5")
        self.assertIn("must not be negative", ctx.exception.reason)

    def test_negative_total_is_rejected(self):
        with self.assertRaises(ProgressValueError):
            parse_progress("3/-5")


class AmbiguousOrGarbageValueTests(unittest.TestCase):
    def test_bare_unitless_number_is_rejected(self):
        with self.assertRaises(ProgressValueError) as ctx:
            parse_progress("0.5")
        self.assertIn("not a valid progress value", ctx.exception.reason)

    def test_garbage_text_is_rejected(self):
        with self.assertRaises(ProgressValueError):
            parse_progress("almost done")

    def test_empty_string_is_rejected(self):
        with self.assertRaises(ProgressValueError):
            parse_progress("")


class IsValidProgressTests(unittest.TestCase):
    def test_true_for_valid_values(self):
        self.assertTrue(is_valid_progress("75%"))
        self.assertTrue(is_valid_progress("3/10"))

    def test_false_for_invalid_values(self):
        self.assertFalse(is_valid_progress("101%"))
        self.assertFalse(is_valid_progress("5/0"))
        self.assertFalse(is_valid_progress("0.5"))


if __name__ == "__main__":
    unittest.main()
