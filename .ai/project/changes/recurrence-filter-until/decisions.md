# Approved decisions

Owner approved the concrete proposal recorded in #1227 on 2026-10-11. This engine task precedes diagnostic routing #1237. Intersections/empty sets replace union/anchor fallback; weekly BYMONTHDAY is rejected. Date-only UNTIL covers the full final day; offset UNTIL denotes an instant. Existing saved text is retained. Human implementation/integration review and merge remain pending.

An old weekly positional-description assertion now expects an explicit rejection under the approved combination contract; valid weekly description assertions remain. Regression testing exposed empty-period overflow, fixed in the same cause/scope with period bounds.
