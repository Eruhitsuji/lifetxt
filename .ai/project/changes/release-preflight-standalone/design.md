# Design

Reuse the merged Core helper's context/source checks and bounded subprocess
runner, and the common schema-1 proof contract. Build from the immutable source
checkout with the existing PyInstaller spec and bundled web/tui extras. Check
the actual native host OS/architecture and 64-bit interpreter; never cross-build.

Retain all five supported platform targets, native runners and artifact names.
Execute the frozen binary outside source with temporary HOME/config/data paths
and without PYTHONHOME/PYTHONPATH. Preserve version, check, init/doctor, paths
with spaces/non-ASCII and timezone smoke. A version mismatch or failed command
cannot produce a successful build report. Hash the binary and LF checksum only
after successful smoke; recheck source/controller and seal the report.

Upload the two-file payload before binding its action-provided archive reference
to the unchanged report and byte digests. Upload proof separately. Matrix job
outputs cannot represent all targets, so use target-named payload/proof artifacts
and require the future parent to reconcile all five with API metadata. No public
manifest writer, tag, release, registry token, environment or legacy workflow
change exists here. Actual OS-matrix execution and Actions transport remain
integration work in #1321; local Linux evidence is not proof for other targets.

Rollback is a PR revert; no published data or public bytes are affected.
