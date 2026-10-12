# lifetxt v1.0.4.1 release notes

This correction release repairs the Python/Core and standalone publication paths that failed for v1.0.4.
The existing v1.0.4 tag is retained; the corrected source is released under a new v1.0.4.1 tag.
These notes are prepared before publication. See [#1298](https://github.com/Eruhitsuji/lifetxt/issues/1298) for actual per-channel acceptance status.

## Changes since v1.0.4

- [#1301](https://github.com/Eruhitsuji/lifetxt/pull/1301): fix cold-process schema bootstrap ordering so the release gate validates the full schema bundle.
- The same PR explicitly includes dynamically loaded schema_extensions_v4 through v34 in PyInstaller, fixing the standalone startup ModuleNotFoundError.
- [#1303](https://github.com/Eruhitsuji/lifetxt/pull/1303): support optional numeric vX.Y.Z.N correction releases while keeping ordinary vX.Y.Z numbering. An omitted N is zero; updates compare numeric release components.
- Core/Mini CLI and the tag use 1.0.4.1. Cargo/Tauri internal SemVer metadata uses 1.0.4+1; build metadata is not used for update ordering.

## Compatibility and limitations

No life.txt Format 1.0 syntax change or data migration. Changes already included in v1.0.4 are retained.
Mini is the Python-free Linux strict-subset runtime, not feature-equivalent to Python Core despite its shared release identity.
Official Mini targets are Linux x86_64 and AArch64. Use the appropriate Core, standalone or Desktop artifacts on Windows/macOS.
Desktop OS version metadata alone does not guarantee subversion upgrade ordering. Native installations and upgrades require per-channel acceptance.
Record pre-publication checks, post-publication reachability and unexecuted native checks separately in #1298/#911.

## Install and update

After publication: `python -m pip install --upgrade lifetxt==1.0.4.1`.
Verify that `lifetxt --version` prints `lifetxt 1.0.4.1`.
Download the correct product/OS/architecture from [v1.0.4.1 Release](https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.4.1), and verify it against the final SHA256SUMS from the same release.
See [Distribution and installation](distribution.md) for channel instructions, Mini boundaries and checksum verification.
Homebrew/winget/Scoop/conda require downstream generation or external propagation; consult #1298 for the actual state.
