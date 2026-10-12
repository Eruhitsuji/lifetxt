# Decisions

User requested #1287 implementation on 2026-10-12. Reuse the actual existing
scripts/merge_sha256sums.py; the earlier issue used the wrong helper filename,
which is corrected in the issue. Do not swallow an error downloading a declared
manifest. Do not claim race-free cross-workflow publication; final reconciliation
is owned by the separate #911 release operation. No tags or assets are changed
in this task. Independent reviewer/integrator and merge authority: Eruhitsuji.
