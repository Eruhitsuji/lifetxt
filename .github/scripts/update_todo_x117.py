from pathlib import Path


path = Path("todo.md")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "Last updated: 2026-07-25 (updated x116)",
        "Last updated: 2026-07-25 (updated x117)",
    ),
    (
        "publish the operations and effective settings through capability discovery; and keep the generated Draft 2020-12 schema bundle at 56 documents.",
        "publish the operations and effective settings through capability discovery; add exact source-file SHA-256 discovery and optional/required optimistic-concurrency checks for `ticket edit|assign|close|reopen|link|unlink`, with shared sidecar locking, in-lock ticket/relation transforms, stale-write refusal, CAS-aware dry runs, per-command and configuration enforcement, and capability discovery while keeping remote ticket writes disabled; and keep the generated Draft 2020-12 schema bundle at 56 documents.",
    ),
    (
        "Remaining ticket work focuses on workflow/history, exact-revision writes, richer planning records, configuration-backed custom fields, report revision/privacy metadata, registry-backed display ordering and diagnostics, and the still-unimplemented Web/TUI/saved-view/remote/command-center adoption rather than rebuilding ticket aggregation.",
        "Remaining ticket work focuses on workflow/history, richer planning records, configuration-backed custom fields, multi-target ticket/event/time-entry revision and recovery contracts, report revision/privacy metadata, registry-backed display ordering and diagnostics, and the still-unimplemented Web/TUI/saved-view/remote/command-center adoption rather than rebuilding ticket aggregation.",
    ),
    (
        "8. Harden the implemented Development Ticket Management Core: typed custom fields, exact-revision writes, relation rules, bulk operations, registry-backed query/sort/completion, fixtures, and the remaining Web/TUI/saved-view/remote/command-center adoption of the shared ticket/project report.",
        "8. Harden the implemented Development Ticket Management Core: typed custom fields, relation rules, all-or-none bulk operations, multi-target revision/recovery contracts, registry-backed query/sort/completion, fixtures, and the remaining Web/TUI/saved-view/remote/command-center adoption of the shared ticket/project report.",
    ),
    (
        "The cross-surface adapter in `lifetxt/ticket_project_surfaces.py` now resolves effective terminal statuses from the configured detailed-status map, resolves high severities and the stale window from ticketing report settings, canonicalizes configured project aliases without mutating authoritative items, registers `ticket summary|board|attention` and `project tickets`, embeds full reports in Project Hub and Portfolio, adds read-only `get_ticket_project_report`/`get_ticket_board`/`get_ticket_attention` MCP tools, and advertises the contract and effective settings through capabilities.",
        "The cross-surface adapter in `lifetxt/ticket_project_surfaces.py` now resolves effective terminal statuses from the configured detailed-status map, resolves high severities and the stale window from ticketing report settings, canonicalizes configured project aliases without mutating authoritative items, registers `ticket summary|board|attention` and `project tickets`, embeds full reports in Project Hub and Portfolio, adds read-only `get_ticket_project_report`/`get_ticket_board`/`get_ticket_attention` MCP tools, and advertises the contract and effective settings through capabilities. The exact-revision adapter in `lifetxt/ticket_revision_writes.py` now publishes `ticket revision`, accepts normalized `--revision`/`--expected-revision` tokens, optionally requires them per command or through `ticketing.write.require_revision`, applies edit/assign/close/reopen and relation transforms under the shared sidecar lock, rejects stale source-file hashes without replacement, returns before/after revisions, validates dry runs without writing, and advertises the local contract while explicitly keeping remote ticket writes disabled.",
    ),
    (
        "- [ ] Add exact-revision checks to ticket writes (`edit/assign/close/reopen/link`). They currently use the atomic in-file updater but not caller-supplied expected revisions; add optimistic-concurrency tokens before remote enablement. `--dry-run` and workspace-aware targets already exist.",
        "- [ ] Extend the implemented exact-revision contract beyond single-source current-ticket writes. `ticket revision` plus `--revision`/`--expected-revision`, `--require-revision`, `ticketing.write.require_revision`, stale-conflict refusal, shared lock/CAS replacement, relation re-read inside the lock, before/after revision reporting, capability discovery, and CAS-aware dry runs now cover `edit/assign/close/reopen/link/unlink`. Next define revision sets and transaction IDs for `ticket new`, all-or-none bulk changes, ticket-plus-event/comment transitions, watcher notifications, time entries, version/sprint membership, attachment references, and project archive; require every touched source/event/store revision; publish inspect/resume/compensate evidence; and keep Web/MCP ticket writes disabled until workflow, permission, clock, history, privacy, and recovery contracts are complete.",
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit("required roadmap text not found: %s" % old[:120])
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
