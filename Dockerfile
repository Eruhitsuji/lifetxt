# Official lifetxt OCI image. Two stages: build a wheel from source, then
# install only that wheel (plus its declared extras) into a slim runtime
# image, so the published image never carries build tooling, the git
# checkout, caches, or other development-only state.
#
# ENTRYPOINT maps directly onto the lifetxt CLI (`docker run <image> check
# life.txt` behaves like `lifetxt check life.txt`); there is no default
# command, since this image serves CLI batch use, one-off `check`/`serve`
# invocations, and long-running Web/MCP deployment equally, and none of
# those is a safe universal default.
#
# See docs/en/distribution.md for the full usage contract (CLI, Web, MCP,
# Compose) and image tag/versioning policy.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS build

WORKDIR /src

COPY pyproject.toml readme.md LICENSE ./
COPY lifetxt/ ./lifetxt/

RUN pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel --outdir /dist


FROM python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.title="lifetxt" \
      org.opencontainers.image.description="Parser, validator, converter, CLI, and optional web UI for life.txt." \
      org.opencontainers.image.source="https://github.com/Eruhitsuji/lifetxt" \
      org.opencontainers.image.licenses="MIT"

# lifetxt's core has no third-party runtime dependency; [web] is included by
# default so the same image can serve the Web UI/API without a second build.
# Extend to `.[web,tui]` here if a future release wants the interactive TUI
# available inside the container too.
COPY --from=build /dist/*.whl /tmp/
# The wheel filename is resolved into a shell variable first: a literal
# glob like `/tmp/*.whl[web]` is parsed by the shell as "*.whl" followed by
# a one-character class matching w/e/b, not as pip's extras syntax, and
# silently matches no file.
RUN WHEEL_FILE="$(ls /tmp/*.whl)" \
    && pip install --no-cache-dir "${WHEEL_FILE}[web]" \
    && rm -rf /tmp/*.whl /root/.cache

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin lifetxt \
    && mkdir -p /data \
    && chown lifetxt:lifetxt /data

USER lifetxt
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8000

ENTRYPOINT ["lifetxt"]
CMD ["--help"]
