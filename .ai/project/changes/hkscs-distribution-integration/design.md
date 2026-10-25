# Custom distribution integration

Operations / assurance escalated from Standard to High for score7, M (2/2/1/2/0).
A single explicit runtime/source/artifact byte contract cannot safely be split
into independent partially accepted builders. Public adoption approval and
independent review remain outside this implementation. One Issue #1417, one
branch ops/hkscs-distribution-integration, base main 0b7fd88f, final PR to main.
Owner/Integrator Eruhitsuji, Implementer Codex, no parallel executor.
Phase design → implementation → developer integration verification → PR review.
Review: source-specific licence scope, modified MPL source availability, byte
allowlist, CSP/private text, failure/rollback and human authority. Test: actual
candidate and complete sources, rehashed mutations, 16KiB/CJK boundaries and
Worker recovery/browser/network/storage, existing source/notice/site regression.
Coding/security: reuse fixed hashes and source lock, no downloaded code execution,
strict local inputs, new output directory, reject symlinks/unlisted bytes, no CDN,
no silent old-runtime fallback, retain approval=false and existing human gate.

Custom sources replace the upstream CPython archive with the verified curated
one, and replace Pyodide with its modified source plus build helper. All other
required archives and licences remain pinned. Never ship the old original-core
archive as custom source proof or claim custom bytes match the official release.
A dedicated fixed custom source lock binds derived archive hashes and changed
members. The complete expected artifact is reconstructed from reviewed sources;
regenerating a manifest cannot bless changed script/source/runtime/notice bytes.
The existing official artifact profile remains compatible and separate. The
custom profile uses the existing publication evidence evaluator with its actual
curated CPython binding and unresolved independent acceptance statuses.
Rollback: human-reviewed revert, never deployed by this work.
