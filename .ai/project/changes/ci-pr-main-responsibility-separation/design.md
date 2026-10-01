# Design

Lifecycle phase: implementation and developer verification. This M task cannot
be split further safely because event conditions, the `needs` graph, aggregate
gates, and main failure automation must change together; landing only part
would either duplicate the old matrix or create an unmonitored/falsely green
state.

The `test` matrix is event-aware: pull requests receive Python 3.12, while
push/manual runs receive Python 3.10, 3.11, and 3.12. Compatibility jobs use an
explicit non-PR condition. Type and documentation jobs serve both flows. A
small PR-only traceability job preserves the current base-SHA/PR-URL contract
without invoking artifact release work.

`PR gate` and `Main compatibility gate` both run under `always()` and inspect
every required `needs.*.result`; any value other than `success`, including
failure, cancellation, or an unexpected skip, fails the aggregate. The main
failure Issue job now depends only on the stable main aggregate result.

Concurrency keys same-PR work by pull-request number and enables cancellation
only for pull requests. Main and manual runs include `run_id`, so they cannot
cancel one another. Release workflows are separate and unchanged.
