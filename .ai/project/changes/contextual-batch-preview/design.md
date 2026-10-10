# Contextual native batch review

Add POST /api/items/preview with {text:string}; leave legacy parse/batch contracts intact.
The read-only endpoint is exempt from mutation revision/clock preconditions while
retaining existing Bearer authentication and read-only access. No write authority added.

Copy effective runtime config, parse proposed text, capture bounded exact-byte
workspace context with #1187, parse captured source texts, then run shared Core
all-value ID and reference diagnostics over workspace + batch. Use synthetic
workspace:N/batch source labels before Core diagnostics so locations do not expose
private paths. Existing unsupported Format or syntax errors block review eligibility.
W213 becomes a DUPLICATE_ID blocking projection; reference/date/custom-key warnings
keep Core severity. Complete proposed records and all diagnostics are returned,
not workspace bodies. Input/source bounds bound memory; graph complexity is Core's
existing behavior. Recursion overflow fails unavailable, without a partial token.

Token v1 is SHA-256(context fingerprint + ':' + exact UTF-8 input digest), prefixed
batch-preview-v1:. This is deterministic identity, not a credential. Manifest mode (including legacy paths globs/directories)
re-resolves sources per snapshot scan; mismatch fails closed. Explicit fixed paths
claim only fixed-path scope. External config requires restart. A writable target
outside effective sources is unavailable rather than omitted. There is no global
lock/atomicity. Error responses contain safe reason categories, never private paths.

Native UI expands every proposed record and complete diagnostic list using DOM
textContent, not raw HTML. Original text is available verbatim. Omission counts
apply to proposed records and diagnostics; workspace bodies are intentionally not
returned. Input edits/late replies invalidate eligibility. Existing Add all remains
unchanged and the UI explicitly states the unguarded context-save gap. #1188/#1189
own save enforcement/recovery; #317/#289 external observation remains separate.

Revert this PR to restore text-only Bulk Preview; no migration or stored-data change.
