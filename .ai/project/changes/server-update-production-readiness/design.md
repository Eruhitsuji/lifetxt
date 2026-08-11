# Design

## Summary

`server-update` keeps the previous simple config as the default path and adds
four opt-in extensions:

- `installer: "pip" | "uv" | "conda-pip"` builds `<python> -m pip install ...`,
  `<uv> pip install --python <python> ...`, or
  `<conda> run --name|--prefix ... python -m pip install ...`.
- `service_command` and `service_preflight_commands` are structured argv lists,
  so operators can use a narrow sudo/Polkit wrapper without giving the whole
  updater root privileges.
- `integrity_checks` may remain strings or become objects with per-check
  targets and context.
- `validation_commands` are structured, timeout-bound commands run after
  reinstall/sanity/import/integrity checks and before service restart.

## Interfaces and Contracts

- ADDED: `installer`, `uv_executable`, `uv_install_args`.
- ADDED: `conda_executable`, `conda_env_name`, `conda_env_prefix`, `conda_install_args`.
- ADDED: `service_command`, `service_preflight_commands`.
- ADDED: top-level and per-check `application_config` and `workspace`.
- ADDED: object form for `integrity_checks`.
- ADDED: `validation_commands`.
- MODIFIED: dry-run and review reports include `installer` and `install_command`.
- MODIFIED: integrity-check results include command/path/config/workspace fields.
- REMOVED: none.

## Horizontal Environment Review

- Pip-based virtualenvs remain the default because they are already deployed and
  tested.
- Pip-less uv virtualenvs are handled by running uv outside the venv and passing
  `--python <venv-python>`, avoiding any need to install pip solely for the
  updater.
- Conda-managed environments are handled with `conda run --name` or
  `conda run --prefix`, matching conda's documented environment-targeting
  surface. The backend still invokes `python -m pip install` inside that
  environment, so deployments keep the established editable local-project
  install behavior while making the environment explicit.
- Non-systemd or externally-managed environments keep using
  `service_manager: "none"`.
- System-level systemd units require authorization for start/stop. The runbook
  documents a narrow wrapper allowlist plus sudoers rule. A broad
  passwordless `systemctl` rule and running the entire updater as root were
  rejected.
- `systemctl --dry-run` is not used as the permission probe: current and older
  Ubuntu/systemd man pages document dry-run support for power/session verbs,
  not start/stop service management. Operators can instead configure explicit
  preflight commands such as `sudo -n -l <wrapper>`.

## Alternatives

- A free-form `install_command` string was rejected because it would add shell
  parsing and injection ambiguity.
- Direct use of the emerging conda PyPI installer path was not made the default
  because the stable compatibility target is existing conda environments with
  pip installed; conda's own guidance still treats pip as the last step for
  PyPI packages in a conda environment.
- A single universal service authorization probe was rejected because probing
  start/stop authority without performing start/stop is not portable across
  target systemd versions.
- Replacing all integrity checks with a single custom validation command was
  rejected because it would discard the structured built-in check results and
  weaken existing compatibility.

## Risks

- `service_preflight_commands` can only prove the exact command they run; the
  wrapper allowlist remains the real authorization boundary.
- Validation commands are operator-trusted deployment config. They are argv-only
  to avoid shell injection but still run with the updater user's privileges.

## Operations Impact

This change improves production compatibility for uv-managed installs and
least-privilege systemd deployments. Any validation failure after the code
update keeps the existing fail-safe: stopped services are not restarted with
unvalidated code.

## Compatibility Impact

Existing simple configs remain valid: `installer` defaults to `pip`,
`service_command` defaults to `["systemctl"]`, string `integrity_checks` still
use `life_txt_path`, and validation/preflight commands are disabled by default.
Conda support is opt-in and requires exactly one explicit environment selector.
