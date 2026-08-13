# Design

## Summary

Add a thin evidence-orchestration runner around the existing release verifier.
The runner observes the actual host, invokes `scripts/run_ci_like.py --profile
release`, captures stdout/stderr/exit status/duration, probes optional selector
tools, hashes caller-supplied artifacts, and serializes everything into one
sanitized JSON document.

## Interfaces and Contracts

- ADDED: `python scripts/run_external_verification.py`.
- ADDED: versioned JSON evidence bundle with `schema_version: 1`.
- MODIFIED: repository command registry and external-verification runbook.
- UNCHANGED: `scripts/run_ci_like.py`, lifetxt runtime/public command behavior,
  stable-support classification, and human release authority.

The bundle uses `real_environment` only to describe facts observed while the
runner executes on a supported non-CI host. It also sets
`evidence_scope: host_execution_only`; interactive TUI, browser, Remote, SMTP,
external filesystem, deployment, release, and rollback scenarios remain
`manual_required` or `blocked` until their dedicated procedures run.

## Alternatives

- Separate PowerShell/Bash implementations were rejected because they would
  duplicate evidence semantics and drift across platforms.
- Reimplementing release build/install smoke was rejected because
  `scripts/run_ci_like.py --profile release` already owns that behavior.
- Automatically installing OS packages or external services was rejected because
  it requires administrator/provider authority and can hide environment gaps.
- Multiple per-command log files were rejected because the user explicitly
  requested one low-friction output artifact.

## Risks

- False-pass risk: controlled by explicit `manual_required`/`blocked` states and
  host-only evidence scope.
- Secret/path leakage: controlled by allow-listed metadata and pre-persistence
  redaction of captured output.
- Cross-platform decoding/path issues: controlled by `errors="replace"`, argument
  lists, platform-specific filesystem probes, and focused tests.
- Stale evidence: the bundle records exact git SHA and package version; release
  policy still determines when evidence is stale.

## Operations Impact

The runner writes only under `.cache/` by default and uses disposable environments
created by the existing release profile. It does not deploy, mutate production
data, or contact external providers by itself.

## Compatibility Impact

Additive developer/release tooling only. No stable lifetxt runtime or data-format
contract changes.
