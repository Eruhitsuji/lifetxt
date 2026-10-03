# OpenWrt WAN semantic-event PoC

`lifetxt-wan-event` is a deliberately small edge adapter. It accepts only the
fixed semantic notifications `WAN_UP` and `WAN_DOWN`, then appends one bounded
`E` record through the existing `lifetxt-mini add` command.

The OpenWrt hotplug or interface hook is expected to provide the stabilization
boundary. Raw link samples are not stored. The adapter remembers the last
stable state in `/var/lib/lifetxt/openwrt-wan.state` (override with
`LIFETXT_WAN_STATE_FILE`) and ignores repeated notifications. The first
observation establishes state without writing an event; a later state change
writes exactly one event. A lock directory prevents concurrent hooks from
processing the same transition.

## Installation and invocation

Install `lifetxt-mini` at `/usr/bin/lifetxt-mini`, copy the adapter to
`/usr/libexec/lifetxt-wan-event`, and make it executable. Set `LIFETXT_FILE`
when the target is not `/root/life.txt`:

```sh
LIFETXT_FILE=/root/life.txt \
  /usr/libexec/lifetxt-wan-event WAN_UP
LIFETXT_FILE=/root/life.txt \
  /usr/libexec/lifetxt-wan-event WAN_DOWN
```

`LIFETXT_MINI` overrides the Mini path and `LIFETXT_WAN_STATE_FILE` overrides
the adapter-local state path. The event ID is source-scoped and contains the
UTC transition timestamp, so a later return to a previous state gets a new ID.
The state is committed only after `lifetxt-mini` succeeds; a failed write does
not falsely advance the stable state.

The produced records use only Mini-supported fields:

```text
[ ] E "WAN disconnected" id:iot-wan-wan_down-20261003T010203Z tag:iot tag:network
```

This is an integration proof of concept, not a safety-critical connectivity
monitor. Do not use lifetxt as the sole alert or recovery path. The adapter is
local-only and provides no HTTP, MQTT, Home Assistant, telemetry, or device
management service. Treat the state file as operational adapter state, not
authoritative Personal Context.
