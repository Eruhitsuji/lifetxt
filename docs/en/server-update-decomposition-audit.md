# Server Update Decomposition Audit

Issue: #374  
Implementation follow-up: #389

## Responsibility Map

| Cluster | Current symbols/tests | Coupling | Decision |
| --- | --- | --- | --- |
| Configuration validation | `load_config`, validation helpers, `LoadConfigTests` | Input policy and command safety | Keep at module boundary |
| File integrity and backup | `hash_paths`, `create_backup`, `HashAndBackupTests` | Data safety and filesystem state | Preserve together initially |
| Command/service execution | `_run`, service helpers, installer helpers | Structured argv and process lifecycle | High-risk; do not split first |
| Health readiness | `check_health`, `wait_for_health`, `CheckHealthTests` | Bounded timing and network I/O | Separate only with timing tests |
| Diff/review parsing | `gather_diff_summary`, `classify_risk`, `format_review_block` | Pure report transformation | First extraction candidate #389 |
| Update orchestration | `run_server_update`, apply/review test classes | All safety phases | Keep cohesive until helpers are extracted |

The selected seam is the pure diff-summary/risk-review path. It must preserve
review classifications, approval matching, refusal behavior, and the exact
diagnostic block consumed by the CLI.
