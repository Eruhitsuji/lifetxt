# Design: explicit external fetch/import policy

## Scope and architecture

Task A (#1129) persists the owner-accepted #1103 design in
[English](../../../../docs/en/external-resource-fetch-policy.md) and
[Japanese](../../../../docs/ja/external-resource-fetch-policy.md).
The same twelve sections, L1-L8 budgets, N01-N17 negative cases and internal JSON
intent example are used in both languages. No usable config/schema/API is emitted.

The trust boundaries are: authored reference versus network operation; current
principal/workspace/item grants versus profile/destination authority; DNS answers
versus actual socket peer; direct connection versus translated/proxy egress;
remote input versus bounded complete bytes; fetched bytes versus CAS-guarded local
commit; internal recovery/secret material versus projected external output.

## Reuse and integration

Reuse cap-web-browser-safe-attachment-upload and cap-resource-reference-runtime
contracts, attachment_transactions.put_attachment, multi_target and
transaction_journal. Existing auth/membership/read-only/write-clock/source CAS
remain authoritative. A lookup, mailbox envelope or receipt supplies no grant.
A distinct design-only capability documents requirements, never runtime support.
Shared registries receive one new entry each; existing entries are not remapped.
Main updates are merged before the final push and independently reviewed.

## Review and verification

AC1-AC11 map to the bilingual section list in verification.yml. Mechanically check
section numbering, JSON parity and full hash length, L/N IDs and budget rows, local
links, YAML structure/unique capability, allowed changed paths and whitespace.
Manually compare all twelve sections and negative outcomes for EN/JA semantic
agreement, authority/peer/cancellation/recovery boundaries and scope preservation.
Run existing governance and targeted compatibility checks; record actual skip
counts. Prose/matrix tests cannot certify the unimplemented connector.

Independent human latest-head design/security/integration review remains pending.
The accepted investigation is not a review of the final PR. Consumer enablement
requires controlled network fixtures and deployed egress verification under B-D.

## Operations and rollback

This change installs no service, selects no provider/destination and changes no
secret or data. Revert only these documentation/package/registry additions.
No runtime rollback, deletion or migration is needed. Future consumers need their
own explicit disable-before-rollback, committed-outcome recovery and storage plans.
