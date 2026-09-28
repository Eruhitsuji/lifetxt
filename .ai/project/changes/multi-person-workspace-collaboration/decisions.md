# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-28 | Store roles in each named workspace's `collaboration.members` map, keyed by existing Remote principal ID | Codex, per approved #983 contract | Deployment-global role; life.txt ACL fields; second credential registry | Keeps workspace access separate from identity and record semantics | #984 |
| 2026-09-28 | Intersect workspace operation permissions with authenticated principal scopes and existing item/source rules | Codex, per approved #983 contract | Let owner/editor roles replace global scopes | Prevents workspace membership from escalating existing authority | #985/#986 |
| 2026-09-28 | Use exact config revision CAS through `write_config` and refuse a last-active-owner transition | Codex | Workspace content revision; last-write-wins; remote config editing | Configuration and content revisions protect different authorities; CAS prevents silent member-update loss | #986 |
| 2026-09-28 | Use a single protocol-v2 member route plus explicit operation payload and one Remote CLI command per operation | Codex | Separate unversioned routes or client-side config editing | Keeps all mutations behind the same authenticated API and config CAS | #986 |
| 2026-09-28 | Add collaboration controls to the authenticated Remote page, with server capability gating and no browser-side policy authority | Codex | Duplicate authorization in the standard Web client | Existing Remote page already owns authenticated session, CSRF, and capability negotiation | #987 |
| 2026-09-28 | Display actor IDs from Native History records and retain the stable ID as fallback | Codex | Infer actor from assignee/person or rewrite history on membership changes | Historical actor is authoritative evidence and remains stable across membership changes | #987 |
