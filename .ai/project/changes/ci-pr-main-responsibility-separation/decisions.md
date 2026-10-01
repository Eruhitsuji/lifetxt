# Decisions

- Use an event-aware Python matrix instead of duplicating the full test job.
- Keep mypy and release-document validation on both PR and main.
- Move traceability into a lightweight PR-only job.
- Remove release artifact work from general CI; the existing Release workflow remains its owner.
- Treat every non-success dependency result as aggregate-gate failure.
- Key cancellation by PR number and make main/manual concurrency groups unique by run ID.
- Defer path-based conditional execution to #1011.
