# Filesystem Recovery Support Matrix

Issue: #304

## Environments

Where safely available, test a normal local filesystem, cloud-synchronized
directory, removable media, and network share. Identify filesystem/provider,
mount/options class, OS, and whether interruption was process crash or actual
power loss. Do not label an environment supported from a simulated directory.

## Operations and result

For each environment run normal write, interrupted write, journal inspect,
recovery, and restore. Record byte-integrity/revision results, recovery
artifacts, and any explicit refusal. Publish a matrix with `verified`,
`unsupported`, or `not tested`; keep physical power-loss evidence separate
from subprocess interruption. This record defines the evidence format and does
not claim portability beyond tested environments.
