# Verification input trust boundary

Operations/High review and Bug/High correction, W-model. Source baseline is
197583c88072b37cbc27ce198bbbb1b483c374ed (merged #1419/#1420).
Work branch fix/distribution-review-input-binding; final PR base main.
Owner/Integrator/Merge Authority Eruhitsuji; correction implementer Codex.

The old verifier checked the curated archive against source-removal.json and
build inputs against build-profile.json from the same mutable workspace. It
then reconstructed compiler inputs using that workspace curated archive. A
changed input and matching receipt could therefore describe an unpinned build.
The separate final custom distribution lock already rejected different bytes;
this finding concerns the standalone evidence producer, not a demonstrated
publication bypass.

Reuse hkscs_free.prepare_build in a fresh temporary directory, which verifies
fixed Pyodide/CPython/xz/zstd/SQLite archive bytes and applies the reviewed local
transformations. Compare reconstructed profile and removal receipt, curated
archive digest, and exact bytes of all four modified compiler inputs. Do this
before existing library/object/source/runtime checks. The temporary stage is
removed on success and error; no downloads, compiler execution or new binary.
This adds temporary extraction/compression time and disk use. Existing pinned
host/compression reproducibility limits apply and fail closed on differing bytes.

Viewpoints: requirements completeness; source identity; receipt independence;
notice/source retention; runtime compatibility; publication authority. Tests
exercise the real staging implementation on explicitly synthetic locked archives,
including self-consistent forgeries and a missing cache. Real fixed inputs are
checked separately when obtainable. Final distribution acceptance remains
separate; an implementing Codex cannot approve its own correction or satisfy the
publication evaluator's separate-tool/human review requirement.

Rollback: human-reviewed revert; no deployment or binary changes.
