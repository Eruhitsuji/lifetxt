# Release Artifact Evidence

`scripts/release_evidence.py` builds the release wheel and sdist once and
generates evidence from that exact pair:

```console
python scripts/release_evidence.py --output release-evidence
```

The output contains:

- `SHA256SUMS`, with one SHA-256 entry per artifact;
- `sbom.cdx.json`, a machine-readable CycloneDX 1.5 dependency manifest for
  declared runtime dependencies plus the optional-extra policy; and
- `provenance.json`, containing package/version, source commit/tag, Python and
  platform, build-tool versions, workflow run identifier, and the same artifact
  hashes.

The build uses `--no-isolation` so the recorded build-tool environment is the
one selected by the release job. Build inputs are temporary and removed after
the artifact pair is copied to the requested output directory. The evidence
writer records no absolute paths, credentials, tokens, or unrelated environment
variables. `GITHUB_RUN_ID` is the only workflow environment value retained; a
local run records `local`.

To verify an artifact after download, compare its SHA-256 with `SHA256SUMS`:

```console
sha256sum lifetxt-*.whl
sha256sum -c SHA256SUMS
```

On PowerShell, use `Get-FileHash` and compare the `Hash` value with the matching
line. Release evidence must be generated from the same artifact directory that
passes the release smoke and policy checks; do not rebuild a second pair for
publication.
