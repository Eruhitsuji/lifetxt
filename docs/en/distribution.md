# lifetxt distribution channels

This document tracks the canonical distribution architecture from
[#567](https://github.com/Eruhitsuji/lifetxt/issues/567): one release
tag/version, built into a small set of canonical artifacts (Python
wheel/sdist, an OCI image, and standalone platform binaries), then exposed
through the package managers appropriate to each audience. Package-manager
metadata (winget, Homebrew, conda-forge) stays a thin adapter around those
canonical artifacts rather than a second, independent build.

```text
                         lifetxt source
                               |
                         version / tag
                               |
              +----------------+----------------+
              |                                 |
       Python artifacts                    Native artifacts
       wheel / sdist                  Win / Linux / macOS
              |                                 |
            PyPI                         GitHub Release
              |                                 |
       pip / uv / pipx          winget / Scoop / Homebrew
              |
         conda-forge

                     OCI container image
                              |
                             GHCR
                              |
                     Docker / Compose
```

Every channel below identifies the same source revision for a given version:
the Git tag, the `pyproject.toml` `project.version`, and every published
artifact's own embedded version must agree. `scripts/check_release_tag_version.py`
enforces the tag/version half of that guarantee before any workflow proceeds.

## 1. PyPI (Python package)

Tracks [#568](https://github.com/Eruhitsuji/lifetxt/issues/568).

### End-user installation

```sh
pip install lifetxt
uv tool install lifetxt
pipx install lifetxt
uvx lifetxt --help

# optional extras
pip install "lifetxt[web]"
pip install "lifetxt[tui]"
```

`lifetxt --version` reports the installed release version once published.

### How releases reach PyPI

`.github/workflows/release.yml` runs on every `v*.*.*` tag push:

1. Check out the repository at the exact tag.
2. Confirm the tag matches `pyproject.toml`'s `project.version`
   (`scripts/check_release_tag_version.py`) — a moving `main` tree can never
   be published under a version that already identifies an earlier release.
3. Run the existing release-policy profile (`scripts/run_ci_like.py --profile release`).
4. Build wheel and sdist with checksums, an SBOM, and provenance metadata
   (`scripts/release_evidence.py`, already used for release evidence records).
5. Validate package metadata with `twine check`.
6. Install the built wheel into a clean virtual environment and smoke test
   `lifetxt --version` / `lifetxt check`.
7. Publish to PyPI via [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   (OIDC — no long-lived upload token stored in this repository).
8. Attach the same wheel/sdist/checksums/SBOM/provenance to the matching
   GitHub Release.

### One-time PyPI-side setup (maintainer action, not automatable from here)

PyPI Trusted Publishing must be linked from the PyPI project itself before
step 7 can succeed — this cannot be done from inside this repository or by
an AI agent, since it requires the `lifetxt` PyPI project owner's own PyPI
account:

1. Reserve the `lifetxt` project name on PyPI (first publish must currently
   be a manual `twine upload` of one build, *or* PyPI's "pending publisher"
   flow, which lets you register a Trusted Publisher before the project
   exists yet — see PyPI's own documentation for the current option).
2. On <https://pypi.org/manage/project/lifetxt/settings/publishing/>, add a
   GitHub Trusted Publisher:
   - Owner: `Eruhitsuji`
   - Repository: `lifetxt`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. In this repository's Settings → Environments, create an environment named
   `pypi` (GitHub creates it automatically on first workflow run that
   references it, but creating it ahead of time lets you add required
   reviewers or a deployment branch rule if you want extra release-review
   friction).

Until step 2 is done, `release.yml`'s `publish-pypi` job runs and fails
cleanly at the PyPI OIDC exchange — it does not publish a partial or
malformed release.

### Verifying a release once published

```sh
python -m venv /tmp/lifetxt-pypi-smoke
/tmp/lifetxt-pypi-smoke/bin/pip install lifetxt
/tmp/lifetxt-pypi-smoke/bin/lifetxt --version
/tmp/lifetxt-pypi-smoke/bin/lifetxt check examples/minimal_life.txt

uv tool install lifetxt && lifetxt --version
pipx install lifetxt && lifetxt --version
uvx lifetxt --help
```

### Contributor vs. end-user installs

Contributors changing lifetxt's own source still use an editable install
(`pip install -e ".[dev]"`, see
[Development environment](../../readme.md#development-environment)); `lifetxt
update`/`lifetxt server-update` specifically depend on that editable, git-backed
install to fast-forward the checkout. `pip install lifetxt` (this document) is
the separate, ordinary end-user path and never assumes a git checkout exists.
