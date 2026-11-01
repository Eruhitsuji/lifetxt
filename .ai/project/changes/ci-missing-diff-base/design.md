# Conservative diff recovery

The failed Ubuntu 24.04 classifier job ran bash -e and git diff against a
push.before commit absent after full-history checkout. The missing object is
confirmed by the job log; why that object became unreachable is not established.

Guard both diff commands. Either failure discards both lists, including any
partial output. Empty lists already select full, heavy, no-Web, coverage and
Python 3.10 checks. Keep the existing classifier and all aggregate gates.
No speculative fetch is required: availability cannot be guaranteed by fetching
an obsolete SHA. No shell eval, credentials, new dependencies or public API.

Tests execute the actual workflow shell under bash -e in a disposable Git
repository, including docs, new module, missing SHA, zero/empty base and dispatch.
Rollback is a human-approved revert of the recovery PR; no data migration.
