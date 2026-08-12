# Remote Attachment Authorization and Bounds

Issue: #299

## Verification matrix

Test allowed and denied source roots, files outside the configured root,
caller-visibility differences, transaction lookup before and after retention
expiry, and files at/beyond the selected chunk and total-size limits. Include
both authorized and unauthorized clients and ensure package contents cannot
escape the configured source boundary.

## Evidence requirements

Record the configured policy class, request class, response code, bounded
size/chunk values, retention state, and whether any package was produced.
Never commit real paths, tokens, file contents, or client identifiers. The
final support statement must distinguish tested limits from untested limits;
this preparation record does not claim real-client or large-file coverage.
