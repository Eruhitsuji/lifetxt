"""One-shot precise roadmap update for the ticket/project surface integration."""

from pathlib import Path


PATH = Path("todo.md")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit("%s: expected one match, found %d" % (label, count))
    return text.replace(old, new, 1)


def main():
    text = PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "Last updated: 2026-07-25 (updated x115)",
        "Last updated: 2026-07-25 (updated x116)",
        "update counter",
    )
    text = replace_once(
        text,
        "development-ticket-core, and shared ticket/project-report batches.",
        "development-ticket-core, shared ticket/project-report, and cross-surface ticket/project integration batches.",
        "active batch list",
    )
    text = replace_once(
        text,
        "The ticket batches add the `record:ticket` model and local management operations plus a versioned, read-only `ticket-project-report-v1` aggregation contract with deterministic summary, board, attention, dependency, due-date, stale, assignment, severity, and estimate/elapsed metrics; register the report through `schema_extensions_v16`; and expand the generated Draft 2020-12 schema bundle to 56 documents.",
        "The ticket batches add the `record:ticket` model and local management operations plus a versioned, read-only `ticket-project-report-v1` aggregation contract with deterministic summary, board, attention, dependency, due-date, stale, assignment, severity, and estimate/elapsed metrics; register the report through `schema_extensions_v16`; integrate the exact same report into the main `ticket`/`project` CLI trees, Project Hub, Portfolio, and read-only MCP; normalize configured project aliases before aggregation; derive terminal statuses, high severities, and stale windows from effective ticketing configuration while retaining explicit overrides; publish the operations and effective settings through capability discovery; and keep the generated Draft 2020-12 schema bundle at 56 documents.",
        "ticket batch summary",
    )
    text = replace_once(
        text,
        "Remaining ticket work focuses on workflow/history, exact-revision writes, richer planning records, configuration-backed custom fields, and cross-surface adoption of the shared report rather than rebuilding ticket aggregation.",
        "Remaining ticket work focuses on workflow/history, exact-revision writes, richer planning records, configuration-backed custom fields, report revision/privacy metadata, registry-backed display ordering and diagnostics, and the still-unimplemented Web/TUI/saved-view/remote/command-center adoption rather than rebuilding ticket aggregation.",
        "remaining ticket work",
    )
    text = replace_once(
        text,
        "7. Finish project archive, validation, cross-surface Project Hub exposure, permissions, and privacy on top of the implemented Project/Portfolio read foundation.",
        "7. Finish project archive, record validation, Web/TUI/saved-view/remote Project Hub exposure, permissions, privacy, and revision-aware report delivery on top of the implemented CLI/MCP Project/Portfolio read foundation.",
        "priority project track",
    )
    text = replace_once(
        text,
        "8. Harden the implemented Development Ticket Management Core: typed custom fields, exact-revision writes, relation rules, bulk operations, registry-backed query/sort/completion, fixtures, and cross-surface adoption of the shared ticket/project report.",
        "8. Harden the implemented Development Ticket Management Core: typed custom fields, exact-revision writes, relation rules, bulk operations, registry-backed query/sort/completion, fixtures, and the remaining Web/TUI/saved-view/remote/command-center adoption of the shared ticket/project report.",
        "priority ticket track",
    )

    text = replace_once(
        text,
        "it is directly inspectable through `python -m lifetxt.ticket_projects summary|board|attention`. Remaining work adds writes-that-move, integration of this shared report into the existing Project Hub and Portfolio commands and other public surfaces, privacy, and an explicit boundary between generic project issues and development tickets.",
        "it remains directly inspectable through `python -m lifetxt.ticket_projects summary|board|attention`; the same versioned object is now integrated into the main `ticket summary|board|attention` and `project tickets` commands, Project Hub, Portfolio, read-only MCP tools, and capability discovery, with configured project aliases normalized before aggregation. Remaining work adds writes-that-move, Web/TUI/saved-view/remote adoption, revision-aware delivery, privacy, and an explicit boundary between generic project issues and development tickets.",
        "project track summary",
    )
    text = replace_once(
        text,
        "- [ ] Expose the existing `project`/`portfolio` operations through TUI, Web, MCP, saved views, and remote read-only clients where capabilities permit, reusing `lifetxt/projects.py` and the implemented `lifetxt/ticket_projects.py` report contract rather than reimplementing either aggregation per surface. Thread the same reference time, stale window, terminal-status set, high-severity set, project scope, formulas, caveats, and dependency-unknown counts through every adapter; add capability and schema-version discovery before remote clients depend on the report.",
        "- [ ] Finish exposing the existing `project`/`portfolio` operations through TUI, Web, saved views, and remote read-only clients where capabilities permit. The main CLI, Project Hub, Portfolio, read-only MCP tools, project-alias normalization, shared reference/stale/terminal/severity settings, and capability discovery are implemented through `lifetxt/ticket_project_surfaces.py`; remaining adapters must consume the same complete `ticket-project-report-v1` object, preserve formulas/caveats/dependency-unknown counts, publish source revisions and privacy scope, and refuse unsupported schema versions instead of recalculating metrics locally.",
        "project surface bullet",
    )

    text = replace_once(
        text,
        "English/Japanese documentation exists in `docs/*/tickets.md` and `docs/*/ticket-projects.md`.",
        "English/Japanese documentation exists in `docs/*/tickets.md` and `docs/*/ticket-projects.md`. The cross-surface adapter in `lifetxt/ticket_project_surfaces.py` now resolves effective terminal statuses from the configured detailed-status map, resolves high severities and the stale window from ticketing report settings, canonicalizes configured project aliases without mutating authoritative items, registers `ticket summary|board|attention` and `project tickets`, embeds full reports in Project Hub and Portfolio, adds read-only `get_ticket_project_report`/`get_ticket_board`/`get_ticket_attention` MCP tools, and advertises the contract and effective settings through capabilities.",
        "ticket track summary",
    )
    text = replace_once(
        text,
        "- [ ] Integrate `ticket-project-report-v1` into the main `ticket` and `project` command trees, Project Hub, Portfolio, command center, health, workload, review, notification, TUI, Web, MCP, saved-view, and remote read-only surfaces. Reuse report objects and schema payloads directly instead of recalculating open/by-status, blocked, dependency-unknown, overdue, unassigned, high-severity, stale, estimate/elapsed, or count-progress values. Preserve the standalone `python -m lifetxt.ticket_projects` commands for diagnostics and backward-compatible scripting.",
        "- [ ] Finish integrating `ticket-project-report-v1` into command center, health, workload, review, notification, TUI, Web, saved-view, and remote read-only surfaces. The main `ticket`/`project` CLI trees, Project Hub, Portfolio, read-only MCP, capability discovery, and standalone diagnostic commands now return or embed the shared report. Every remaining adapter must reuse the complete schema payload rather than recalculating open/by-status, blocked, dependency-unknown, overdue, unassigned, high-severity, stale, estimate/elapsed, or count-progress values; add explicit schema-version refusal and revision/privacy metadata before caching or remote delivery.",
        "ticket surface bullet",
    )
    text = replace_once(
        text,
        "- [ ] Resolve default terminal statuses, status display order, priority order, and high-severity values from the effective versioned `ticketing` registry while retaining explicit library/CLI overrides and embedding the effective values in every report. Reject unknown or contradictory registry values with stable diagnostics instead of silently changing project counts.",
        "- [ ] Finish registry-driven report ordering and validation. Integrated surfaces now derive terminal statuses from effective `ticketing.statuses` life-status mappings, derive high severities and stale windows from `ticketing.report`/`ticketing`, retain explicit CLI/MCP/library overrides, and embed the effective values in every report and capability document. Next resolve status display order and priority order from the registry, publish their provenance, add stable diagnostics for unknown/duplicate/contradictory ordering entries, and preserve deterministic fallback ordering for older configurations.",
        "ticket configuration bullet",
    )
    text = replace_once(
        text,
        "- [ ] Publish `ticket-project-report-v1` through capability discovery, add cross-version schema compatibility fixtures, and extend the report with version/sprint attention only after authoritative `record:version` and `record:sprint` contracts exist. The schema itself, release-policy sample, generated bundle entry, and `format schemas` count/filename verification are implemented through `schema_extensions_v16`.",
        "- [ ] Add cross-version schema/capability compatibility fixtures and extend the report with version/sprint attention only after authoritative `record:version` and `record:sprint` contracts exist. Capability discovery now publishes the report schema, supported CLI/MCP operations, embedded surfaces, read-only property, dependency-scope rule, and effective terminal/severity/stale settings; the schema, release-policy sample, generated bundle entry, and `format schemas` verification remain implemented through `schema_extensions_v16`. Add older-client refusal/fallback tests before changing this contract.",
        "ticket capability bullet",
    )
    text = replace_once(
        text,
        "- [ ] Add local CLI fixtures and English/Japanese documentation for bug, feature, task, support, and security trackers; parent/subtask, duplicate, dependency, private/custom-field, cross-file, archive, and malformed-ticket cases; and migration from an existing Task or generic `record:issue` through an explicit diff/proposal.",
        "- [ ] Add local CLI fixtures and English/Japanese documentation for bug, feature, task, support, and security trackers; parent/subtask, duplicate, dependency, private/custom-field, cross-file, archive, and malformed-ticket cases; and migration from an existing Task or generic `record:issue` through an explicit diff/proposal. Main report-command, project-alias, Project Hub, Portfolio, MCP, and capability integration fixtures now exist; keep expanding corpus coverage rather than duplicating adapter-specific metric tests.",
        "ticket fixture bullet",
    )
    insertion = (
        "- [ ] Add source-manifest, exact input-revision, generated-at, privacy/redaction, and cache-validity metadata to `ticket-project-report-v1` or a versioned result envelope before Web, saved-view, remote, notification, or AI-context consumers persist reports. Define how partial/unreadable/private sources affect `dependency_unknown` reasons and project totals, ensure capability discovery declares the metadata version, and add stale-report rejection tests without exposing unrelated ticket bodies.\n"
    )
    anchor = "- [ ] Add a dependency-universe contract so a project-filtered report can evaluate permitted cross-project/cross-file dependencies without exposing unrelated ticket bodies. Preserve `dependency_unknown` when the referenced ticket is missing, unreadable, private, archived outside scope, or rejected by workspace resolution, and disclose the reason without guessing its state.\n"
    text = replace_once(text, anchor, anchor + insertion, "report metadata proposal")

    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
