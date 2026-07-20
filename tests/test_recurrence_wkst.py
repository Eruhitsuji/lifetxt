"""WKST week boundaries, and calendar import that expands recurrences.

The WKST cases come from RFC 5545 section 3.8.5.3, which gives two rules that
differ only in WKST and produce different dates. That pair is the whole point
of the feature, so it is asserted verbatim.
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifetxt import recurrence
from lifetxt.ics import items_from_ics_text
from lifetxt.serializer import item_to_line
from lifetxt.validator import validate_item
from lifetxt.parser import parse_text


def _dates(rule, start, **kwargs):
    return [moment.strftime("%Y-%m-%d")
            for moment in recurrence.expand(recurrence.parse_rule(rule), start, **kwargs)]


class WkstParsingTests(unittest.TestCase):
    def test_defaults_to_monday(self):
        rule = recurrence.parse_rule("RRULE:FREQ=WEEKLY;BYDAY=MO")

        self.assertEqual(recurrence.WEEKDAY_CODES["MO"], rule["wkst"])

    def test_reads_the_declared_week_start(self):
        rule = recurrence.parse_rule("RRULE:FREQ=WEEKLY;BYDAY=MO;WKST=SU")

        self.assertEqual(recurrence.WEEKDAY_CODES["SU"], rule["wkst"])

    def test_is_no_longer_reported_as_unsupported(self):
        rule = recurrence.parse_rule("RRULE:FREQ=WEEKLY;BYDAY=MO;WKST=SU")

        self.assertEqual([], rule["unsupported"])

    def test_a_bad_week_start_fails_loudly(self):
        with self.assertRaises(recurrence.RecurrenceError):
            recurrence.parse_rule("RRULE:FREQ=WEEKLY;BYDAY=MO;WKST=XX")


class Rfc5545ExampleTests(unittest.TestCase):
    """The two rules differ only in WKST and must produce different dates."""

    START = datetime(1997, 8, 5, 9, 0)

    def test_week_starting_monday(self):
        dates = _dates("RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO", self.START)

        self.assertEqual(["1997-08-05", "1997-08-10", "1997-08-19", "1997-08-24"], dates)

    def test_week_starting_sunday(self):
        dates = _dates("RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU", self.START)

        self.assertEqual(["1997-08-05", "1997-08-17", "1997-08-19", "1997-08-31"], dates)

    def test_the_two_actually_differ(self):
        monday = _dates("RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO", self.START)
        sunday = _dates("RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU", self.START)

        self.assertNotEqual(monday, sunday)


class WkstScopeTests(unittest.TestCase):
    def test_week_start_orders_days_within_a_week(self):
        # With WKST=SU the Sunday leads its week; with WKST=MO it trails.
        sunday_first = _dates(
            "RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=2;BYDAY=TU,SU;WKST=SU",
            datetime(1997, 8, 17),
        )

        self.assertEqual(["1997-08-17", "1997-08-19"], sunday_first)

    def test_no_effect_on_a_plain_weekly_rule(self):
        # With INTERVAL=1 every week is selected, so the boundary cannot matter.
        start = datetime(2026, 7, 1)
        monday = _dates("RRULE:FREQ=WEEKLY;COUNT=4;BYDAY=MO;WKST=MO", start)
        sunday = _dates("RRULE:FREQ=WEEKLY;COUNT=4;BYDAY=MO;WKST=SU", start)

        self.assertEqual(monday, sunday)

    def test_description_names_a_non_default_week_start(self):
        text = recurrence.describe("RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=SU,TU;WKST=SU")

        self.assertIn("weeks start Sunday", text)

    def test_description_stays_quiet_when_it_cannot_matter(self):
        self.assertNotIn("weeks start", recurrence.describe("RRULE:FREQ=WEEKLY;BYDAY=MO;WKST=SU"))
        self.assertNotIn("weeks start", recurrence.describe("RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"))


class DescriptionAccuracyTests(unittest.TestCase):
    def test_weekly_does_not_claim_a_position_it_ignores(self):
        # Weekly expansion drops the number, so describing "2nd Monday" while
        # returning every Monday was a lie about what would happen.
        self.assertEqual("Every week on Monday",
                         recurrence.describe("RRULE:FREQ=WEEKLY;BYDAY=2MO"))

    def test_monthly_still_names_the_position(self):
        self.assertEqual("Every month on 2nd Monday",
                         recurrence.describe("RRULE:FREQ=MONTHLY;BYDAY=2MO"))


class ValidatorAgreesWithTheEngineTests(unittest.TestCase):
    """The validator used to warn about parts the engine had learned to expand."""

    def _warnings(self, line):
        items = parse_text(line)[0]
        return [d.message for item in items for d in validate_item(item) if d.code == "W223"]

    def test_supported_keys_are_derived_from_the_engine(self):
        from lifetxt import validator

        self.assertEqual(set(recurrence.SUPPORTED_PARTS), validator._SUPPORTED_RRULE_KEYS)

    def test_expandable_rules_produce_no_warning(self):
        for rule in (
            "RRULE:FREQ=MONTHLY;BYDAY=1MO",
            "RRULE:FREQ=MONTHLY;BYMONTHDAY=-1",
            "RRULE:FREQ=YEARLY;BYMONTH=1,7;BYMONTHDAY=15",
            "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=SU,TU;WKST=SU",
            "RRULE:FREQ=YEARLY;BYDAY=-1FR",
        ):
            line = "[ ] E Meeting repeat:%s from:2026-07-06\n" % rule

            self.assertEqual([], self._warnings(line), rule)

    def test_genuinely_unsupported_parts_still_warn(self):
        self.assertTrue(self._warnings("[ ] E M repeat:RRULE:FREQ=WEEKLY;BYSETPOS=1 from:2026-07-06\n"))
        self.assertTrue(self._warnings("[ ] E M repeat:RRULE:FREQ=HOURLY from:2026-07-06\n"))

    def test_positional_byday_warns_only_where_it_is_ignored(self):
        weekly = self._warnings("[ ] E M repeat:RRULE:FREQ=WEEKLY;BYDAY=2MO from:2026-07-06\n")
        monthly = self._warnings("[ ] E M repeat:RRULE:FREQ=MONTHLY;BYDAY=2MO from:2026-07-06\n")

        self.assertTrue(weekly)
        self.assertIn("ignored for FREQ=WEEKLY", weekly[0])
        self.assertEqual([], monthly)

    def test_a_malformed_weekday_still_warns(self):
        self.assertTrue(self._warnings("[ ] E M repeat:RRULE:FREQ=WEEKLY;BYDAY=XX from:2026-07-06\n"))


ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:standup@example.com
SUMMARY:Team standup
DTSTART:20260706T090000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4
END:VEVENT
BEGIN:VEVENT
UID:once@example.com
SUMMARY:One off
DTSTART:20260710T140000
END:VEVENT
END:VCALENDAR
"""


class IcsExpansionTests(unittest.TestCase):
    def test_default_keeps_the_compact_rule(self):
        items = items_from_ics_text(ICS)

        self.assertEqual(2, len(items))
        self.assertIn("repeat:RRULE:", item_to_line(items[0]))

    def test_expanding_writes_one_record_per_occurrence(self):
        items = items_from_ics_text(ICS, expand=True)

        # Four occurrences plus the single non-recurring event.
        self.assertEqual(5, len(items))
        starts = [i.details["from"][0] for i in items[:4]]
        self.assertEqual(
            ["2026-07-06T09:00", "2026-07-08T09:00", "2026-07-13T09:00", "2026-07-15T09:00"],
            starts,
        )

    def test_occurrences_get_unique_ids(self):
        items = items_from_ics_text(ICS, expand=True)
        ids = [i.details["id"][0] for i in items]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual("standup@example.com_20260706", ids[0])

    def test_occurrences_keep_the_uid_and_anchor(self):
        first = items_from_ics_text(ICS, expand=True)[0]

        # uid: still points at the calendar event, and repeat_base records the
        # series anchor, so the instances remain traceable to their source.
        self.assertEqual("standup@example.com", first.details["uid"][0])
        self.assertEqual("2026-07-06", first.details["repeat_base"][0])

    def test_occurrences_drop_the_rule(self):
        first = items_from_ics_text(ICS, expand=True)[0]

        # Keeping repeat: would make every instance look like its own series.
        self.assertNotIn("repeat", first.details)

    def test_non_recurring_events_pass_through_unchanged(self):
        plain = items_from_ics_text(ICS, expand=True)[-1]

        self.assertEqual("once@example.com", plain.details["id"][0])
        self.assertNotIn("repeat_base", plain.details)

    def test_wkst_is_honored_through_the_import_path(self):
        text = ICS.replace(
            "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4",
            "RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU",
        ).replace("DTSTART:20260706T090000", "DTSTART:19970805T090000")

        items = items_from_ics_text(text, expand=True)
        starts = [i.details["from"][0][:10] for i in items[:4]]

        self.assertEqual(["1997-08-05", "1997-08-17", "1997-08-19", "1997-08-31"], starts)

    def test_expansion_is_bounded(self):
        unbounded = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:d@x\nSUMMARY:Daily\n"
            "DTSTART:20260101T080000\nRRULE:FREQ=DAILY\nEND:VEVENT\nEND:VCALENDAR\n"
        )

        default_window = items_from_ics_text(unbounded, expand=True)
        capped = items_from_ics_text(
            unbounded, expand=True, expand_until=datetime(2030, 1, 1)
        )

        from lifetxt.ics import DEFAULT_EXPAND_DAYS, MAX_EXPAND_OCCURRENCES

        # A year by default, and never past the hard ceiling however wide the
        # window: one runaway rule must not fill the file.
        self.assertLessEqual(len(default_window), DEFAULT_EXPAND_DAYS + 2)
        self.assertEqual(MAX_EXPAND_OCCURRENCES, len(capped))

    def test_explicit_count_wins(self):
        items = items_from_ics_text(ICS, expand=True, expand_count=2)

        self.assertEqual(2, len([i for i in items if "repeat_base" in i.details]))

    def test_an_unexpandable_rule_keeps_the_event(self):
        # Dropping a calendar entry because its rule is exotic would be far
        # worse than leaving it in the compact form.
        exotic = ICS.replace("FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4", "FREQ=SECONDLY")

        items = items_from_ics_text(exotic, expand=True)

        self.assertEqual(2, len(items))
        self.assertIn("repeat:RRULE:FREQ=SECONDLY", item_to_line(items[0]))

    def _occurrence_dates(self, extra):
        text = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x@y\nSUMMARY:Standup\n"
            "DTSTART:20260706T090000\nRRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=4\n"
            "%sEND:VEVENT\nEND:VCALENDAR\n" % extra
        )
        return [i.details["from"][0][:10] for i in items_from_ics_text(text, expand=True)]

    def test_exdate_removes_a_cancelled_occurrence(self):
        # A feed cancels one date with EXDATE. Materializing it anyway would
        # put an event on the calendar that the source already removed.
        self.assertEqual(
            ["2026-07-06", "2026-07-20", "2026-07-27"],
            self._occurrence_dates("EXDATE:20260713T090000\n"),
        )

    def test_exdate_accepts_a_comma_separated_list(self):
        self.assertEqual(
            ["2026-07-06", "2026-07-20"],
            self._occurrence_dates("EXDATE:20260713T090000,20260727T090000\n"),
        )

    def test_exdate_may_repeat(self):
        self.assertEqual(
            ["2026-07-06", "2026-07-27"],
            self._occurrence_dates("EXDATE:20260713T090000\nEXDATE:20260720T090000\n"),
        )

    def test_exdate_with_a_tzid_parameter_still_matches(self):
        self.assertEqual(
            ["2026-07-06", "2026-07-20", "2026-07-27"],
            self._occurrence_dates("EXDATE;TZID=Asia/Tokyo:20260713T090000\n"),
        )

    def test_unparseable_exdate_is_ignored_not_fatal(self):
        # A malformed exclusion must not lose the whole series.
        self.assertEqual(4, len(self._occurrence_dates("EXDATE:not-a-date\n")))

    def test_expanded_output_validates(self):
        from lifetxt.validator import validate_item

        for item in items_from_ics_text(ICS, expand=True):
            errors = [d for d in validate_item(item) if d.level == "error"]

            self.assertEqual([], errors, item_to_line(item))


if __name__ == "__main__":
    unittest.main()
