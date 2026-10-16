# Decisions

- The 2026-10-17 request to implement #1350 approves the proposed same-repository website/, bilingual static introduction, project URL and manual deployment boundary. It does not authorize live publication.
- Use dependency-free static generation rather than a framework: small public pages, no client state or server/API need. Canonical docs remain in docs/.
- Root Japanese plus stable /ja/ and /en/ paths; no browser-language redirects, storage or cookies. Language switching retains page identity.
- Three tracked units: #1351 content/build/validation; #1352 publication operations; #1353 public acceptance/promotion after deployment. Each implementation issue has a PR to main. No permanent next/develop branch.
- Implementer self-review is recorded as verification only. Independent review remains assigned to Eruhitsuji; no AI self-approval or merge.
- Rollback: human-reviewed revert and re-publication after separate owner approval. No user data migration.

- #1352 operations is High assurance because GitHub Actions permissions and deployment are affected. Its implementation and integration/operations review stages are separate and pending; execution does not assert acceptance of risk.
- No automatic deploy on merge/push, and no configure-pages enablement. First publication requires Owner setup and approval. Public read-only environment inspection needs no token. A sole maintainer may initiate and explicitly approve deployment; this is not source self-approval.

- #1353 Owner request (2026-10-17) supersedes the initial Japanese root: render English directly, retain /ja/ and /en/, and use English deep-page x-default. No implicit redirects or browser detection.
- First publication is confirmed by run 38977955823 and successful live HTTP body checks at main a64e38b3; see public-acceptance.md. Source changes in #1353 require a separate reviewed merge/deployment.
- #1353 request authorizes scoped implementation and README promotion after HTTP verification. Live homepage metadata, deployment, merge and residual manual acceptance remain human actions; browser-local checker investigation is #1356.
