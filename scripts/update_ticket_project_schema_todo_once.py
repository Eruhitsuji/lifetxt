"""Apply the completed ticket-report schema registration to todo.md once."""

from pathlib import Path

path = Path("todo.md")
text = path.read_text(encoding="utf-8")
replacements = {
    "The ticket batches add the `record:ticket` model and local management operations plus a versioned, read-only `ticket-project-report-v1` aggregation contract with deterministic summary, board, attention, dependency, due-date, stale, assignment, severity, and estimate/elapsed metrics.":
        "The ticket batches add the `record:ticket` model and local management operations plus a versioned, read-only `ticket-project-report-v1` aggregation contract with deterministic summary, board, attention, dependency, due-date, stale, assignment, severity, and estimate/elapsed metrics; register the report through `schema_extensions_v16`; and expand the generated Draft 2020-12 schema bundle to 56 documents.",
    "under `ticket-project-report-v1`; it is directly inspectable through":
        "under `ticket-project-report-v1`; the contract is installed through `schema_extensions_v16` and emitted by the 56-document `format schemas` bundle; it is directly inspectable through",
    "embed formulas/caveats, and conform to `ticket-project-report-v1.schema.json`. English/Japanese documentation exists":
        "embed formulas/caveats, conform to `ticket-project-report-v1.schema.json`, and register the contract and release-policy sample through `schema_extensions_v16` in the 56-document generated schema bundle. English/Japanese documentation exists",
    "- [ ] Register `ticket-project-report-v1.schema.json` in the schema bundle/index and capability discovery, add schema compatibility fixtures, and extend the report with version/sprint attention only after authoritative `record:version` and `record:sprint` contracts exist.":
        "- [ ] Publish `ticket-project-report-v1` through capability discovery, add cross-version schema compatibility fixtures, and extend the report with version/sprint attention only after authoritative `record:version` and `record:sprint` contracts exist. The schema itself, release-policy sample, generated bundle entry, and `format schemas` count/filename verification are implemented through `schema_extensions_v16`.",
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit("todo.md text not found: %s" % old[:100])
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
