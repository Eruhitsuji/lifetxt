# contrib/

Example, non-authoritative deployment configuration referenced by
[`docs/deployment/ubuntu-server.md`](../docs/deployment/ubuntu-server.md).

Every file under `contrib/` is a documented template with placeholder
values (paths, usernames, hostnames, ports). None of it is installed or
read by `lifetxt` itself -- copy what you need, edit the placeholders, and
install it into your own system configuration.

- `systemd/` -- unit/timer/environment-file examples for running
  `lifetxt serve` and periodic `lifetxt sync-ics` under systemd.
- `nginx/` -- a reverse-proxy example for the loopback-only `lifetxt serve`
  bind.

Never commit a filled-in copy of any file here: several of them have a slot
for a hostname, certificate path, or Calendar URL that becomes sensitive
once it names a real deployment.
