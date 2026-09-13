# Design

`run_server_update()` now treats the initial active-unit snapshot only as the
restore set. It separately stops every configured unit in list order, then
queries every unit again and refuses before backup or code mutation unless
systemd positively reports a non-active state.

This closes the timer/oneshot TOCTOU window without attempting to infer systemd
relationships. Operators retain responsibility for ordered configuration;
`server-init` emits each known timer immediately before its oneshot service.

On failure before code mutation, the updater starts only originally active units
that it successfully stopped. After validated mutation it likewise starts only
the original active set. Existing post-mutation failures continue to leave all
managed units stopped.

## Recovery

The change does not alter repository rollback. If an update fails after code
mutation, keep services stopped, restore the reported pre-update commit and
backup, run the configured integrity checks, then restore the intended systemd
state. The previous implementation can be restored with a normal PR revert.

