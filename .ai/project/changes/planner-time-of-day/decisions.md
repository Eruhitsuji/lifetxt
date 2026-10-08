# Decisions

Owner approved the default display policy on 2026-10-09 JST, then approved
custom browser-local start times and the additive current_datetime API scope.
Approval and the execution contract are recorded on #1149.

Defaults: 05:00 / 11:00 / 18:00, ordered within a day; Evening wraps midnight.
Manual mode lives in memory. Custom bands extend existing versioned browser
preferences; no server config registry key, config explain entry, life.txt field
or migration applies. Older clients may drop the added local field when saving.
Standard assurance remains appropriate: bounded additive read data, no new auth,
authoritative writes or external dependencies. Human review/merge remain pending.
