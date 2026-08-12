# Stable Diagnostic Matrix

This matrix records the current diagnostic boundary for #324. Diagnostic codes
and categories are automation-facing; human-readable messages and hints may be
improved without changing the code, category, or structured field meaning.

| Failure area | Current code source | Contract status | Remaining work |
| --- | --- | --- | --- |
| parser syntax and body ambiguity | `PARSER_DIAGNOSTIC_HINTS`, `E001`-`E022` | stable code/hint registry | add end spans where parser source boundaries are available |
| validation and references | validator and links diagnostics | stable category mapping | audit every release-supported record family for dedicated codes |
| canonical format policy | `F101`-`F109` | stable format-policy diagnostics | connect migration refusal to the same documented compatibility table |
| mutation conflicts and revision failures | mutation/surface runtime contracts | stable conflict/revision responses | preserve parity across Web and MCP envelopes |
| configuration/profile/include failures | config validation | mixed | assign dedicated deterministic codes for remaining message-only failures |
| remote clock/recovery evidence | remote contract schemas and diagnostics | supported only where explicitly advertised | require real-environment evidence before promoting to stable |
| deferred/experimental features | support matrix | not stable | do not add stable codes until the feature is promoted |

Unknown diagnostic fields must be tolerated by consumers. Existing codes must
not be reused for a different failure meaning; intentional changes require a
compatibility-policy and migration decision.
