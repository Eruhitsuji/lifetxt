from pathlib import Path


CAPABILITY_ID = "cap-personal-context-toolkit"
CAPABILITY_BLOCK = r'''

  - id: cap-personal-context-toolkit
    name: Deterministic Personal Context toolkit
    summary: >-
      Executable, provider-neutral Personal Context views and a proposal-first
      correction lifecycle built on the existing Personal AI Memory convention
      and Format 1.0 records. Provides bounded health, explanation, capsule,
      decision projections, and reviewable corrections without introducing a
      new record kind or first-class Query/Format vocabulary.
    status: active
    owner: Eruhitsuji
    source_requirements:
      - req-personal-context-health
      - req-personal-context-why
      - req-personal-memory-correction
      - req-personal-context-capsule
      - req-personal-decision-memory
      - req-personal-context-toolkit-integration
    implementation_locations:
      - lifetxt/personal_context.py
      - lifetxt/personal_context_cli.py
      - lifetxt/entrypoint.py
      - tests/test_personal_context.py
      - tests/test_personal_context_cli.py
      - tests/test_personal_context_correction.py
      - docs/en/personal-context-toolkit.md
      - docs/ja/personal-context-toolkit.md
    public_interfaces:
      - lifetxt context health
      - lifetxt context why <id>
      - lifetxt context capsule
      - lifetxt memory correct <id> TEXT
      - lifetxt decisions
    tests_or_evidence:
      - tests/test_personal_context.py
      - tests/test_personal_context_cli.py
      - tests/test_personal_context_correction.py
      - PR #553 CI
    related_issues:
      - https://github.com/Eruhitsuji/lifetxt/issues/500
      - https://github.com/Eruhitsuji/lifetxt/issues/503
      - https://github.com/Eruhitsuji/lifetxt/issues/547
      - https://github.com/Eruhitsuji/lifetxt/issues/548
      - https://github.com/Eruhitsuji/lifetxt/issues/549
      - https://github.com/Eruhitsuji/lifetxt/issues/550
      - https://github.com/Eruhitsuji/lifetxt/issues/551
      - https://github.com/Eruhitsuji/lifetxt/issues/552
    related_pull_requests:
      - https://github.com/Eruhitsuji/lifetxt/pull/553
    reuse_policy: prefer_reuse_or_extension_before_new_implementation
    notes: >-
      Reuses cap-personal-ai-memory-convention, cap-unified-inbox-proposals,
      cap-temporal-context, and the existing ID/link helpers. `corrects:` is a
      freeform detail convention scoped to this toolkit, not new Format or Query
      vocabulary. `memory correct` stages a replacement Note through Unified
      Inbox and never directly rewrites or deletes the authoritative old record.
    replacement:
      replaces: []
      replaced_by: null
      deprecation_issue: null
'''

TRACEABILITY_BLOCK = r'''

    - requirement_id: req-personal-context-health
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/547
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - tests/test_personal_context.py
        - tests/test_personal_context_cli.py
        - docs/en/personal-context-toolkit.md
        - docs/ja/personal-context-toolkit.md
      tests_or_evidence:
        - Context Health tests cover current, stale, superseded, missing-source, and broken-reference findings.
        - PR #553 CI.
      release_or_deployment: null
      status: implemented

    - requirement_id: req-personal-context-why
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/548
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - tests/test_personal_context.py
        - tests/test_personal_context_cli.py
      tests_or_evidence:
        - Context Why tests cover deterministic source, temporal, link, backlink, and correction evidence.
        - PR #553 CI.
      release_or_deployment: null
      status: implemented

    - requirement_id: req-personal-memory-correction
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/549
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - tests/test_personal_context_correction.py
        - docs/en/personal-context-toolkit.md
        - docs/ja/personal-context-toolkit.md
      tests_or_evidence:
        - Correction tests prove the replacement is staged through Unified Inbox and authoritative life.txt remains byte-unchanged before review acceptance.
        - Replacement Notes retain history through a freeform corrects relation instead of deleting the old record.
        - PR #553 CI.
      release_or_deployment: null
      status: implemented

    - requirement_id: req-personal-context-capsule
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/550
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - tests/test_personal_context.py
        - tests/test_personal_context_cli.py
      tests_or_evidence:
        - Capsule tests cover canonical deterministic SHA-256 revision, bounded output, and stale/superseded default exclusion.
        - PR #553 CI.
      release_or_deployment: null
      status: implemented

    - requirement_id: req-personal-decision-memory
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/551
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - tests/test_personal_context.py
        - tests/test_personal_context_cli.py
      tests_or_evidence:
        - Decision Memory reuses tag:decision and project metadata with project filtering applied before the requested limit.
        - Regression coverage locks the project-filter/limit ordering.
        - PR #553 CI.
      release_or_deployment: null
      status: implemented

    - requirement_id: req-personal-context-toolkit-integration
      capability_id: cap-personal-context-toolkit
      epic: https://github.com/Eruhitsuji/lifetxt/issues/500
      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/552
      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/553
      changed_files_or_scope:
        - lifetxt/personal_context.py
        - lifetxt/personal_context_cli.py
        - lifetxt/entrypoint.py
        - tests/test_personal_context.py
        - tests/test_personal_context_cli.py
        - tests/test_personal_context_correction.py
        - docs/en/personal-context-toolkit.md
        - docs/ja/personal-context-toolkit.md
        - .ai/project/CAPABILITIES.yml
        - .ai/project/TRACEABILITY.yml
      tests_or_evidence:
        - Focused Personal Context domain and CLI suites.
        - Repository traceability gate.
        - Final PR #553 CI.
      release_or_deployment: null
      status: implemented
'''


def main():
    capabilities_path = Path(".ai/project/CAPABILITIES.yml")
    traceability_path = Path(".ai/project/TRACEABILITY.yml")

    capabilities = capabilities_path.read_text(encoding="utf-8")
    if CAPABILITY_ID not in capabilities:
        if not capabilities.endswith("\n"):
            capabilities += "\n"
        capabilities += CAPABILITY_BLOCK.lstrip("\n")
        capabilities_path.write_text(capabilities, encoding="utf-8", newline="\n")

    traceability = traceability_path.read_text(encoding="utf-8")
    if "req-personal-context-toolkit-integration" not in traceability:
        marker = "\nrequired_chain:\n"
        if traceability.count(marker) != 1:
            raise SystemExit("expected exactly one required_chain marker")
        traceability = traceability.replace(
            marker,
            TRACEABILITY_BLOCK.rstrip("\n") + "\n\nrequired_chain:\n",
            1,
        )
        traceability_path.write_text(traceability, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
