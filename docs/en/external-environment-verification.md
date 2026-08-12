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

Store one record per command in reviewable Markdown or JSON:

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

## Release decision

An environment may be called stable only when its row has all required
`real_environment` records, CI/release gates pass, and evidence is linked from
the tracker and traceability metadata. An unavailable host, failure, or missing
terminal evidence remains `unverified` or `blocked`; it is not converted into
a support claim by inference.
