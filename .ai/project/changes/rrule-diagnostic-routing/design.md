# RRULE diagnostic and agenda routing

Keep established diagnostics and use shared parse_rule for otherwise-clean supported values/combinations. Agenda uses rule_for_item for RRULE normalization, rejects invalid/unsupported rules before fallback, and retains only their authored anchor as a normal match. Valid BY-bearing RRULEs always use shared expansion, including plain monthly/yearly weekdays. Shortcuts keep legacy arithmetic, including weekdays, which is not a shared-engine short name.

No new engine/dependency, mutation or authorization changes. W223 remains warning-only by default. rrule preview keeps its existing unsupported-key partial preview contract and is explicitly documented separately. Do not mistake preview for full agenda support.

A catalog regression found PAT-REC-007's old empty agenda is now one ordinary authored anchor with no generated recurrence. Store the old output in agenda_history and record measured current output; fixture/check provenance stays intact. PAT-REC-001's weekdays result stays unchanged after a shortcut regression was repaired.

Review/testing: valid/plain/positional filters, invalid values/combinations/unsupported parts, default/error exit, COUNT/window/UNTIL, completion, custom-key permissiveness, input-to-meaning catalog inspection. Complexity remains bounded by the existing engine; invalid rules generate no series.
