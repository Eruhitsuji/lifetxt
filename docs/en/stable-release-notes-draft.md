# lifetxt 1.0.0 Release Notes

**`v1.0.0`** is published: <https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.0>.
It was promoted from the validated `v1.0.0rc1` candidate per
[#454](https://github.com/Eruhitsuji/lifetxt/issues/454)'s
release-candidate-and-promotion procedure; see "Release status" below for
the full promotion evidence.

[#454](https://github.com/Eruhitsuji/lifetxt/issues/454) narrows the
remaining Stable 1.0 gate to a minimum: a Format 1.0 compatibility baseline,
protection against regressions in core parse/read/write/canonicalization
behavior, no known release-blocking data-loss defect, a working clean-artifact
install/smoke path, and documented (not exhaustively pre-verified) known
limitations. #454 supersedes the exhaustive real-host verification framing
this document previously described as a release prerequisite; it does not
withdraw or invalidate the real-environment evidence already recorded under
the earlier stabilization trackers (#283 and #339), which remains valid,
historical stabilization evidence and may still be resumed as post-Stable-1.0
quality work.

## Highlights

`1.0.0` is lifetxt's first stable release. It provides:

- a dependency-free CLI parsing, validating, filtering, converting, and
  atomically mutating `life.txt` plain-text records (tasks, events, habits,
  status/presence, messages, notes, and journal entries);
- Format 1.0 as an explicit, versioned compatibility contract (see "Stable
  boundary" below);
- ticket, project, and portfolio management on top of the same records
  (workflow history, time tracking, dependencies, custom fields);
- optional Web UI/API (`web` extra), TUI (`tui` extra), MCP server, and
  Remote Safe Mode surfaces for read access and a bounded set of
  revision-checked writes;
- transaction, backup, and recovery tooling for durable multi-file writes;
- CLI self-update (`lifetxt update`) and guarded production deployment
  tooling (`lifetxt server-init`/`server-update`) for git-clone installs.

Every one of these areas has its own dedicated documentation linked from
[readme.md](../../readme.md); this section is a summary, not a substitute
for it. Which of these surfaces carry the stable compatibility promise, and
which remain experimental or deferred, is defined by "Known limitations"
below, the full [compatibility policy](release-compatibility-policy.md), and
the support matrix in `.ai/project/STABLE_RELEASE.yml`.

## Stable boundary

The stable core is the dependency-light CLI and local life.txt workflow. The
supported format write path is unversioned input to Format 1.0. Existing
Format 1.0 documents are no-ops for migration. Legacy, unknown, future, and
downgrade transformations remain inspection-only or refusal-before-write.
See [Format migration](format-migration.md), the
[compatibility matrix](format-compatibility-matrix.md), and the
[Format 1.0 finalization review](format-1.0-finalization-review.md).

## Verification status

Required CI covers the supported Python range, release policy, clean wheel
smoke, and native Windows/macOS core CLI smoke. The minimal clean-artifact
verification defined by #454 (build wheel/sdist, install into a fresh
supported Python environment, confirm both entry points start, run a
representative core smoke) is recorded in
[Stable Release Artifact Verification](stable-release-artifact-verification.md).

Per #454, exhaustive real-host verification of every supported shell,
terminal, browser, filesystem class, SMTP provider, optional client, or
OS/Python combination is explicitly **not** a Stable 1.0 prerequisite. Missing
exhaustive evidence is not by itself a release blocker; a deterministic
failure of the representative core workflow, a Format 1.0 compatibility
violation, a data-loss/corruption defect, a broken build/install/start path,
or a critical security vulnerability is.

## Known limitations

Deferred from the Stable 1.0 gate per #454 (valid post-Stable-1.0 follow-up
work, not release blockers unless a concrete critical/data-loss defect is
found):

- real Web revision deployment evidence (#288-#292);
- exhaustive remote attachment failure/restart evidence (#297-#299);
- cloud-sync/removable/network filesystem verification (#304);
- real terminal and selector matrix verification (#312-#314);
- real SMTP provider verification (#315-#316);
- real browser-engine verification (#317-#318);
- exhaustive external-host verification and its supporting release-harness
  hardening (for example #437/#453);
- exhaustive real-host OS/Python matrix evidence beyond normal CI and the
  minimal clean-install smoke.

Independent of the #454 re-scope, these limitations continue to apply:

- Web writes remain subject to the strict revision evidence and deployment
  gates; read-only Web schema coverage is bounded and route-specific.
- MCP writable tools, Remote writes, and SMTP delivery are not stable promises
  without their dedicated evidence and authorization contracts.
- TUI, browser-engine, fzf/peco, cloud-sync, removable, and network filesystem
  support is limited to environments explicitly recorded by the release
  evidence matrix.
- Diagnostic spans are complete only for the parser families covered by the
  linked issues; diagnostics without source boundaries retain their existing
  representation.

## Upgrading

`1.0.0` is lifetxt's first release; there is no prior published release to
upgrade from, so none of the following migrations apply to this release
itself. They are referenced here because they are the mechanisms a future
release would use, and because installing `1.0.0` must not silently change
data that predates it:

- **Format**: existing `life.txt` files with no `#! format_version:`
  directive remain valid unversioned input and are not modified by
  installing or running `1.0.0`. See [Format migration](format-migration.md)
  for the one supported, explicit, revision-checked migration to
  `format_version: 1`, and the [compatibility matrix](format-compatibility-matrix.md)
  for what remains inspection-only.
- **Configuration**: `.lifetxt.json` files are unaffected by installing
  `1.0.0`; `lifetxt config migrate` remains available for future
  configuration schema changes. See [config.md](config.md).
- **Policy/journal (transactions and recovery)**: existing transaction
  journals and recovery evidence are read by the same version-aware
  inspection path documented in
  [Transaction recovery and strict timers](transaction-recovery-and-strict-timers.md);
  a newer journal a future release might write remains inspect/export-only
  under `1.0.0`, and `1.0.0` never mutates a journal it cannot fully
  understand.
- **Web revision**: the Web UI's optimistic-concurrency revision contract is
  unchanged by this release; see
  [Public surface revisions](public-surface-revisions.md) for its current
  guarantees.

No downgrade path from a future release back to `1.0.0` is defined by this
release; see the [compatibility policy](release-compatibility-policy.md) for
the general deprecation and migration lifecycle that will govern that when it
becomes relevant.

## Release status

Per #454's reduced release-candidate procedure:

- **`v1.0.0rc1`**: cut 2026-08-22 at commit
  `ca1894b6f5571b3862138d84bfe9dc542ebc2551` (the merge commit for PR #467),
  as a [GitHub prerelease](https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.0rc1)
  with the built wheel (`lifetxt-1.0.0rc1-py3-none-any.whl`, sha256
  `fba241ab14bea43eb74281ec106a76f7a9c89aab5318e5dc7f837e1955b12c88`) and
  sdist (`lifetxt-1.0.0rc1.tar.gz`, sha256
  `73ffca299840d4268578d782a3caa2dac416b8e9b115fe03901d694e6eba3cf0`)
  attached. `twine check` passed for both; required CI passed on the
  target commit; the minimal installed-artifact smoke ran directly against
  the installed wheel in a fresh virtual environment: parse/read (`check`),
  create (`quick`), mutate (`complete`), serialize/write (`format canon`,
  `format migrate --write`, both through the revision-checked atomic-write
  contract), re-read, and the recovery-safe write path -- see
  [Stable Release Artifact Verification](stable-release-artifact-verification.md)
  for the full evidence record.
- **`v1.0.0`**: promoted 2026-08-22 at commit
  `4f6eead6587c383eac7ee8e92873bb1596cc1c69` (the merge commit for PR
  #469, the release-metadata-only version bump), identical in product
  behavior to the validated `v1.0.0rc1` candidate. Published as the
  [GitHub Release](https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.0)
  (not a prerelease) with the built wheel (`lifetxt-1.0.0-py3-none-any.whl`,
  sha256 `1da07155a8edfe6dc9ab535d2007d0e65b1ed4688a2ef8c647c7af596dc54e8f`)
  and sdist (`lifetxt-1.0.0.tar.gz`, sha256
  `3be2157c7462193223afce782037ac1cc8260290d9e2ad7d4da65e4fbf74f803`)
  attached. `twine check` passed for both; required CI passed on the
  promoted commit; the same representative core smoke that validated
  `v1.0.0rc1` (parse/read, create, mutate, serialize/write through the
  revision-checked atomic-write contract, re-read, recovery-safe write)
  was re-run against the installed final wheel and passed. A real
  `lifetxt update-check` against the live GitHub API confirmed
  `kind: "release"` (not `"tag"`, since this is a real, non-prerelease
  Release) and `status: "up_to_date"`. Approved by the repository owner
  after #463's open-issue review found no release-blocking defect during
  the RC period.

## Installation smoke

Release validation must use a clean wheel or sdist in a fresh virtual
environment, not an editable checkout:

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

Per #454, the minimal clean-artifact verification recorded in
[Stable Release Artifact Verification](stable-release-artifact-verification.md)
is the release-critical minimum for this smoke; the fuller external
verification procedure remains available for additional, non-blocking
real-host evidence.
