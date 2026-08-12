# Release Documentation Parity Audit

This record closes issue #354 for the release-critical English and Japanese
documentation. The audit compares user-visible claims rather than requiring a
line-by-line translation. Commands, stable boundaries, compatibility behavior,
safety limitations, and release verification steps were checked on 2026-08-12.

## Audited pairs

| Area | English | Japanese | Result |
| --- | --- | --- | --- |
| CLI and configuration | `cli.md`, `config.md` | same filenames | commands and configuration boundaries align |
| Format and release baseline | `release-baselines.md` | same filename | baseline purpose and review flow align |
| Release gates and safety | `release-policy-gates.md`, `release-safety-foundations.md` | same filenames | gate intent and safety boundary align |
| Remote read and compatibility | `remote.md`, `remote-compatibility.md` | same filenames | read-only boundary, negotiation, and warnings align |
| Web installation and startup | `web.md` | same filename | install/start commands and write flags align |
| Recovery and workspace safety | `transaction-recovery-and-strict-timers.md`, `timezone-revision-workspace-safety.md` | same filenames | recovery, timezone, and diagnostic boundaries align |
| Public revisions and delegated recovery | `public-surface-revisions.md`, `delegated-remote-attachments-and-recovery.md` | same filenames | stable preconditions and deferred security work align |
| Stable compatibility and optional dependencies | `release-compatibility-policy.md`, `optional-dependency-compatibility.md` | same filenames | stable/experimental boundary and install ranges align |
| Artifact evidence | `release-artifact-evidence.md` | same filename | artifact, checksum, SBOM, and provenance claims align |

## Findings and dispositions

- The documented Web install and startup commands are identical in both
  languages, including `--write-file` and `--read-only` examples.
- The stable promise remains narrower than the complete implementation: MCP and
  Remote writes, browser accessibility, SMTP delivery, and provider side
  effects remain outside the stable promise where the English policy identifies
  them as experimental or deferred. The Japanese documents use the same
  boundary.
- The Japanese release documents added in this audit intentionally summarize
  the normative English records while preserving the same commands, ranges, and
  release decisions.
- Machine-generated JSON evidence and detailed smoke logs are operational
  records, not user-facing release guidance. They remain English-only to avoid
  maintaining two copies of generated output; the Japanese user-facing pages
  link to or summarize their disposition where needed.

## Evidence

The pair inventory above was checked for file existence, UTF-8 readability,
matching command literals, and matching stable-boundary terms. Project YAML
records were parsed after the audit, and `git diff --check` was clean. Any future
change to a stable release claim must update both language files and this audit
record or record an approved intentional non-parity.
