# Resource-reference projection contract

## Phase, method and authority

Architecture/design -> scoped documentation delivery -> developer verification;
adaptive-default + W-model, Security / High, size S (one shared contract).
Owner/integrator: Eruhitsuji. Executor: Codex. #1099 owner approval and the current
#1100-through-PR instruction authorize preparation. Independent human contract
acceptance and integration review remain pending; no merge authorization inferred.

## Normative deliverable and reuse

- [English](../../../../docs/en/resource-reference-projection.md)
- [Japanese](../../../../docs/ja/resource-reference-projection.md)
- req-resource-reference-projection -> cap-resource-reference-projection-contract -> #1100.
- Extend cap-web-browser-safe-attachment-upload and cap-web-secure-attachment-upload-ui
  as prospective consumers; their receipt IDs are not resolver references.
- Reuse cap-remote-workspace-sync-snapshot as workspace/source disclosure seam,
  existing principal/action authorization, mutation CAS and attachment transactions.
- No new authority engine, writer, endpoint, binding persistence or secret store.

## Source review seams

| Source | Checked meaning |
| --- | --- |
| lifetxt/attachments.py | HASH_LENGTH=16; local file/dir and tree hash compatibility. |
| lifetxt/attachment_transactions.py | resolve_attachment_target, attachment_revision, source-wide item_revision, journal transactions and open plan. |
| lifetxt/web_attachment_upload.py | Allowlisted path-free receipt; uuid receipt identifier differs from future 128 random-bit lookup ID. |
| lifetxt/webapp.py | api_item includes source/text/details/Markdown; raw re-fetch remains outside new contract. |
| lifetxt/remote_backend.py | _workspace_manifest and _item_rows: opaque source/workspace, recursive redaction and raw-field removal seams. |
| lifetxt/remote_access.py | Current authorization/redaction/capabilities are reusable but do not classify every capability URL. |
| lifetxt/remote_contracts_v6.py and dist/schemas/attachment-*-v1.schema.json | Legacy path/chunk/open-plan contract unchanged. |

## Review and test viewpoints

Requirements: map every #1100 acceptance criterion to numbered EN/JA sections.
Design/security: identity vs authority/revision, IDOR, cross-workspace correlation,
root/race constraints, removal/recreation, restore/revocation, read-only/id-less,
all disclosure surfaces, immutable existing v1 and no silent downgrade.
Coding: no runtime changes; typed allowlists and version grammar are explicit.
Verification: parse JSON examples, boundary grammar/revision checks, bilingual
fixture parity, YAML/reference/local links, existing attachment/Remote compatibility,
package/traceability gates, release docs and diff scope. No new implementation-mirroring
tests or schema: concrete consumer approval is absent. Offline example inspection
is not proof of runtime authorization enforcement.
Operations: no deployment or credential handling; revert docs/package/registry only.
High human security/design and integration reviews must inspect the latest PR head.
