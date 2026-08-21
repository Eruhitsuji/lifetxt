# Stable Release Notes Draft

This draft is prepared for the first stable release. The release version and
tag are intentionally left to the release decision; this document must not be
read as a published release announcement.

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
- The version/tag is intentionally unset in this draft. Release authority must
  select it after the Format 1.0 baseline confirmation and the minimal
  clean-artifact verification pass; #454 names `1.0.0rc1` and `1.0.0` as the
  intended candidate/release identifiers.

## Installation smoke

Release validation must use a clean wheel or sdist in a fresh virtual
environment, not an editable checkout:

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

The exact artifact hash, Python version, OS, and result must be recorded using
the external verification procedure before a stable tag is promoted.
