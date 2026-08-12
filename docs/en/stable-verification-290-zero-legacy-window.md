# Zero-Legacy-Write Observation Window

Issue: #290

## Gate definition

The observation window starts only after the deployment identity, supported
client versions, metric counters, and required duration are recorded. The
window is invalidated by any write using compatibility fallback, by a metric
gap, or by an untracked client version.

## Collection record

For every interval record the deployment revision, observe-mode counters,
supported client/version set, write count, legacy-write count, and monitoring
availability. Keep values and timestamps, but redact host paths, headers, and
credentials. A zero count is meaningful only when the counter source covered
the complete interval.

## Decision

Produce an explicit `pass`, `reset`, or `blocked` decision with the reason and
next action. No strict-mode change may rely on an incomplete or local-only
window. This record defines the gate and does not assert that a qualifying
window has been observed yet.
