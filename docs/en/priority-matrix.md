# Importance and priority matrix

Use optional `importance:high`, `importance:normal`, or `importance:low` on tasks. This is your judgment, stored in `life.txt`. Existing `priority:` metadata remains separate and is not interpreted as importance.

```text
[ ] T "Submit report" importance:high due:2026-09-27
```

Run `lifetxt list --matrix life.txt` (or `python -m lifetxt list --matrix life.txt`). Use `--quadrant Q1` to filter and `--json` for structured output. Only open (`[ ]`) and in-progress (`[/]`) tasks (`T`) appear. Completed, canceled, deferred, pending, and non-task records are excluded.

Urgency is recomputed on each run from `due:` in the configured workspace timezone: overdue = critical; due within 24 hours = high; due within 7 days = normal; later or without a due date = low. Date-only deadlines expire at the end of their local calendar day. Boundaries at exactly 24 hours and 7 days belong to the nearer category. Explicit offsets are honored. Critical, high, and normal count as urgent; only `importance:high` counts as important. These produce Q1 (both), Q2 (important only), Q3 (urgent only), and Q4 (neither). Missing, invalid, or repeated importance and malformed due values appear in `unclassified`. `check` warns on invalid or repeated importance. Source order is preserved within each group. The derived category is never saved to the file.
