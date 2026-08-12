# Server-Update Review Extraction Preparation

Issue: #389

The first implementation seam is the pure diff-summary and risk-review path:
`gather_diff_summary`, `classify_risk`, and `format_review_block`. It must retain
the current `ServerUpdateError` step classification, review reasons, approval
matching, and CLI review block text. Process/service orchestration and health
timers remain in `server_update.py` until the pure seam has focused parity
tests.
