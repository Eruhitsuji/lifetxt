# Informational self-review

Codex implementer. Inspected coverage boundaries, generated-cache exclusions,
symlinks/nonregular inputs, optional configs, manifest identity, diagnostic
semantics, negative tests and unchanged runtime/source/approval pins.

Adjusted scope to include Makefile.envs and the fixed SDK/environment/dependency
configs actually present upstream. Optional root package JSONs are covered if
present; existing src/ comparisons cover upstream nested runtime sources.
Tests verify changed and missing support files through the public staging verifier,
not merely a manifest helper. Profile-only mutation is rejected before runtime
access. No additional unresolved code finding found in this self-review.

An initial combined suite started before the ICU data fetch had completed and
failed the missing icu-charset-readme.txt check. The fetch was completed, its
standalone offline verification passed, and the suite was rerun sequentially.
This was a test-setup ordering error; no passing result is inferred from that run.
The initial output is retained locally, while final output accompanies this package.
A streamed rerun returned without a complete log summary; no pass was inferred.
The final buffered child run returned exit 0 with an asserted complete 86-test
summary (83 successful and 3 skipped), and its full output is retained.
The environment initially lacked ruff and coverage; installed them before the
final verification. No repository dependency/coverage threshold was changed.

The fixed real upstream reconstruction checks 68 bounded support files and
matches both existing fixed curation receipts. Historical custom runtime/object
and browser records were not regenerated. The old source-build proof is preserved;
new reports have the additional staging_input_check field. Independent final-head
implementation/integration review remains pending; self-review is not approval.
