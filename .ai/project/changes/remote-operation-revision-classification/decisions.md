# Decisions

- Classify the correction as Bug / High because it affects revision migration
  admission and a security-sensitive Remote operational route.
- Treat login, logout, write-check, and backup-run admission as operational;
  classify ticket mutations as authoritative.
- Reuse the existing Web no-revision registry rather than introduce a third
  route-exclusion mechanism.
- Require a route-inventory regression test so future mutating Remote routes
  cannot be added without an explicit classification decision.
