# Decisions

Reuse cap-ci-responsibility-separation and its empty-input full route.
One S task addresses a single failure boundary; no unrelated CI changes.
Maintenance flow with W-model verification. High assurance because CI is shared.
Implementation, test, integration and fail-safe security review remain human
review boundaries. CI/main verification is pending; this package does not claim
that main has recovered. The Incident stays open until full main CI succeeds.
