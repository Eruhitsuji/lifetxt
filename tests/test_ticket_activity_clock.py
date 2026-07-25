import datetime
import unittest

from lifetxt.ticket_activity import _date_text, _utc_text
from lifetxt.timezone_policy import clock_context


class TicketActivityClockTests(unittest.TestCase):
    def test_default_event_time_uses_injected_shared_utc_clock(self):
        tokyo = datetime.timezone(datetime.timedelta(hours=9))
        fixed = datetime.datetime(2026, 7, 25, 0, 30, 45, tzinfo=tokyo)
        with clock_context(fixed):
            self.assertEqual("2026-07-24T15:30:45Z", _utc_text())
            self.assertEqual("2026-07-24", _date_text())

    def test_authored_offset_time_is_normalized_to_utc(self):
        self.assertEqual(
            "2026-07-25T01:15:00Z",
            _utc_text("2026-07-25T10:15:00+09:00"),
        )

    def test_naive_event_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            _utc_text("2026-07-25T10:15:00")


if __name__ == "__main__":
    unittest.main()
