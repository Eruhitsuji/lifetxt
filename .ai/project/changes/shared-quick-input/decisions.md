# Decisions

The issue and its mandatory horizontal-expansion comment authorize the additive API
and all applicable Quick adapters. Parser recognition uses one centralized leading
bracket rule (previously duplicated in Web); no second Format grammar. Explicit
structured/raw/import operations retain their contracts. Independent approval remains
pending for the final PR. No runtime dependency, auth, format, or persistence change.

Self-review corrections: remove UI format detectors and Focus's hand serializer;
use all loaded local TUI items rather than visible rows for IDs; reject repeated
IDs within a full record using authoritative ID diagnostics; keep CLI tag flag
merging opt-in so Web/MCP repeated shorthand values remain intact. Update the
Web assembly regression hash only for the reviewed, intentional fragment changes.

Publication is blocked by automatic approval review despite matching the user-named
public Eruhitsuji/lifetxt repository and the connected owner's permissions. No
remote branch was created. Explicit user approval for public push and PR creation
is required before retrying; independent review and merge approval remain separate.
Local full-regression evidence is complete. PR traceability links remain null until
the PR exists; fill them before the final CI-triggering push.
