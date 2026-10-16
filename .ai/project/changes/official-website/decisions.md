# Decisions

- The 2026-10-17 request to implement #1350 approves the proposed same-repository website/, bilingual static introduction, project URL and manual deployment boundary. It does not authorize live publication.
- Use dependency-free static generation rather than a framework: small public pages, no client state or server/API need. Canonical docs remain in docs/.
- Root Japanese plus stable /ja/ and /en/ paths; no browser-language redirects, storage or cookies. Language switching retains page identity.
- Three tracked units: #1351 content/build/validation; #1352 publication operations; #1353 public acceptance/promotion after deployment. Each implementation issue has a PR to main. No permanent next/develop branch.
- Implementer self-review is recorded as verification only. Independent review remains assigned to Eruhitsuji; no AI self-approval or merge.
- Rollback: human-reviewed revert and re-publication after separate owner approval. No user data migration.
