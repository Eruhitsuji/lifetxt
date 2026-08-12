# Required-Revision Cutover Gate

Issue: #291

Strict mode is a deployment change, not a source-only toggle. It is permitted
only after #290 has a complete passing window and #289 has a supported-client
matrix.

## Pre-cutover checklist

- preserve and back up the metrics/revision store;
- record the exact package commit and configuration revision;
- verify valid `If-Match` writes, missing preconditions, and stale revisions in
  a disposable deployment;
- prepare rollback instructions that restore configuration without deleting
  revision evidence.

## Evidence

Record request method/path, precondition class, response status/code, source
revision before and after, and whether the authoritative file changed. Redact
tokens and local paths. The cutover record must include an operator approval,
rollback result, and service restart result. This repository record documents
the gate; no production deployment is claimed here.
