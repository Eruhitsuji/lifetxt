# Decisions and review

Owner approved the proposed #1225/#1226/#1227 scopes on 2026-10-11. #1227 remains
an investigation, not authorization to redefine invalid-rule expansion. M size
keeps both localized causes and their common instant-equivalence matrix together.

Self-review found and fixed a same-cause negative-offset floating-date boundary
and covered a mixed aware/naive interval duration. A sibling date-only until value
is parsed at midnight by rule_for_item, unlike RRULE UNTIL's inclusive day end;
this independent historical inconsistency belongs to #1227, not this repair.
Likewise ordinary monthly/yearly BYDAY dispatch, malformed supported-key fallback,
ordinal out-of-range fallback and RFC filter algebra remain tracked there.

Security review: read-only parsing and comparison, no external IO, secrets,
new dependencies, authentication or mutation changes. Malformed clocks still
produce no anchor. Existing DST localization rejects ambiguous/nonexistent naive
boundaries instead of guessing. No named-zone/DST recurrence redesign claimed.

Documentation merge reconciled equivalent earlier local and published commits by
keeping the complete latest documentation branch, including new main's catalog
work and PR linkage. No independently authored runtime changes were discarded.

Implementer self-review is not independent approval. Human implementation and
integration review must inspect the final PR head before merge.
