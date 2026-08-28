# packaging/

Package-manager-specific build inputs. Each subdirectory is a thin adapter
around the canonical release artifacts (PyPI wheel/sdist, GHCR image,
standalone binaries) built by `.github/workflows/*.yml`; none of them
duplicate lifetxt's own application logic. See
[docs/en/distribution.md](../docs/en/distribution.md) /
[docs/ja/distribution.md](../docs/ja/distribution.md) for the full
distribution architecture.

- `pyinstaller/` — standalone CLI binary build (#570).
- `winget/` — generated winget manifest templates and generator output (#571).
- `scoop/` — generated Scoop manifest and generator output (#571).

`winget/generated/` and `scoop/generated/` are per-release output, not
templates — they are gitignored and regenerated for each release rather than
committed.
