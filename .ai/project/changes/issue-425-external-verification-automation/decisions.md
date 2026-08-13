# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-08-13 | Use one standard-library Python runner across Windows, WSL, Linux, and macOS | Eruhitsuji / Codex | Separate PowerShell and Bash implementations | One implementation keeps evidence semantics and redaction consistent across hosts | Verify each supported host through its existing release-evidence issue |
| 2026-08-13 | Reuse `scripts/run_ci_like.py --profile release` instead of duplicating artifact verification | Eruhitsuji / Codex | New build/install implementation | The existing release profile is already authoritative and tested | Keep the new runner orchestration-only |
| 2026-08-13 | Aggregate all automated output into one JSON file and leave external/interactive scenarios incomplete | Eruhitsuji / Codex | Multiple logs; infer pass from local tests | Minimizes operator work without weakening real-environment evidence rules | Future RC dossier aggregation may consume these bundles after evidence format is proven |
