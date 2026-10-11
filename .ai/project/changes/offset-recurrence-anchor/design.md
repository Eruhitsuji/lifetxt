# Fixed-offset boundary repair

Agenda combines the actual authored date and clock through parse_anchored_time.
No current-date anchoring or host conversion occurs before combination. Floating
clock candidates derive dates in the clock's authored offset, so a negative
offset crossing into the next configured day also selects the preceding authored
date. One-sided floating queries remain excluded.

The shared recurrence engine uses timetz and LifeDateTime.combine to retain the
authored representation. Its comparisons and agenda overlap/step calculations
use offset_comparison_pair: naive-only pairs remain wall-time values; a mixed
pair localizes the naive side with the existing resolved timezone policy; aware
pairs compare UTC instants. Range sentinels remain unbounded without overflowing
localization. Only comparison copies are normalized; serialization keeps offsets.

Do not replace parse_time or LifeDateTime's global legacy comparisons: unrelated
callers explicitly depend on those contracts. No third-party dependency or new
public response field is introduced. Complexity remains linear in emitted
candidates, subject to existing ceilings, with constant-time timezone comparison.

Shared consumers: CLI agenda/time filters, Web API, MCP, TUI, Remote, reports and
command center use agenda_records/item_time_matches. Freebusy uses nonrecurring
matches; Daily Flow already normalizes through timezone_policy independently.
Existing consumer suites supply integration coverage, not physical-device QA.

The first full suite found two AI catalog output changes. The current expected
agenda outputs are remeasured while agenda_history preserves the source evidence.
The fixtures and historical check provenance are not altered.
