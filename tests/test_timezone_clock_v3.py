import datetime
import unittest

from lifetxt.timezone_policy import (
    clock_context,
    interpret_time,
    local_now_naive,
    now,
    timezone_context,
    today,
    utcnow,
)


class TimezoneClockV3Tests(unittest.TestCase):
    def test_frozen_aware_clock_converts_per_context(self):
        frozen = datetime.datetime(2026, 7, 23, 15, 30, tzinfo=datetime.timezone.utc)
        with clock_context(frozen), timezone_context("Asia/Tokyo"):
            self.assertEqual("2026-07-24T00:30:00+09:00", now().isoformat())
            self.assertEqual(datetime.date(2026, 7, 24), today())
            self.assertEqual("2026-07-23T15:30:00+00:00", utcnow().isoformat())
            self.assertEqual(datetime.datetime(2026, 7, 24, 0, 30), local_now_naive())

    def test_frozen_naive_clock_is_resolved_wall_time(self):
        frozen = datetime.datetime(2026, 1, 2, 3, 4)
        with clock_context(frozen), timezone_context("Asia/Kathmandu"):
            self.assertEqual(
                "+05:45", now().strftime("%z")[:3] + ":" + now().strftime("%z")[3:]
            )
            self.assertEqual(datetime.date(2026, 1, 2), today())

    def test_time_only_default_anchor_uses_context_today(self):
        frozen = datetime.datetime(2026, 7, 23, 15, 30, tzinfo=datetime.timezone.utc)
        with clock_context(frozen), timezone_context("Asia/Tokyo"):
            value = interpret_time("09:00")
        self.assertEqual(datetime.date(2026, 7, 24), value.date())
        self.assertEqual(9, value.hour)

    def test_clock_context_is_nested_and_restored(self):
        outer = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        inner = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)
        with clock_context(outer), timezone_context("UTC"):
            self.assertEqual(1, now().month)
            with clock_context(inner):
                self.assertEqual(2, now().month)
            self.assertEqual(1, now().month)


if __name__ == "__main__":
    unittest.main()
