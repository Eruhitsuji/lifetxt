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

The user explicitly approved public publication and PR creation on 2026-10-02.
Git transport lacked write credentials, so the connected GitHub contents API
published the verified files to the feature branch. Before PR creation, its tree
75bd65dc71ab56d90fc3ba724335af7c0b911114 exactly matched the local verified
publication tree. PR #1023 is linked in the registries and change package before
the final CI-triggering update. Independent review and merge approval remain
separate and pending; publication approval does not authorize merging.
