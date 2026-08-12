# Web Client Revision Preconditions

Issue: #289

## Client inventory

The verification set must cover the browser bundle's revision discovery and
write wrapper, direct API callers, attachment writes, and work-session writes.
For each path record the method/path, the revision source, the `If-Match`
header construction, stale-revision response handling, and whether the client
is supported or intentionally legacy/read-only.

## Local evidence

Use focused route/client tests to prove valid, missing, and stale revision
preconditions without mutating a real workspace. Add a real-browser/API run to
the evidence only after the observe-mode deployment from #288 is available.

## External evidence

The final redacted record must include client version, endpoint, request header
presence (never the token value), response status/code, and confirmation that a
stale request did not overwrite authoritative data. This document is a
verification contract; it does not claim that the supported-client matrix has
already been exercised.
