# Main CI recovery contract

The current failure is an optional test dependency boundary violation, not a
runtime defect. Quick adapter loops run CLI/TUI/MCP regardless of Web extras;
Web and remote TUI comparisons join only when FastAPI and its TestClient HTTP
transport are available. Three Web-only tests explicitly skip otherwise. The
Web extras lane runs the complete original surface guarantees.

Reuse the no-Web job for PRs touching tests, Python runtime modules or scripts.
Reuse dev-only coverage for changes to dependency declarations, coverage controls
or CI workflows. Empty change lists select both. These are conservative categories,
not the full main suite: OS, Python-version and optional-version matrices remain
main-only. Docs-only selects neither. PR aggregation explicitly requires selected
jobs to succeed and unselected jobs to skip. Coverage stays dev-only; optional
Web cases skip and the Web extras lane owns their verification. Baselines and
thresholds remain unchanged.

A read-only main-health job emits warnings and a summary on each PR. An open
Incident, a failed/pending latest main run, or unknown health requires recovery-first
handling. The check is advisory about main health, so a recovery PR's own checks
can pass. Merge Authority must recheck health just before merge, defer ordinary
features and prioritize a reviewed repair. This documented process supplies the
human decision boundary rather than a blanket red-main block.

The push-only visibility job paginates open issues, jobs and associated PRs.
It filters source PRs to the actual merged main commit, includes failed job/step
links and artifacts, updates the Incident body and appends every subsequent
failure. Source PR lookup failure retains commit evidence. Only the latest main
push run may mutate Incident state; only full compatibility success may close it.
A later pending run therefore prevents an older run from falsely reporting recovery.
No raw logs or credentials are copied to Issues. API responses are used as data,
not shell commands; the PR advisory needs no checkout or issue writes.

Rollback: human-approved revert of this PR. Do not remove no-Web assurance or
lower coverage thresholds as mitigation. No product or data migration is needed.
