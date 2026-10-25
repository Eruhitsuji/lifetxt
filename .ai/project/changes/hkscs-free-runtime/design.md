# HKSCS-free runtime candidate

Operations/High, adaptive Kanban and W-model. Phase: architecture/design →
implementation and developer verification → independent PR review. M score6
(scope1/dependency2/uncertainty1/test2/ops0): pinned source curation, isolated
build and absence proof are one vertical slice. Adoption into the website's
complete distribution contract remains #1398/#1400 work. Reuse
cap-official-website, the source lock, Core fixtures and PoC adapter.

Source: main 946d8c04. Branch ops/hkscs-free-runtime; PR base main.
Owner/Integrator Eruhitsuji; implementer Codex. No parallel executor.
Review viewpoints: source and license provenance, object inclusion, no fallback,
compatibility, honest evidence scope. Test viewpoints: input tampering,
incomplete source, repeatable archive bytes, actual compiled object/runtime
absence, Japanese and existing Core cases. Coding/security: fixed hashes,
validated tar paths/types, no archive traversal, explicit local SDK, fresh output
only, no automatic runtime package installation or publication approval.

Remove seven upstream files and the two codec aliases, preserve licensing and
historical documentation. The generator's reference to HKSCS is not table data;
it is retained for upstream attribution, but must not regenerate removed data.
Disable _codecs_hk in Pyodide Setup.local before compiling. Fail if curated
CPython cache disappears; do not redownload the official HKSCS-containing input.
Retain the original upstream SHA and the curated archive SHA separately.

A WASM execution probe must reject builtin/module/codec availability and retain
Japanese codecs. Pair it with compiler-source, generated module table, static
library and stdlib checks. Symbol absence alone is insufficient. The candidate
is not installed into the existing audited official runtime: its distinct bytes
require a new provenance/distribution binding before publication. Existing N-7
source-specific gates stay unchanged. Both actual publication flags stay false.

Rollback: human-reviewed revert; there is no deployment in this change.
