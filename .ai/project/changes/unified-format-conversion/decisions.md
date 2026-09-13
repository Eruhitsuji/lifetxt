# Decisions

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-13 | Use one text-only shared conversion core | Future `/v1/convert` can reuse domain code without importing CLI or HTTP concerns |
| 2026-09-13 | Support all sources to life/JSON/JSONL/CSV, but only life to ICS | Shared items preserve the first four representations; ICS is event-only and needs a deliberate loss boundary |
| 2026-09-13 | Reject lossy ICS in `convert`, preserve legacy `to-ics` behavior | New canonical contracts fail loudly while existing scripts remain compatible |
| 2026-09-13 | Keep sqlite/lifetxtz outside this initial core | They are binary interchange/archive workflows and do not fit stdin/stdout textual conversion |
