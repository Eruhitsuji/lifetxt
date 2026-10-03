# Connected semantic-event PoC

`connected_semantic_event.py` is the connected follow-up to the local OpenWrt
adapter in `contrib/openwrt/`. It accepts only `WAN_UP` and `WAN_DOWN`, maps
them to fixed ordinary `E` records, and delegates the authoritative write to
the existing Remote protocol-v2 item mutation client.

Example:

```sh
python -m contrib.remote.connected_semantic_event home WAN_DOWN \
  iot-wan-down-20261003T010203Z
```

The `home` profile must use a dedicated Remote principal with only the minimum
`read` and `write` scopes. The server must advertise protocol 2 and enable
`item-mutations`; the client fails closed otherwise. The existing client sends
the current snapshot revision as `If-Match`, and a revision conflict retries
only the same fixed payload and transaction identity once. The server's
existing transaction replay contract therefore handles an unknown response
without creating another item, while changed-payload reuse remains rejected by
the server.

The adapter does not expose an endpoint, accept arbitrary device payloads, or
add MQTT, Home Assistant, telemetry, device management, Mini features, or
Remote configuration. It is not a safety-critical connectivity monitor; do not
use lifetxt as the sole alert or recovery path. Successful writes use the
existing ordinary-item Remote path and its Native History evidence.
