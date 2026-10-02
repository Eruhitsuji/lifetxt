# Decisions

- Extend cap-ci-responsibility-separation and preserve req-ci-pr-main-responsibility-separation.
- Keep one M issue/PR: the optional-boundary fix, selective aggregate gate and
  recovery contract must be verified and reverted coherently against shared ci.yml.
- Complexity 6/10; High assurance as specified by #1026. Owner/integrator is Eruhitsuji.
- Reuse full existing no-Web suite for conservative Python/test categories rather
  than infer imported dependencies or execute only directly changed tests, which
  could miss transitive boundary failures. Coverage is narrower to avoid doubling
  every PR. Main matrices and release/distribution are unchanged.
- Keep coverage dev-only and baseline unchanged. Web guarantees remain in extras CI.
- Recovery-first is mandatory merge governance plus an always-visible PR advisory;
  no automatic revert or all-PR red-main failure. Explicit source-PR resolution can
  degrade to merge-commit evidence, while Incident write errors remain visible.
- CI design approval, independent implementation/integration review and human merge
  remain pending on the final PR. Implementer self-review is not final approval.
