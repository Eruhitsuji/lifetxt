# Decisions

- #1099 owner approval is the design basis; the current #1100 request authorizes scoped documentation preparation. Final contract adoption is the human PR review/merge decision.
- Use exact att:v1: + 32 lowercase hex, 128 independently random bits; receipt UUIDs and deterministic path/content identities cannot be promoted into resolver IDs.
- Bind one workspace/source/item/resource-association generation; independently issue across workspaces/installations. Never revive detached IDs on restore or reconstruction.
- Project exact existing source/byte validators through scoped random rev:v1 tokens. This preserves source-wide CAS semantics without cross-workspace source digest disclosure. Optional full byte digest needs separate permission.
- Allow only file descriptors initially. Existing local/read-only enrollment cannot rewrite life.txt, invent item identity, disambiguate by line/ordinal or fall back to a path.
- Reconstruct all restricted surfaces from typed/classified projected data or deny. A safe upload receipt is not a complete Web/Remote disclosure boundary.
- Choose opt-in resource-reference-v1; a later attachment v2 may carry it. Deny legacy/raw alternatives to restricted principals rather than downgrade. Preserve operator-selected local MCP and existing v1 schemas.
- Defer schema until an approved concrete consumer. #1101 owns lookup/resolver/byte-operation refinement; #1102 profiles and #1103 SSRF/fetch remain separate.
- Self-review corrections: explicitly scope revision tokens to stop content-hash correlation, distinguish receipt UUID entropy, invalidate uncertain association continuity and restore epochs, require search over projected data and denial of alternate raw routes.
