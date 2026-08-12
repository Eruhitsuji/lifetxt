# Web Revision Observe-Mode Verification

Issue: #288

This record defines the external deployment evidence still required; no real
server credentials, hostnames, or deployment result are stored in the
repository.

## Procedure

1. Use a supported Ubuntu deployment created from the documented server
   configuration with `web.revision_mode` set to `observe`.
2. Record the package commit, Python version, OS image, configuration revision
   (not its secret values), and the metrics/revision store path class.
3. Start the service, exercise browser and direct API reads plus one supported
   write, restart the service, and repeat the write after the package update.
4. Confirm the revision/legacy-write counters survive restart and update, and
   capture any fallback event as a separate blocker.

## Evidence format

Store a redacted Markdown table with timestamps, deployment identity, action,
expected result, observed result, and artifact/checksum references. Replace
host paths and tokens with placeholders. A successful record must explicitly
state that this is external deployment evidence, not TestClient evidence.

The repository currently provides the observe-mode implementation and local
contract tests, but this real-environment run remains outstanding.
