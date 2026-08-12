# Oversized File Decomposition Audit

Issue #366 inventories production and test files around the 50 KB / 1,500-line
review threshold. The authoritative classification is
`config/maintainability/oversized-file-classification-v1.json`.

The audit distinguishes executable implementation, static/resource containers,
and test suites. `web_assets.py` is an asset container and should be handled by
#367 as a resource extraction. `cli.py`, `mcp.py`, `webapp.py`, and the large test
modules have responsibility/coupling risk and receive bounded investigations or
follow-ups. `tui.py`, `server_update.py`, and `agenda.py` are recorded for later
reassessment rather than split solely because of size.

The first CLI seam is documented in #353 and its implementation follow-up is
#384. No production behavior is changed by this audit, and every split or
resource recommendation points to a dedicated issue.
