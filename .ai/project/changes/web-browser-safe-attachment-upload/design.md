# Browser-safe attachment upload

## Contract
GET/POST /api/attachments/upload. POST consumes raw application/octet-stream bytes.
Header contract: X-Lifetxt-Upload: 1, compact item ID, UTF-8 percent-encoded basename, exact 64-hex source revision; existing API Bearer authentication applies.
GET returns only upload limit/deadline/active bound/writable state. No new config.

## Authority and transaction
Validate source/id/revision before receiving; repeat before commit. Existing put_attachment commits random create-only file and item reference with MISSING_HASH plus exact source CAS under journal-backed multi-target locks. Dedicated namespace under attachments.root rejects symlink or non-directory ancestors and every existing target (file/directory/link/FIFO). Filename only supplies safe display name/suffix, never a path. The upload exemption from SurfaceTransaction prevents a second single-source commit or stale ETag overwriting the attachment transaction. Unsupported source Format is rejected explicitly.

## Bounds and disclosure
10 MiB or lower existing attachment limit. Bytearray bounds both bytes and tiny-chunk bookkeeping. A total 30-second receive deadline and two active slots include synchronous commit; cancellation keeps the slot until the commit worker finishes. No upload spool files. Existing journal artifacts remain local and intentionally retained for recovery.
Do not call request.body/json/multipart or log bytes/filenames. Reject query/encoding/duplicate contract headers. Marker plus Origin/Fetch-Metadata same-origin checks, no CORS; do not independently trust proxy headers. MIME rules apply to conservative observed content and filename-associated type; reject executable extension/shebang and common native signatures. This is not malware detection.
Response is an explicit allowlist with no domain path/value/targets/journal fields. Full byte and source revisions differ from truncated stored attachment hash. attachment_id is a receipt ID only, not a bearer/resolver; generic safe projection remains #1100/#1101. Legacy generic raw item/text/Markdown and local MCP behavior are unchanged and not advertised as externally redacted.

## Failure and lifecycle
Missing/malformed/stale revisions fail before mutation; mid-receive edits fail on recheck/CAS. Collision never replaces any existing object. Multi-target failure is compensated by existing engine; compensation failure retains recovery evidence and returns bounded 503, requiring local operator recovery. Cancellation/lost response after commit may mean success; refresh before retry. No upload idempotency/replacement/download or automatic retry.

## Review/test viewpoints
Authentication, CSRF, path confinement, process memory/concurrency, spoofed MIME/executables, revisions/Format, compensation, error disclosures, optional-Web import boundary and v1 compatibility. See verification.yml and test_web_attachment_upload.py.
