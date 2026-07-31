# Operations Standard

Operational readiness is part of development, not a separate afterthought.

## Required Operations Viewpoints

Projects must consider:

- Monitoring
- Logging
- Metrics
- SLI/SLO
- Alert
- Runbook
- Backup/Restore
- Rollback
- Vulnerability response
- Incident response
- Capacity/Performance
- Data retention
- Deprecation/Retirement

## Operations Evidence

Operations-impacting PRs must record:

- expected runtime impact
- monitoring or logging changes
- alerting changes
- rollback path
- runbook update or reason not needed
- data retention or backup impact
- incident response owner when relevant

## Incidents

Incident work must separate:

- immediate mitigation
- root-cause investigation
- corrective implementation
- regression tests
- post-incident review

An AI may assist the Incident Commander, but cannot be the Incident Commander.
