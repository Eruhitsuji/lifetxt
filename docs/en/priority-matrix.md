# Importance and priority matrix

Use optional `importance:high`, `importance:normal`, or `importance:low` on tasks. This is your judgment, stored in `life.txt`. Existing `priority:` metadata remains a separate, explicit execution/order preference under its existing contract. The matrix never converts between `priority:` and `importance:` and never uses `priority:` to classify a task.

```text
[ ] T "Submit report" importance:high due:2026-09-27
```

These fields answer different questions:

| Field | Meaning | Stored or derived |
| --- | --- | --- |
| `priority:` | Your explicit ordering preference, honored by existing priority-aware views such as `next` | Stored in `life.txt` |
| `importance:` | Your explicit judgment of how important the task is | Stored in `life.txt` |
| Urgency | Time pressure derived from `due:` and the evaluation time | Derived each run |
| Q1–Q4 | Attention category derived from importance and urgency | Derived each run; not saved |

For example, `priority:C importance:high` and `priority:A importance:low` are both valid. Changing only `priority:` does not change urgency or quadrant. If `importance:` is missing or invalid, the task remains `unclassified`, even with `priority:A`. Existing views may use `priority:` for their own ordering; matrix groups retain source order and are not sorted by `priority:`.

Run `lifetxt list --matrix life.txt` (or `python -m lifetxt list --matrix life.txt`). Use `--quadrant Q1` to filter, `--json` for structured output, and `--horizon` to show the next time-based quadrant transition. Only open (`[ ]`) and in-progress (`[/]`) tasks (`T`) appear. Completed, canceled, deferred, pending, and non-task records are excluded.

Priority Horizon is derived read-only context: it shows the current group and the next scheduled quadrant change, if one exists. For example, a high-importance task with a deadline more than seven days away is currently Q2 and moves to Q1 when its deadline enters the existing seven-day urgency window. With `--horizon --json`, rows include `next_at` and `next_quadrant`; both are `null` when no scheduled transition exists. No horizon value is written to `life.txt`. Tasks without a usable future deadline, tasks already in an urgent quadrant, and unclassified tasks have no scheduled transition.

Urgency is recomputed on each run from `due:` in the configured workspace timezone: overdue = critical; due within 24 hours = high; due within 7 days = normal; later or without a due date = low. Date-only deadlines expire at the end of their local calendar day. Boundaries at exactly 24 hours and 7 days belong to the nearer category. Explicit offsets are honored. Critical, high, and normal count as urgent; only `importance:high` counts as important. These produce Q1 (both), Q2 (important only), Q3 (urgent only), and Q4 (neither). Missing, invalid, or repeated importance and malformed due values appear in `unclassified`. `check` warns on invalid or repeated importance. Source order is preserved within each group. The derived category is never saved to the file.

Q1–Q4 are not replacements for the existing `priority:` field, and the matrix does not calculate an overall score or recommended execution order.
