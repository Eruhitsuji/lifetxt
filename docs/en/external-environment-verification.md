# External Environment Verification

This runbook defines the evidence required for stable-support environments
Windows, WSL, Linux, and macOS. It is a release-evidence procedure, not a
claim that every environment has already been tested.

## Evidence classes

Record each result as `simulated_or_subprocess` (unit, fixture, subprocess,
disposable-local, or CI evidence) or `real_environment` (the named OS,
terminal, or filesystem class). Only the latter satisfies the OS, terminal, or
filesystem entries in `.ai/project/STABLE_RELEASE.yml`; CI is supporting
evidence only.

## Test setup

Use a clean checkout at the release-candidate commit. Record the full commit
SHA. Use a disposable virtual environment and workspace outside the checkout.
Never use production data, credentials, remote accounts, or real SMTP.

From the repository root, run the existing profiles with the native Python
launcher:

```text
python scripts/run_ci_like.py --profile core
python scripts/run_ci_like.py --profile cli
python scripts/run_ci_like.py --profile release
```

Run `--profile web` or `--profile mcp` only when those optional dependencies
are intentionally installed. On Windows PowerShell, `python` may be replaced
by `py -3.12`; on WSL, Linux, and macOS use `python3` when needed. Record
output and exit code for every command.

## Low-friction automated collection

For the mechanically verifiable host portion, prefer the external-verification
collector. It reuses `scripts/run_ci_like.py --profile release`, captures the
complete stdout/stderr and exit status, records sanitized host/git/Python/
terminal/filesystem metadata, probes `fzf` and `peco`, and writes everything to
one JSON file under `.cache/` by default.

Run exactly one command from the repository root:

| Environment | Command |
| --- | --- |
| Windows PowerShell | `.\scripts\verify-external.ps1` |
| WSL | `./scripts/verify-external.sh` |
| Linux | `./scripts/verify-external.sh` |
| macOS Terminal | `./scripts/verify-external.sh` |

These entry scripts do not need a pre-installed supported Python. Their only
job is finding *any* Python 3 already on the host -- even an unsupported
version -- to hand off to `scripts/run_external_verification.py`, which then
bootstraps a supported interpreter (3.10-3.12) itself: it prefers an
already-installed one (checked in priority order 3.12 -> 3.11 -> 3.10), and
otherwise provisions a verification-only interpreter from a pinned,
checksum-verified [python-build-standalone][pbs] release under
`.cache/lifetxt-verify-python/` -- never touching the host's system Python and
never requiring administrator/root privileges on the normal path. See
`scripts/verification_python_bootstrap.py` for the exact search order,
manifest, and verification logic. The bootstrap outcome (an already-installed
interpreter vs. a managed one, and its version) is recorded as its own
`python-bootstrap` entry in the evidence bundle's `checks`; a bootstrap or
isolated-environment-creation failure is recorded as `blocked` with an
actionable reason rather than crashing the collector or fabricating a release-
profile pass.

[pbs]: https://github.com/astral-sh/python-build-standalone

If a supported interpreter is already active in your shell, calling
`scripts/run_external_verification.py` directly still works exactly as
before. The command prints only a short result summary and the final
`evidence=...` path; the complete command output is embedded in that one JSON
bundle, so there are no separate log files to collect.

Use an explicit filename when transferring evidence between machines:

```text
./scripts/verify-external.sh --output .cache/external-verification.json
```

On Windows PowerShell:

```text
.\scripts\verify-external.ps1 --output .cache/external-verification.json
```

Optional already-built artifacts or evidence inputs can be hashed into the same
bundle by repeating `--artifact PATH`. `--skip-release` exists only for a quick
collector/debug run; it records the release profile as `skipped` and is not
release evidence.

### Release-profile timeout

The release profile (`scripts/run_ci_like.py --profile release`) is bounded by
`--release-timeout SECONDS`, forwarded unchanged by both entry scripts:

```text
./scripts/verify-external.sh --release-timeout 43200
```

```text
.\scripts\verify-external.ps1 --release-timeout 43200
```

The default is 28800 seconds (8 hours), raised from an earlier 14400-second
(4-hour) default that was itself raised from 7200 seconds. Real supported-host
runs observed WSL completing in about 7427 seconds (up from about 4959 seconds
on an earlier run of the same host class -- real host performance genuinely
varies run to run), macOS completing in about 14225 seconds (barely inside the
prior 14400-second boundary), and native Linux again hitting the collector's
timeout at 14400 seconds while still inside the test run itself, with no
compatibility failure observed before the cutoff. The current default gives
roughly 2x headroom over the highest confirmed near-miss (macOS's ~14225s) and
substantial room for native Linux and further host-to-host variance. Raise it
further with `--release-timeout` on a host that is slower still; a timeout is
never treated as a passing result regardless of the configured limit.

A run that exceeds `--release-timeout` is recorded with `"status": "timeout"`
on the `release-profile` check -- distinct from `"failed"` (the command ran
and returned a non-zero exit code) and from `"blocked"` (the command could
not start at all). The record also carries `"timeout_seconds"` with the
configured limit and retains whatever partial `stdout`/`stderr` the process
had already produced. A `timeout` status fails the collector's own exit code
exactly like `failed`, so it is never mistaken for a pass. Short metadata and
tool probes (`git rev-parse`, `fzf`/`peco` version checks) use the
independent, much shorter `--probe-timeout SECONDS` (default: 30) and are
unaffected by `--release-timeout`.

The collector does **not** synthesize evidence it cannot observe. Interactive
TUI checks, real selector actions, browser-engine behavior, Web deployment
cutover, Remote clients, SMTP providers, external filesystem classes, physical
power loss, release, and rollback remain `manual_required` or `blocked` until
their dedicated procedures run. A non-CI host run may record
`evidence_type: real_environment` for facts observed on that host, but its
`evidence_scope` remains `host_execution_only`.

Prerequisites are intentionally not installed automatically because OS package
installation may require administrator authority. A host with literally no
Python 3 at all remains an explicit `blocked`/manual case -- install any
Python 3 to let the entry scripts bootstrap a supported one, as above. If
`venv`, `pip`, `git`, `fzf`, or `peco` is unavailable or fails (for example, a
Linux host missing `python3-venv`'s `ensurepip` support), the collector or the
reused release profile blocks/fails explicitly and retains the reason in the
same JSON file rather than silently skipping it.

## Required scenarios

For every environment record OS/build, kernel where applicable, terminal,
Python/package versions, commit SHA, and filesystem. Run:

1. Core and release profiles, including wheel installation, both
   `python -m lifetxt --help` and installed `lifetxt --help`, and the minimal
   example check.
2. A disposable CLI write/mutation: verify one revision change, readable
   output, and idempotent repeat.
3. Disposable replacement/interference and recovery. Windows must include the
   documented file-lock case; POSIX systems must include the documented
   permission/recovery case.
4. Paths with spaces and non-ASCII characters, and LF/CRLF input where
   supported.
5. TUI smoke only from a real terminal/PTY when TUI is supported. Record
   terminal and locale; a subprocess test is not a substitute.
6. Web or MCP smoke only with the optional dependencies installed. Browser,
   Remote, and SMTP evidence belongs to their dedicated environment procedures
   and must not be inferred from a local CLI run.

## Platform matrix

| Environment | Required real-environment evidence | Additional notes |
| --- | --- | --- |
| Windows PowerShell | CLI smoke, timezone behavior, file replacement and recovery | Record Windows build, PowerShell, filesystem, and lock behavior. |
| WSL | CLI smoke and TUI smoke when supported | Record distribution/kernel, terminal host, and whether the workspace is on Linux storage or a mounted Windows path. |
| Linux | Release-artifact CLI smoke and local filesystem recovery | Record distribution, kernel, shell, filesystem, and Python source. |
| macOS Terminal | Release-artifact CLI smoke and TUI smoke when supported | Record macOS version, terminal, architecture, filesystem, and locale. |

The four rows are independent. A skipped optional dependency is `skipped` with
its reason, never `passed`.

## Evidence record

The automated collector writes one self-contained versioned JSON document. For
manually executed scenarios, retain equivalent fields so the records remain
reviewable and mergeable into the same release evidence model:

```json
{
  "environment": "windows",
  "evidence_type": "real_environment",
  "os_release": "<sanitized OS/build>",
  "terminal": "<terminal>",
  "python": "<version>",
  "package_version": "<version>",
  "commit_sha": "<40-char SHA>",
  "artifact_sha256": "<hash or null>",
  "scenario": "release-artifact-cli-smoke",
  "command": "<redacted command>",
  "result": "passed",
  "exit_code": 0,
  "notes": "<sanitized details>"
}
```

Redact usernames, absolute home paths, credentials, tokens, private content,
secret-bearing URLs, and raw life entries. Keep artifact hash, commit SHA,
exit code, and failure summary. Apply a timeout and cleanup to every scenario;
failed cleanup is a failed result requiring review.

### Progress evidence and persistence refusal

A full-profile run can take hours, and the final JSON bundle is written only
once, at the very end. The collector also writes two sanitized, incrementally
flushed progress artifacts alongside it, sharing the same name stem:

```text
.cache/
├─ external-verification-windows-<UTC>.log
├─ external-verification-windows-<UTC>.progress.jsonl
└─ external-verification-windows-<UTC>.json
```

`.log` is a human-readable line per lifecycle event (collector start, host
classification, git identity, Python bootstrap, release-profile start and
result, tool probes, final-evidence persistence, collector completion).
`.progress.jsonl` records the same events as one JSON object per line
(`run_id`, `timestamp`, `event`, `status`, and event-specific fields). Every
field in both files is redacted through the same sanitizer the final JSON
uses *before* it is ever written -- never write-then-sanitize -- and every
write is flushed and fsynced immediately, so a process kill, a timeout, or a
persistence refusal leaves the latest completed event durable on disk even
though the final JSON was never produced.

The final JSON is refused, not silently written, if a raw repo/home/temp/
username value survives sanitization (a persistence-time defense-in-depth
rescan). The refusal names only the candidate *category*
(`repo`/`home`/`temp`/`username`), never the raw value, and both progress
artifacts still contain a `final_evidence_persistence`/`refused` event with
that category. The progress artifacts are diagnostic only: an
incomplete/refused/interrupted run is never treated as passing
release-profile evidence, and the collector's own exit code stays non-zero.

## Release decision

An environment may be called stable only when its row has all required
`real_environment` records, CI/release gates pass, and evidence is linked from
the tracker and traceability metadata. An unavailable host, failure, or missing
terminal evidence remains `unverified` or `blocked`; it is not converted into
a support claim by inference.
