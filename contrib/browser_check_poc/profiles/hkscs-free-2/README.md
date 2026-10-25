# Explicit HKSCS-free runtime profile 2

This distribution identity binds candidate hkscs-free-rebuild-20261025-161559.
Source recipe lifetxt-hkscs-free-1 and its ten source archive hashes are reused.
Raw source/object/WASM reports retain that recipe label; they are not evidence
that the legacy runtime bytes were restored. Three runtime files differ.
The candidate record is a historical measurement before profile integration;
its distribution_profile_adopted=false is retained rather than rewritten.
profile.json binds every measured report, candidate, environment and observation.
source-build-proof.json includes the actual 68-file staging_input_check.
ICU source-specific comparison was rerun against the curated archive.
Independent HKSCS removal/ICU applicability/distribution acceptance is pending.
Owner authorized this integration; publication and deployment remain unapproved.

Build a new local output directory explicitly:

```
python scripts/build_website_checker.py --output .cache/checker-profile2 --hkscs-profile lifetxt-hkscs-free-2 --hkscs-runtime CANDIDATE --source-cache DERIVED_SOURCES
```

Omitting --hkscs-profile preserves legacy profile 1. Crossed runtimes fail.
Nothing changes the introduction-only Pages build.

## Audit selection contract

The generic distribution auditor discovers one of the finite known identities
from the artifact manifest, then checks that profile's complete fixed lock.
When a caller expects one particular runtime identity, pass it explicitly:

```python
from contrib.browser_check_poc.custom_distribution import audit

audit(artifact, runtime_profile="lifetxt-hkscs-free-2")
```

Passing runtime_profile="lifetxt-hkscs-free-1" rejects a profile2 artifact.
Discovery is not a guarantee that a caller's unstated profile expectation holds.
Source-guide generation rejects a missing or repeated recipe label; template
wording changes require an explicit generator update and test review.
