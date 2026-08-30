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

## Guarded bootstrap or manual setup

You can either follow the sections below by hand or ask lifetxt to resolve the
same reference deployment into an explicit plan first:

```sh
lifetxt server-init --server-config server-init.json
lifetxt server-init --server-config server-init.json --yes
```

Dry-run is the default. The first command prints the directories, files,
systemd artifacts, least-privilege service-control wrapper, nginx artifact,
install command, generated `server-update.json`, integrity checks, and health
check that would be used. The second command applies the plan, creating only
missing artifacts and treating matching existing artifacts as no-op. If an
existing production file, unit, sudoers file, or reverse-proxy file differs,
`server-init` refuses rather than overwriting it; use a deliberate adoption or
repair task for existing manual deployments.

The bootstrap config is a deployment config, not the application
`.lifetxt.json`. It must name `install_root`, `data_root`, installer/Python
environment details, and the service user/group explicitly:

```json
{
  "install_root": "/opt/lifetxt/src",
  "data_root": "/srv/lifetxt",
  "python": "/opt/lifetxt/venv/bin/python",
  "installer": "uv",
  "uv_executable": "/home/lifetxt/.local/bin/uv",
  "extras": ["web", "tui"],
  "service_user": "lifetxt",
  "service_group": "lifetxt",
  "systemd": {
    "enabled": true,
    "unit_dir": "/etc/systemd/system",
    "daemon_reload": false,
    "enable": false,
    "start": false
  },
  "service_control": {
    "enabled": true,
    "wrapper_path": "/usr/local/sbin/lifetxt-systemctl",
    "sudoers_path": "/etc/sudoers.d/lifetxt-server-update"
  },
  "reverse_proxy": {
    "backend": "nginx",
    "nginx_config_path": "/etc/nginx/sites-available/lifetxt.conf"
  }
}
```

Keep privileged targets (`/etc/systemd/system`, `/usr/local/sbin`,
`/etc/sudoers.d`, `/etc/nginx`) explicit. A plan can be reviewed before an
operator runs it with privileges, while the unprivileged git/package/data
workflow remains separate from broad root command execution. The generated
`server-update.json` uses the same installer backend, service wrapper,
backup/update-lock paths, integrity checks, and health URL so the server is
ready for future guarded `server-update` runs.

### Optional: generate an AI-safe workspace at bootstrap time

Add an opt-in `ai_workspace` section to generate the
[AI-Safe Workspaces](../en/ai-integration.md#7-ai-safe-workspaces) pattern
from the start, instead of hand-editing `.lifetxt.json` after the fact:

```json
{
  "ai_workspace": {"enabled": true, "write_file": "ai-inbox.life.txt"}
}
```

When enabled, the generated `.lifetxt.json` switches from the plain
`paths`/`write_file` shape to a `workspaces` config with a `default`
workspace (unchanged behavior) and an `ai` workspace: broad read access to
the primary `life.txt`, writes confined to the new (empty, created for you)
AI-inbox file. `server-init` also adds that file to the generated
`server-update.json`'s `backup_paths` automatically. `write_file` defaults
to `ai-inbox.life.txt` under `data_root` and may be omitted; omitting
`ai_workspace` entirely (the default) generates exactly today's config,
byte for byte. See [server-hosted MCP access](#9-ai-client-access-mcp-over-ssh)
below for connecting an AI client to this workspace.

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

### Least-privilege service control for `server-update`

The example units above are system-level units. A non-root `lifetxt` user
can read some state with `systemctl`, but stopping or starting system
units requires explicit authorization. Do not make the updater user
passwordless for arbitrary `systemctl`, and do not run the whole updater as
root just to cross this boundary: the updater also runs git, package
installation, and validation commands against the application checkout.

One narrow supported pattern is a root-owned wrapper that accepts only the
actions and units used by this deployment, then a sudoers rule for that
wrapper only:

```sh
sudo install -o root -g root -m 0755 /dev/stdin /usr/local/sbin/lifetxt-systemctl <<'EOF'
#!/bin/sh
case "$1:$2" in
  is-active:lifetxt.service|stop:lifetxt.service|start:lifetxt.service) ;;
  is-active:lifetxt-sync-ics.timer|stop:lifetxt-sync-ics.timer|start:lifetxt-sync-ics.timer) ;;
  *) echo "refusing service action: $1 $2" >&2; exit 64 ;;
esac
exec /bin/systemctl --no-ask-password "$1" "$2"
EOF

sudo visudo -f /etc/sudoers.d/lifetxt-server-update
```

`/etc/sudoers.d/lifetxt-server-update`:

```text
lifetxt ALL=(root) NOPASSWD: /usr/local/sbin/lifetxt-systemctl
```

Then set these keys in `/etc/lifetxt/server-update.json`:

```json
{
  "service_command": ["sudo", "-n", "/usr/local/sbin/lifetxt-systemctl"],
  "service_preflight_commands": [
    ["sudo", "-n", "-l", "/usr/local/sbin/lifetxt-systemctl"]
  ]
}
```

`service_preflight_commands` run before backup, service stop, or git
mutation, so a missing sudo rule fails early. This preflight cannot prove
every future systemd action without performing that action; `systemctl
--dry-run` is not a portable start/stop permission probe across supported
Ubuntu/systemd versions. The wrapper allowlist is therefore the real
authorization boundary.

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
- **every configured named workspace's write target** -- if you added a
  `workspaces` section to `.lifetxt.json` (by hand, or via the opt-in
  `ai_workspace` generation above) after your `server-update.json` was
  written, its `backup_paths` does not pick that up automatically; add the
  new write target to `backup_paths` yourself

`lifetxt server-update` checks the last point for you: every dry-run and
applied run compares `backup_paths` against every workspace write target the
live `.lifetxt.json` currently declares and prints a non-fatal
`backup_paths does not cover ...` warning naming anything missing. This never
blocks the update -- it exists so a workspace added after initial setup is
never silently left out of backup coverage, without `server-update` guessing
at your intended backup policy by rewriting `backup_paths` itself.

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
[`lifetxt server-update`](../en/cli.md#23-server-update) wraps the same git
logic with the full backup / service-stop / reinstall / hash-verification /
health-check flow:

```sh
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt server-update --server-config /etc/lifetxt/server-update.json
sudo -u lifetxt /opt/lifetxt/venv/bin/lifetxt server-update --server-config /etc/lifetxt/server-update.json --yes
```

See [`cli.md` section 23](../en/cli.md#23-server-update) for the full flag
reference, the `--server-config` JSON contract, and every failure mode. In
short:

- A normal update backs up production files, stops whichever configured
  services/timers are currently active, fast-forwards to the exact SHA it
  already resolved and inspected, reinstalls the package with either the
  default pip backend, a configured `uv` backend, or a configured
  `conda-pip` backend for conda-managed environments, verifies your
  data/config hashes are unchanged by the code update, runs `lifetxt check`
  / `lifetxt workspace validate` / `lifetxt ids` /
  `lifetxt ticket validate-history` against the configured per-check
  files/config/workspace, runs any optional validation command, restarts
  the services it stopped, and checks `/api/health`.
- A failure before any mutation restores whatever service state existed
  before the attempt. A failure after the code update but before validation
  completes leaves services **stopped** rather than restarting a
  potentially broken install, and the report names the exact backup and
  pre-update commit to restore manually (section 5).
- Before touching anything, `server-update` also classifies how risky the
  update looks (parser/config/atomic-write/schema/remote/ICS/deployment
  changes, a tracked file deletion, or a "breaking"/"security"/"migration"
  commit message). A low-risk update with `--yes` proceeds with no operator
  interaction. A flagged one stops before any mutation and prints a
  paste-friendly review block instead; copy its `approved_command` line
  (or otherwise pass `--approve <exact-target-sha>`) to apply that exact,
  already-reviewed commit. `--approve` is refused if the upstream target
  moved since the block was generated -- see
  [`cli.md` §22.1](../en/cli.md#221-high-impact-review-gate) for the full
  trigger list and block format.
- Health checking after service restart is readiness-aware. If systemd has
  started the service but the Web process is not listening yet,
  `server-update` retries the configured `health_url` until
  `health_ready_timeout` expires, waiting `health_retry_interval` seconds
  between failed attempts. Keep the defaults (`10` seconds total and `0.5`
  seconds between attempts) unless your production startup is consistently
  slower; this wait runs only after code validation and service restart, and
  it does not perform another git/package/data/service mutation.

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

## 9. AI client access (MCP over SSH)

`lifetxt mcp` needs no service, port, or reverse-proxy entry of its own: it
speaks JSON-RPC over stdio, so an AI client on a different machine reaches it
by running the command remotely over an SSH session it already has, exactly
as it would run any other remote command. No new listening port is opened on
the server, and the authoritative workspace and its policy enforcement
(permission profile, workspace selection) stay entirely on the server side —
the client only ever sees what the server-side `lifetxt mcp` process chooses
to expose.

```json
{
  "mcpServers": {
    "lifetxt-server": {
      "command": "ssh",
      "args": [
        "lifetxt-server",
        "cd /srv/lifetxt/data && /srv/lifetxt/.venv/bin/lifetxt mcp --profile read life.txt"
      ]
    }
  }
}
```

`lifetxt-server` above is an entry in the client machine's own `~/.ssh/config`
(`Host lifetxt-server` / `HostName` / `User` / `IdentityFile`), not a value
lifetxt itself understands — set it up with the same key-based,
password-less SSH access you would use for any other remote command
execution. As with local MCP setup, default the profile to `read` unless you
have a specific reason to grant `assist`; see
[ai-integration.md's Server-hosted (SSH) section](../en/ai-integration.md#server-hosted-ssh)
for the full client-side walkthrough, constrained-profile guidance, and how
this differs from `lifetxt serve`'s Web/Remote Safe Mode path documented in
sections 3–4 above.

Use a workspace-scoped path (`lifetxt mcp --workspace ai --profile assist
...`, per [ai-integration.md's AI-Safe Workspaces
section](../en/ai-integration.md#7-ai-safe-workspaces)) instead of the
primary `life.txt` shown above when you want to confine the AI client's
writes to a dedicated proposal/inbox target rather than the same file
`lifetxt serve` and the sync timers write to.

## 10. Scheduled reports

Periodic `lifetxt report` output can be scheduled the same way as the Web
service and calendar sync: systemd owns scheduling, and `report` itself
still owns what a report generates. No resident lifetxt scheduler is added.

**New or fully regenerated deployments** add an opt-in `reporting` section
to `server-init.json`:

```json
{
  "reporting": {
    "enabled": true,
    "profiles": {
      "weekly": {
        "period": "weekly",
        "output": "reports/{iso_year}-W{iso_week}.md",
        "sections": [{"type": "review"}, {"type": "stats"}]
      }
    },
    "jobs": [
      {"name": "weekly", "profile": "weekly", "schedule": "after-period", "at": "00:10"}
    ]
  }
}
```

`reporting.profiles` is validated through the same profile validator
`lifetxt report` itself uses (see
[`reports.md`](../en/reports.md#report-v2-composing-existing-aggregations-sections))
and copied verbatim into the generated application config's `reports`
section. Each `reporting.jobs` entry generates one systemd oneshot service
(`lifetxt-report-<name>.service`, running `report run <profile> --previous`)
and one `Persistent=true` timer (`lifetxt-report-<name>.timer`) whose
`OnCalendar=` matches the profile's own period boundary — daily every day,
weekly on Monday, monthly on the 1st — at the configured `at` (24-hour
`HH:MM`) time, so the timer fires once the period it reports on has just
completed. `schedule` currently supports only `"after-period"`.

**Already-running deployments** add or remove one report job without
re-running `server-init` or touching any other deployment artifact:

```sh
lifetxt server-report plan weekly \
  --app-config /srv/lifetxt/data/.lifetxt.json \
  --service-user lifetxt --service-group lifetxt
lifetxt server-report install weekly \
  --app-config /srv/lifetxt/data/.lifetxt.json \
  --service-user lifetxt --service-group lifetxt --yes --enable --start
lifetxt server-report remove weekly \
  --app-config /srv/lifetxt/data/.lifetxt.json --yes
```

`--app-config` (not `--config`) names the target application `.lifetxt.json`
— using the global `--config` flag here would be silently stripped before
this command ever saw it, the same pitfall `server-init`/`server-update`
avoided with their own `--server-config` flag. `server-report` never creates
or edits a report profile: `weekly` above must already exist in
`.lifetxt.json`'s `reports` section and pass the real Report v2 validator,
keeping runtime report configuration and deployment-unit installation as
separate, reviewable concerns. It reuses the exact same systemd unit
generator the `reporting` section above uses, so a job's unit content is
identical regardless of which command installed it. `install` is dry-run
without `--yes` and refuses to overwrite a conflicting existing unit file;
`remove` only deletes files that still carry the generator's own marker
comment, never an unrelated same-named file.

Generated report files are derived, regenerable artifacts, not source data —
they are deliberately not added to `server-update`'s backup coverage.

## Also see

- [`contrib/systemd/`](../../contrib/systemd/) — the unit/timer/environment
  file examples referenced above.
- [`contrib/nginx/`](../../contrib/nginx/) — the reverse-proxy example.
- [`cli.md`](../en/cli.md) — full flag reference for every command used in
  this runbook.
- [`config.md`](../en/config.md) — workspace and configuration reference.
- [`remote.md`](../en/remote.md) — Remote Safe Mode, if you want
  authenticated API access beyond the plain Web UI.
- [`ai-integration.md`](../en/ai-integration.md) — MCP client setup,
  including the SSH-based server-hosted path from section 9 above.
