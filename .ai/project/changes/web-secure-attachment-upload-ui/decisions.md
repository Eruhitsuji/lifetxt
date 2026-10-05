# Decisions

- Explicit user request authorizes implementation and PR creation. #1095 merged as #1104; current base 09919a97. Refine Inbox to Ready before code edits. Phase implementation, Feature/High, owner Eruhitsuji, implementer Codex; independent human review/merge approval still required.
- Size M, complexity 7: breadth2 + internal dependency1 + uncertainty0 + browser integration effort2 + write risk2. Picker/precondition/pending/failure/receipt form one complete write interaction; server, resolver and global projection already split into #1095/#1100/#1101.
- Extend existing drawer and browser-safe upload capabilities. No new endpoint, dependency, config, Format or provider integration. Historical first-Stable freeze does not override this explicit post-Stable task; no release/deployment/merge performed.
- Upload is in Overview rather than the edit form to preserve unsaved edit behavior. Supplement initial write scope with JS12 close/edit/done lifecycle cleanup. Existing extracted-function tests are supported by checking helper availability.
- Read sandwich rather than changing server read contracts: discard changing/mismatched snapshots and require explicit user refresh. No silent submission with a newer revision.
- Fixed text error guidance and a path-free receipt; raw record/editor surfaces remain explicit operator tools. Latest receipt is session-only metadata, not an authoritative attachment listing or a resolver token.

- Browser self-review found that existing item-filter URL refresh dropped `lang`, so later dynamic upload controls reverted to English despite a Japanese page. Preserve `lang` alongside existing view/theme parameters in JS04; one bounded root-cause fix, evidenced by EN/JA real browser flows. Supplemental scope recorded in #1096.

- Self-review corrections: use the exact policy field `max_upload_bytes`; release native selection on close/edit/done transitions; retain `lang` through filter URL updates; distinguish failed availability reads from an uncertain POST outcome. No blocking self-review findings remain.
- Browser fixture invokes the public compatibility bootstrap before importing the ASGI factory, matching `lifetxt serve`. Fault status/timing injection is test-only and explicitly separated from real 201/409/415 server checks. Test waits require a fully refreshed, non-pending view rather than an intermediate success receipt.
- Chrome for Testing could not run with this environment’s Unix-socket restrictions; Chromium headless shell 141.0.7390.37 ran the native/CDP browser checks. Browser tooling was installed only in the execution environment, with no project dependency change.

- Full regression found the existing selection-contrast stylesheet must stay last. Move the new upload stylesheet before CSS05; preserve the existing assertion. Also distinguish remote clock errors from source-revision conflicts with localized device/server clock guidance and a targeted behavior test.
