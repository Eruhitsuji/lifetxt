# Dependency Security Audit

This is the release-focused dependency audit for issue #351. It covers the
declared core dependency and the stable `web` and `tui` extras from
`pyproject.toml`; the scanner itself is installed only in a development/release
environment and is not a lifetxt runtime dependency.

## Reproduce

```console
python -m pip install pip-audit pip-licenses
python scripts/dependency_audit.py --output docs/en/dependency-audit.json
```

The script records the audit date, direct requirement inputs, installed versions,
package-declared licenses, URLs, pip-audit version, vulnerability results, and
packages that the service could not scan. It does not record local paths,
credentials, or environment variable values.

## Current disposition

The committed JSON evidence is a point-in-time record, not a claim that future
or undisclosed vulnerabilities do not exist. A vulnerable direct or transitive
package must be handled by a dedicated issue or an explicit release decision;
transitive findings are retained with the package that introduced them.

The local lifetxt checkout is intentionally reported as unscanned because it is
not published on PyPI. This audit therefore complements, rather than replaces,
the code-level and release-wide security review tracked by #361.
