# Decisions

- #1309 design and #1315 proof contract were approved; #1322 merged before work.
- #1316 owns only the Core producer, with exact write scope refined in the Issue.
- Both wheel and sdist get clean-install smoke; the latter rebuilds only an
  installation wheel, never replaces the retained publish wheel.
- Preserve existing release.yml and proof schema; omit intermediate SHA256SUMS
  from the four-role payload rather than create a competing canonical writer.
- Independent reviews and human merge remain pending; no release approval granted.
