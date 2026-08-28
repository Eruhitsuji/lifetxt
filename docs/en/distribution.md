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

## 2. GHCR (OCI container image)

Tracks [#569](https://github.com/Eruhitsuji/lifetxt/issues/569).

Docker is primarily the Web/MCP/server/NAS/VPS/home-server/CI installation
path, not a replacement for the normal local CLI installation covered above.

### Image contract

- `ENTRYPOINT ["lifetxt"]`, no default `CMD` beyond `--help` — the image
  behaves like the CLI binary itself: `docker run ghcr.io/eruhitsuji/lifetxt:<version> check life.txt`
  runs the same thing `lifetxt check life.txt` would.
- Runs as a non-root user (uid 1000) with `/data` as its working directory
  and declared volume; mount your `life.txt`/configuration there.
- Built with the `[web]` extra installed, so the same image can serve the
  Web API/UI with no separate build.
- Supported architectures: `linux/amd64` and `linux/arm64`.
- No development files, build tooling, `.git`, or mutable local state are
  shipped — the image is built in two stages (build a wheel, then install
  only that wheel into a fresh runtime layer).

### Tags

| Tag | Meaning |
| --- | --- |
| `ghcr.io/eruhitsuji/lifetxt:<version>` (e.g. `1.0.0`) | Immutable, matches a Git tag/GitHub Release/PyPI release exactly. Prefer this in production. |
| `ghcr.io/eruhitsuji/lifetxt:<major>.<minor>` | Convenience tag, moves to the newest patch release in that line. |
| `ghcr.io/eruhitsuji/lifetxt:<major>` | Convenience tag, moves to the newest release in that major line. |
| `ghcr.io/eruhitsuji/lifetxt:latest` | Convenience tag, moves to the newest stable (non-prerelease) release. Never published for prerelease tags (`rc`/`a`/`b` suffixes). |

Pin the immutable version tag for production; use a convenience tag only
where you deliberately want automatic upgrades.

### CLI mode

```sh
docker pull ghcr.io/eruhitsuji/lifetxt:<version>

docker run --rm \
  -v "$PWD:/data" \
  ghcr.io/eruhitsuji/lifetxt:<version> \
  check /data/life.txt
```

### Web mode

```sh
docker run --rm \
  -p 8000:8000 \
  -v "$PWD:/data" \
  ghcr.io/eruhitsuji/lifetxt:<version> \
  serve /data/life.txt --host 0.0.0.0 --port 8000 --token-env LIFETXT_API_TOKEN \
  -e LIFETXT_API_TOKEN=change-me
```

(Put `-e LIFETXT_API_TOKEN=...` before the image name like any other
`docker run` flag; it is shown last above only for readability.)

### MCP mode

MCP is a stdio protocol — an MCP client spawns the process and talks to its
stdin/stdout directly, so it does not fit a detached, networked
`docker compose up -d` service. Run it attached instead:

```sh
docker run -i --rm -v "$PWD:/data" ghcr.io/eruhitsuji/lifetxt:<version> mcp /data/life.txt
```

Configure your MCP client's `command`/`args` to invoke `docker` with this
exact argument list (see
[ai-integration.md](./ai-integration.md) for the generic MCP client-setup
pattern this substitutes into).

### Docker Compose (persistent Web deployment)

[`docker-compose.yml`](../../docker-compose.yml) at the repository root is a
checked-in, ready-to-copy example:

```sh
cp docker-compose.env.example .env   # then edit LIFETXT_API_TOKEN
mkdir -p data && cp examples/minimal_life.txt data/life.txt
docker compose up -d
curl http://127.0.0.1:8000/api/health
```

It pins nothing by default (`LIFETXT_VERSION` defaults to the `latest`
convenience tag); set `LIFETXT_VERSION=1.0.0` in `.env` to pin an immutable
release for production use.

### Read-only vs. writable usage

Add `--read-only` to the `serve` command for a demo/browse-only deployment
(matches the CLI's own `--read-only` flag — nothing Docker-specific).
Without it, the mounted `life.txt` is writable by the container's uid-1000
user; make sure the host-side file/directory permissions allow that.

### Update/pinning guidance

- Immutable version tags never change once published — safe to pin
  indefinitely.
- `latest` and the `<major>`/`<major>.<minor>` convenience tags are
  re-pointed by `docker-publish.yml` on every matching release; re-pull
  (`docker pull` / `docker compose pull`) to pick up a new version, they are
  not pushed automatically to a running container.
- The base image (`python:3.12-slim`) receives periodic OS-level security
  patches independent of lifetxt's own releases; rebuilding/re-pulling a
  convenience tag periodically is recommended even between lifetxt releases.

### How images reach GHCR

`.github/workflows/docker-publish.yml` runs on every `v*.*.*` tag push (the
same trigger as `release.yml`):

1. Confirm the tag matches `pyproject.toml`'s version.
2. Build a local single-architecture image and smoke test it: a `check`
   command against a mounted example, confirmation the process runs as
   uid 1000, and a `serve` invocation polled until `/api/health` responds.
3. Build the real multi-arch (`linux/amd64`, `linux/arm64`) image with
   Buildx/QEMU and push it to `ghcr.io/eruhitsuji/lifetxt` with the tag
   policy above, using GHCR's own `GITHUB_TOKEN` authentication — no
   separate account or credential setup is required.

`workflow_dispatch` supports building and smoke-testing without pushing
(`push: false`, the default), for verifying a change to the Dockerfile
itself before it reaches a real tag.

### Contributor vs. end-user installs

Contributors changing lifetxt's own source still use an editable install
(`pip install -e ".[dev]"`, see
[Development environment](../../readme.md#development-environment)); `lifetxt
update`/`lifetxt server-update` specifically depend on that editable, git-backed
install to fast-forward the checkout. `pip install lifetxt` (this document) is
the separate, ordinary end-user path and never assumes a git checkout exists.
