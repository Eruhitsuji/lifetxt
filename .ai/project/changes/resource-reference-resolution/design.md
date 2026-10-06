# Restricted resource-reference consumer refinement

Requirements/design refinement -> owner contract acceptance -> Ready -> schema delivery
-> developer verification -> independent security/integration review. Adaptive-default
+ W-model; Security / High; S, complexity 5 (breadth 1, dependency 1, uncertainty 1,
tests 2, operations 0). No parallel agents. Owner/accountable owner/integrator/merge
authority: Eruhitsuji. Executor and informational self-review: Codex.

Normative proposed contracts: [EN](../../../../docs/en/resource-reference-resolution.md)
and [JA](../../../../docs/ja/resource-reference-resolution.md), sections 1–8.
Parent #1101 accepted; concrete envelope/authorization approval required by #1110
is not inferred from a generic instruction to implement the task. Current delivery
is a reviewable design proposal; schema implementation must wait for that approval.

Reuse cap-resource-reference-projection-contract, cap-remote-workspace-sync-snapshot,
existing principal_registry/scopes, collaboration membership, selected workspace/source
handles, transactions, #1097 effective-origin and confined snapshot proof. Binding
remains an identity index, not authority/credential storage. Existing raw snapshot and
generic Web are not safe discovery bootstrap. Operator supplies authorized selectors
over a protected channel; a safe inventory is separate future work.

Source seams inspected: remote_access.py::principal_registry/negotiate_protocol;
remote_backend.py::_workspace_manifest; remote_web.py::remote_guard membership and
POST clock handling; remote_contracts_v6.py legacy attachment/clock contract;
schema_extensions_v32.py and release_policy.py schema/sample generator. Existing
attachment v1 schemas remain unchanged. Reserve next unused extension v33 only after
Ready; six new resource-reference-* schemas and matching contract tests use existing
bootstrap/generator, not another schema writer. Binary response has normative HTTP
bounds, not an invented JSON envelope.

Review viewpoints: requirement/AC coverage, scoped identity vs authority, IDOR/revocation,
source-wide and exact-byte CAS, policy changes, hidden association counts, raw alternate
routes/credentials/session isolation, unsupported platform, semantic vs schema validation,
fixed resource cost, middleware classification, byte-before-error/transfer abort and
bilingual consistency. Coding viewpoint: no runtime changes at proposal stage; later
closed schemas and existing extension pipeline only. Security: no credential/path echo,
no new grants or clock weakening, no false advertisement from schema-only tests.

Verification viewpoints: EN/JA fixtures and limits/catalog parity, JSON round trips,
positive/negative identifier grammar, local links, YAML parse/traceability/package
checks, legacy schema/diff nonchanges and existing attachment/Remote compatibility.
Do not label offline design checks as runtime enforcement or schema validation.

Independent human design/security and integration review remain required. Shared files
receive only this task's entries; owner resolves conflicts. Recheck origin/main before
push; merge new main semantically if necessary. Revert this docs/package/registry-only
proposal for rollback. Schema phase cannot start or final completion be claimed while
concrete approval is pending.
