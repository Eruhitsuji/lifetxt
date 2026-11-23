# contrib/

Optional utilities and example deployment configuration. Nothing in
`contrib/` is installed or read by lifetxt itself.

- [Quick Capture practice](quick-capture-practice/README.md) — a local practice
  site with 50 Japanese exercises covering Quick shorthand, native life.txt,
  and todo.txt.

The following deployment templates are referenced by the
[`Ubuntu Server guide`](../docs/deployment/ubuntu-server.md). Copy what you
need, edit the placeholders, and install it into your own system configuration.

- `systemd/` -- unit/timer/environment-file examples for running
  `lifetxt serve` and periodic `lifetxt sync-ics` under systemd.
- `nginx/` -- a reverse-proxy example for the loopback-only `lifetxt serve`
  bind.

Never commit a filled-in copy of any file here: several of them have a slot
for a hostname, certificate path, or Calendar URL that becomes sensitive
once it names a real deployment.
