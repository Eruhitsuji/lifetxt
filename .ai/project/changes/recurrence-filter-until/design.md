# Shared filter and UNTIL repair

Reuse recurrence.py and existing offset_comparison_pair. Select BYDAY and BYMONTHDAY independently and intersect only when both are present; no matching explicit set never inherits the anchor. Plain unfiltered clamping stays compatible. WKST and weekday order are unchanged. Reject meaningless weekly BYMONTHDAY and daily/weekly positional BYDAY at parsing.

A single UNTIL parser serves shared rules and agenda. Date-only ends cover 23:59:59.999999; UTC/numeric offsets remain authored and compare as instants in resolved timezone. Completion uses the same comparison seam. Empty month/year periods must check the earliest bound before generating, and stop at datetime.max.year: a generator that yields no candidates cannot let expand's per-candidate bound enforce termination.

Space is O(31) per month; time is O(31 * bounded periods). No new dependencies, response fields, saved-data migration or authorization behavior. Named-zone/DST recurrence generation is unchanged; the existing timezone policy interprets naive comparison bounds.

Review viewpoints: filter truth, empty periods, COUNT/window/UNTIL and instant comparison, parser compatibility and bounded computation. Tests use independent expected dates and exact timezone boundaries.
