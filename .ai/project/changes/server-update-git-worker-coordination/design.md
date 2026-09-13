# Design

`server_init._managed_service_units()` is the single source for systemd units
that server-init exposes to `server-update` and to the generated wrapper. The
optional worker contributes its timer first and oneshot service second. The
existing `server_update.run_server_update()` already checks active state before
stopping and restores only units active before the update, so no update-flow
algorithm change is needed.

The worker's existing lock coordination remains defense in depth for shared
data/source deployments; service coordination closes the broader timer/code
replacement race.
