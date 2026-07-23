# Release policy gates

lifetxt releases are validated by a versioned, executable policy rather than by a collection of undocumented CI commands.

## Required GitHub Actions job

The CI workflow contains the required job:

```text
Required release policy and clean wheel
```

It runs the `release` profile in a disposable virtual environment, records `release-gate.log`, writes `.cache/release-policy-manifest.json`, and uploads both as the `release-policy-evidence` artifact.

Run the same profile locally:

```bash
python scripts/run_ci_like.py --profile release --python python3.12
```

The other named profiles are:

```bash
python scripts/run_ci_like.py --profile cli
python scripts/run_ci_like.py --profile web
python scripts/run_ci_like.py --profile mcp
python scripts/run_ci_like.py --profile core
```

## Release checks

The executable policy currently enforces the following independently reported contracts:

1. shared CAS rejects a stale writer;
2. offset-aware datetime round-trip remains lossless;
3. `pyproject.toml` package name matches `lifetxt`;
4. package version matches `lifetxt.__version__`;
5. the `lifetxt` console script points to `lifetxt.entrypoint:main`;
6. the `web` optional dependency group exists;
7. the `tui` optional dependency group exists;
8. the golden corpus has a versioned policy;
9. required golden cases remain present and uniquely named;
10. canonical golden outputs remain canonically normalized;
11. every generated and published schema is valid Draft 2020-12 JSON Schema;
12. published schemas exactly match `schema_bundle()`;
13. representative item, diagnostic, capability, and conflict documents validate;
14. Web Japanese chrome and explicit `t()` strings have dictionary coverage while `data-no-i18n` record content is reported separately;
15. new direct write path/call pairs are rejected unless added to the reviewed baseline;
16. optional example files pass stable format diagnostics;
17. sdist and wheel build successfully;
18. Twine accepts the built metadata;
19. the wheel installs into a second clean virtual environment;
20. both `python -m lifetxt` and the installed `lifetxt` console script run from outside the repository.

The manifest includes a deterministic SHA-256 fingerprint. The fingerprint changes when check output, policy versions, or compatibility versions change.

## Direct command

Run only the policy checks and write a manifest:

```bash
python scripts/check_release_policy.py \
  --root . \
  --pretty \
  --output .cache/release-policy-manifest.json \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

The normal CLI route uses the same implementation:

```bash
lifetxt safety release-gate \
  --root . \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

`jsonschema` is deliberately a release-development dependency rather than a runtime dependency. The dependency-free package can inspect a partial report with:

```bash
python scripts/check_release_policy.py --allow-missing-jsonschema
```

That mode is not sufficient for publication.

## Translation coverage

The scanner reads the embedded `UI_STRINGS.ja` dictionary from `HTML_PAGE`, collects visible static text and readable attributes, and inspects quoted strings passed to `t()`.

Record containers marked with `data-no-i18n` or known record-content classes are excluded and counted separately. A title such as `Done` written by a user must never be treated as interface chrome.

When a new button, label, placeholder, title, help string, or explicit `t()` literal is added, its English source text must also be added to `UI_STRINGS.ja` in the same change.

## Write-route baseline

`config/release/write-route-baseline-v1.json` records reviewed pre-existing path/call pairs. Line numbers are not part of the key, so ordinary edits do not create false failures.

A new direct call such as these fails the release gate:

```text
open(..., "w"|"a"|"x")
os.replace(...)
atomic_write_bytes(...)
```

Do not update the baseline merely to make CI green. First determine whether the call is an authoritative life.txt/state write, an export, a generated artifact, or a cache. Authoritative writes must use the shared mutation boundary. A baseline change must explain why the remaining direct write is reviewed and safe.

## Golden policy

`tests/golden/policy-v1.json` pins the corpus version, minimum case count, required fields, and required case names.

Changing canonical output or removing a required case requires:

1. a corpus version bump;
2. an explicit migration note;
3. updated compatibility expectations;
4. review of downgrade and older-client behavior.

## Clean-wheel verification

The release profile builds both sdist and wheel, runs Twine metadata checks, creates another virtual environment, installs only the wheel, changes to a directory outside the repository, and runs module, console-script, and parser smoke tests. This prevents an editable checkout from hiding missing package files or broken entry points.

## Legacy Web revision migration telemetry

Before the temporary Web revision fallback can be removed, its usage must be measurable.

```http
GET /api/revision-metrics
```

The response reports:

- whether fallback is enabled;
- total fallback writes;
- counts by endpoint path;
- the UTC time of the most recent fallback write;
- the documented removal condition.

A fallback write also returns:

```http
Warning: 299 lifetxt "Legacy write without client revision; fetch /api/revision and send If-Match."
Deprecation: true
X-Lifetxt-Legacy-Revision-Fallback: used
```

Revision-aware writes do not increment the counter. Strict sessions still reject a missing revision with HTTP 428.
