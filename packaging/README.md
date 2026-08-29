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
- `homebrew/` — generated Homebrew Formula output (#572).
- `conda-forge/` — generated conda-forge recipe output (#573).

`winget/generated/`, `scoop/generated/`, `homebrew/generated/`, and
`conda-forge/generated/` are per-release output, not templates — they are
gitignored and regenerated for each release rather than committed.
`homebrew/generated/lifetxt.rb` is the same file
`.github/workflows/homebrew-tap.yml` pushes to
[`Eruhitsuji/homebrew-tap`](https://github.com/Eruhitsuji/homebrew-tap);
running any of these generators locally only writes here, none of them
publish or submit anything by themselves.
