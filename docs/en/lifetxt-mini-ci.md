# lifetxt-mini development CI

The Mini Runtime is a strict subset of the Python Core implementation. The
development workflow targets native Linux x86_64 and AArch64, plus static musl
artifacts for both supported architectures. Native jobs execute the built
binary; cross-build jobs verify artifact format and linkage.

Python Core remains the reference implementation. The shared preservation
fixture is validated by Core and Mini in CI. Human-readable output need not be
identical: supported persisted semantics must agree. Same-named Mini commands
introduced later must pair supported arguments and normalized semantic results
with Core; unsupported arguments must be rejected or clearly identified.

Startup and RSS are recorded as hosted-runner measurements, not hard
performance gates. Release publication and packaging remain deferred to the
later release phase.
