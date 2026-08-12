# Stable Remote Read Smoke Evidence

This record closes the `remote-read-client` evidence requirement in the stable
support matrix. It covers the read-only client path only; Remote writes remain
experimental.

## Scope and safety

The server profile used for this smoke has a `reader` principal, no mutation
scope, and loopback-only transport. The token is supplied through an environment
variable and is never written to the profile or captured output. Evidence must
replace deployed URLs, usernames, filesystem paths, and tokens with placeholders
before it is committed.

The same client commands are used for a supported deployed profile:

```console
lifetxt remote test PROFILE
lifetxt remote resources PROFILE
lifetxt remote get PROFILE tickets --param limit=5
lifetxt remote diagnose PROFILE
```

`PROFILE` is intentionally not recorded here. Operators provide it through the
documented profile store and keep its credentials outside the repository.

## Contract checks

The release smoke must demonstrate all of the following:

| Check | Expected evidence |
| --- | --- |
| Read authorization | A reader can fetch capabilities and permitted resources; a write principal is not required. |
| Bounded pagination | `tickets` returns `next_cursor` and `has_more`; following the cursor reaches a terminal page with `next_cursor: null`. |
| Revision consistency | A page's `revision` is accepted as `since_revision`; a changed workspace returns `REMOTE_RESOURCE_REVISION_CHANGED` and the client reports a restart-from-first-page diagnostic. |
| Resource metadata | Capability revision and protocol negotiation are present and consistent between the response body and headers. |
| Stale/restarted session | A session or server restart produces a bounded connection/session diagnostic; it does not expose a traceback or secret. |
| Write boundary | The smoke invokes no Remote write route and does not grant mutation capability. |

## Reproducible verification

The repository-level contract checks are:

```console
python -m unittest tests.test_remote_pagination tests.test_remote_compatibility_v21 tests.test_remote_client_v20
python -m lifetxt check examples/minimal_life.txt
```

The first command exercises the real Remote HTTP route, including reader
authorization, terminal cursor behavior, stale revision rejection, and
capability-revision diagnostics. The deployed-profile commands above are the
required installed-client smoke before an RC is promoted.

## Evidence record

- Issue: #359
- Support-matrix surface: `remote-read-client`
- Transport: documented Remote profile path; loopback HTTP is permitted only for
  the disposable local smoke profile
- Principal: read-only `reader` role
- Mutation capability: not granted
- Recorded artifacts: command summary, pass/fail results, protocol version, and
  capability revision only
- Redaction: no credentials, tokens, deployed URLs, or local source paths

This document is a release evidence index, not a credential or environment
configuration file.
