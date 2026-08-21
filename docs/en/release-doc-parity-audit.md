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

## Addendum: #454 minimal-stabilization changes (2026-08-22)

`cli.md`'s `update` section (an audited pair above) was corrected in both
languages together, in the same change, when it changed under #454: it no
longer calls `-e .` "the documented install method" now that a plain
`pip install .` is the primary getting-started path, and explains why
`update`/`server-update` specifically still require the editable install.
Both language versions carry the same explanation.

`readme.md`, `docs/en+ja/readme.md`, `docs/en+ja/use-cases.md`, and
`docs/ja/optional-dependency-compatibility.md` are outside this audit's
original file list (root `readme.md` was never included; `use-cases.md` and
`optional-dependency-compatibility.md` were not release-critical at the time
of the original audit). Their #454-driven installation-example changes
(`pip install -e .` -> `pip install .` for the primary path) were made to
both language files together in the same change and reviewed for matching
claims; this is a note that they were kept in parity, not a new formal
addition to the audited-pairs table above, which remains scoped to the
original #354 release-critical set.

`docs/en+ja/stable-release-notes-draft.md` is also outside the original
audited-pairs list (it did not carry a finalized version or content when the
#354 audit closed). It was written in both languages together throughout the
#454 work, including the version 1.0.0 selection, the Highlights/Upgrading/
Release status sections added when the version was set, and the
known-limitations content; both language files were checked to reference
the same issues, sections, and doc cross-links.
