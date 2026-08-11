# Ubuntu Server Production Deployment

This is a reference runbook for running `lifetxt` continuously on an Ubuntu
Server as a small personal or team service: a `lifetxt serve` process behind
a reverse proxy, plus an optional periodic Google Calendar / ICS sync.

It generalizes operational practice proven on a real deployment. It is
**not** a copy of any one operator's machine. Every path, username, port,
and URL below is a placeholder — fill in your own values, and never commit
the filled-in versions (secrets, VPN addresses, real hostnames) back into
this repository.

## What is normative, recommended, and example-only

- **Normative** (do this, or accept the consequence documented alongside
  it): keep `lifetxt serve` bound to `127.0.0.1` and put a reverse proxy in
  front of it; keep production data outside the source checkout; take a
  backup before every update.
- **Recommended**: the specific systemd layout, the nginx example, the
  `lifetxt`/`lifetxtcal` user split. Reasonable alternatives exist; deviate
  when your environment already has an established pattern (Apache instead
  of nginx, a container runtime instead of systemd, etc.).
- **Example-only**: exact paths (`/opt/lifetxt`, `/srv/lifetxt`), the sample
  port (`8765`), and the sample unit/environment file names. Change these
  freely; nothing in `lifetxt` itself assumes them.

## 1. Environment

`lifetxt` requires Python 3.10+ (see `pyproject.toml`'s `requires-python`).
Ubuntu 22.04 LTS and 24.04 LTS both ship a compatible Python 3, or you can
use `deadsnakes`/`pyenv` on an older release.

Install only the extras you need:

```sh
python3 -m venv /opt/lifetxt/venv
/opt/lifetxt/venv/bin/pip install -e "/opt/lifetxt/src[web,tui]"
```

`web` is required for `lifetxt serve`. `tui` is optional (only needed if you
plan to run `lifetxt tui` interactively on the server itself, which most
deployments do not). See [config.md](../en/config.md) and
[cli.md](../en/cli.md) for the full extras list, including the `dev` extra
you do **not** need in production.

## 2. Layout: separate code from data

Keep the git checkout (application code) and the writable data/config
directory (your `life.txt`, archive, `.lifetxt.json`, generated sources,
backups) in separate trees. This is what makes `lifetxt update` /
`lifetxt server-update` (section 6) safe: the update only ever touches the
checkout, and the pre/post-update hash check in section 6 can prove your
data was untouched by a code change.

```text
/opt/lifetxt/
  venv/                  # Python virtual environment
  src/                   # git clone of lifetxt (the checkout `update` fast-forwards)

/srv/lifetxt/
  life.txt               # authoritative data
  .lifetxt.json           # config (workspace-based, see config.md)
  archive/life.txt        # role: archive destination
  .generated/              # role: generated sources (e.g. google_calendar.life.txt)
  backups/                 # timestamped pre-update backups (section 6)
```

Run both the checkout and the data directory as a dedicated, non-login
system user (`lifetxt` in the examples below), not `root` and not your own
login account. Create it with `adduser --system --group --home /srv/lifetxt lifetxt`.

## 3. systemd services

Example unit files live in [`contrib/systemd/`](../../contrib/systemd/):

- [`lifetxt.service`](../../contrib/systemd/lifetxt.service) — runs
  `lifetxt serve`, bound to `127.0.0.1` only.
- [`lifetxt-sync-ics.service`](../../contrib/systemd/lifetxt-sync-ics.service)
  and [`lifetxt-sync-ics.timer`](../../contrib/systemd/lifetxt-sync-ics.timer)
  — periodic `lifetxt sync-ics` for Google Calendar / ICS sources, if you use
  one. See [`cli.md` section 5.2](../en/cli.md#52-sync-ics).
- [`lifetxt.env.example`](../../contrib/systemd/lifetxt.env.example) — the
  environment file `lifetxt-sync-ics.service` reads via `EnvironmentFile=`
  for its Calendar URL. `lifetxt.service` does **not** read this file; its
  paths/user/port are literal values in `lifetxt.service` itself, edited
  directly (see below). Copy `lifetxt.env.example` to
  `/etc/lifetxt/lifetxt.env`, fill in your real Calendar URL, and
  `chmod 600` it (it is sensitive, even though it is not a password).

Install:

```sh
# Edit User=/Group=/WorkingDirectory=/ExecStart= paths directly in
# lifetxt.service and lifetxt-sync-ics.service before copying them --
# neither reads paths/user/port from an environment file.
sudo mkdir -p /etc/lifetxt
sudo cp contrib/systemd/lifetxt.env.example /etc/lifetxt/lifetxt.env
sudo chmod 600 /etc/lifetxt/lifetxt.env
sudo $EDITOR /etc/lifetxt/lifetxt.env   # fill in your real Calendar URL

sudo cp contrib/systemd/lifetxt.service /etc/systemd/system/
sudo cp contrib/systemd/lifetxt-sync-ics.service /etc/systemd/system/
sudo cp contrib/systemd/lifetxt-sync-ics.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lifetxt.service
sudo systemctl enable --now lifetxt-sync-ics.timer   # only if you use Calendar sync
```

Lifecycle:

```sh
sudo systemctl status lifetxt.service
sudo systemctl restart lifetxt.service
sudo journalctl -u lifetxt.service -f
sudo systemctl list-timers lifetxt-sync-ics.timer
```

## 4. Reverse proxy

`lifetxt serve` binds `127.0.0.1` only by design
(`cap-serve-single-worker-default`; there is no supported way to make it
listen on a public interface directly). Put a reverse proxy in front of it
for TLS termination, access logging, and Basic Auth or another access
control layer of your choosing — `lifetxt` itself has no built-in
authentication for the plain Web UI (Remote Safe Mode's bearer-token auth is
a separate, opt-in surface; see [remote.md](../en/remote.md) if you need
it).

An nginx example is in [`contrib/nginx/lifetxt.conf.example`](../../contrib/nginx/lifetxt.conf.example).
It proxies to the loopback bind only and leaves TLS certificate setup
(certbot, an existing wildcard cert, etc.) to you — do not copy a
certificate path from the example without replacing it with your own.

## 5. Backup and restore

Before any update (section 6 does this automatically), and on whatever
schedule you choose otherwise, back up:

- `life.txt` (primary)
- the archive destination file(s)
- `.lifetxt.json`
- any `role: generated` source files (e.g. the Google Calendar mirror)

A plain timestamped copy is sufficient; `lifetxt` does not require a special
backup format. To restore, stop the services, replace the files from a
backup, verify with section 7's checks, then restart:

```sh
sudo systemctl stop lifetxt.service lifetxt-sync-ics.timer
cp /srv/lifetxt/backups/<timestamp>/life.txt /srv/lifetxt/life.txt
# ... repeat for config/archive/generated as needed
python -m lifetxt check /srv/lifetxt/life.txt
sudo systemctl start lifetxt.service lifetxt-sync-ics.timer
```

## 6. Update and rollback

Two ways to update, from least to most automated:

**Manual**, for occasional or one-off updates — `lifetxt update` (see
[`cli.md`'s `update` section](../en/cli.md#16-init-and-doctor)) fast-forwards
the checkout's own git working tree. It is dry-run by default, refuses on
an unclean tree or a non-fast-forward target, and only ever runs `git fetch`
plus `git merge --ff-only`:

```sh
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt update
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt update --yes
sudo -u lifetxt /opt/lifetxt/venv/bin/pip install -e /opt/lifetxt/src[web,tui]
sudo systemctl restart lifetxt.service
```

`update` does not stop services, take a backup, or reinstall dependencies
for you — that is why the next option exists.

**Guarded**, for routine production updates —
[`lifetxt server-update`](../en/cli.md#22-server-update) wraps the same git
logic with the full backup / service-stop / reinstall / hash-verification /
health-check flow:

```sh
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt server-update --server-config /etc/lifetxt/server-update.json
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt server-update --server-config /etc/lifetxt/server-update.json --yes
```

See [`cli.md` section 22](../en/cli.md#22-server-update) for the full flag
reference, the `--server-config` JSON contract, and every failure mode. In
short:

- A normal update backs up production files, stops whichever configured
  services/timers are currently active, fast-forwards to the exact SHA it
  already resolved and inspected, reinstalls the package, verifies your
  data/config hashes are unchanged by the code update, runs `lifetxt check`
  / `lifetxt workspace validate` / `lifetxt ids` /
  `lifetxt ticket validate-history`, restarts the services it stopped, and
  checks `/api/health`.
- A failure before any mutation restores whatever service state existed
  before the attempt. A failure after the code update but before validation
  completes leaves services **stopped** rather than restarting a
  potentially broken install, and the report names the exact backup and
  pre-update commit to restore manually (section 5).
- `server-update` has **no built-in high-impact-change review gate yet** --
  with `--yes`, it runs the full flow above unconditionally once the
  target is resolved. A pre-mutation risk classification and approval step
  (stopping before any mutation when a change looks high-impact, with an
  explicit `--approve <exact-sha>` step) is a tracked, not-yet-implemented
  follow-up. Until it lands, review `server-update`'s dry-run output
  (which lists the pending commits) yourself before passing `--yes` for
  any update you have not already reviewed through your normal process.

**Rollback**, if an update produces a broken state that `server-update`'s
own failure handling did not already recover from: restore the backup
(section 5), then check out the pre-update commit recorded in the update
report:

```sh
sudo -u lifetxt git -C /opt/lifetxt/src checkout <pre-update-sha>
sudo -u lifetxt /opt/lifetxt/venv/bin/pip install -e /opt/lifetxt/src[web,tui]
python -m lifetxt check /srv/lifetxt/life.txt
sudo systemctl start lifetxt.service
```

## 7. Validation and health checks

Run these after any update, restore, or configuration change:

```sh
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt doctor
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt workspace validate --all
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt check /srv/lifetxt/life.txt
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt ids /srv/lifetxt/life.txt
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt ticket validate-history /srv/lifetxt/life.txt
curl -sf http://127.0.0.1:8765/api/health
```

`server-update` (section 6) runs a configurable subset of these
automatically as its own step 13; running them by hand is for everything
outside an update — after a manual restore, a configuration edit, or simply
as a periodic health check.

## 8. Secrets and privacy

Never commit to this repository, and never leave world-readable on the
server:

- Basic Auth credentials/hashes for the reverse proxy
- Google Calendar URLs or any sync tokens
- VPN addresses or topology
- production `life.txt` content
- the `lifetxt.env` file's filled-in values (keep it `chmod 600`,
  owned by the `lifetxt` user)

Keep the reverse proxy's access-control layer (section 4) and
`lifetxt serve`'s loopback-only bind (section 3) as your two independent
boundaries — do not rely on either one alone.

## Also see

- [`contrib/systemd/`](../../contrib/systemd/) — the unit/timer/environment
  file examples referenced above.
- [`contrib/nginx/`](../../contrib/nginx/) — the reverse-proxy example.
- [`cli.md`](../en/cli.md) — full flag reference for every command used in
  this runbook.
- [`config.md`](../en/config.md) — workspace and configuration reference.
- [`remote.md`](../en/remote.md) — Remote Safe Mode, if you want
  authenticated API access beyond the plain Web UI.
