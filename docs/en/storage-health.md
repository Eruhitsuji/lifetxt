# Storage Health and Scheduled Maintenance

`lifetxt storage health PATH...` is a read-only diagnostic. It reports active
and archive bytes/records, parse diagnostics, measured parse time, thresholds,
and an advisory status. It never writes a workspace, creates a backup, or
applies an archive plan.

The first recommendation thresholds are evidence-based from the #944 baseline:
16 MiB or 200,000 active records. They are advisory and should be revisited
with representative deployment measurements; they are not universal limits.

Server deployments may opt into `maintenance_schedule` in the server-init JSON:

```json
{
  "maintenance_schedule": {
    "enabled": true,
    "mode": "warn",
    "interval_minutes": 1440
  }
}
```

`off` is the default. `warn` records a health result. `plan` also creates a
reviewable `archive-plan-v1` document for the configured project when health
recommends maintenance. It never applies that plan. The generated systemd
timer uses `Persistent=true`, so a missed run is attempted after reboot, and
the dedicated oneshot service prevents overlapping runs through systemd's
unit serialization. Scheduled backup remains a separate operation.

`auto` is a separate High-assurance, explicit opt-in mode. It generates the
same frozen plan, re-runs the existing revision/config/selection/reference and
recovery checks, and only then calls the existing `project archive
--apply-plan` path. Any error records a blocked/non-success result and performs
no apply. Disable it by setting `enabled` to `false` or `mode` to `off`.
