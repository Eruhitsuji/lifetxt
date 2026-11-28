# Engineering References and Verification Records

[Documentation home](../README.md) · [English documentation](../en/readme.md) · [日本語ドキュメント](../ja/readme.md)

See the [contributor setup](../../readme.md#development-environment) for working
on lifetxt and the [CI responsibilities](../en/ci-responsibilities.md) for check
coverage. For the current user-facing behavior, use the
[format and behavior reference](../en/readme.md#format-and-behavior-reference).

Verification records describe the environments and versions they cover. Use the
[external verification guide](../en/external-environment-verification.md) to
check the status of a specific scenario or collect fresh evidence.

## Development and shared contracts

- [Branch readiness criteria](branch-readiness.md)
- [Public schema test contract](public-schema-contract.md)
- [Core import boundary](../design/core-import-boundary.md)
- [Static typing boundary](../en/static-typing-boundary.md)
- [lifetxt-mini CI](../en/lifetxt-mini-ci.md)
- [Historical regression test policy](../testing-regressions.md)

## Format and machine-readable interfaces

- [Format 1.0 compatibility matrix](../en/format-compatibility-matrix.md)
- [Format migration boundary](../en/format-migration.md)
- [Backup format](../en/backup-format-v1.md)
- [Compressed archive format](../en/format-lifetxtz-v1.md)
- [SQLite interchange format](../en/format-sqlite-interchange-v1.md)
- [Machine-readable contract matrix](../en/stable-contract-matrix.md)
- [Diagnostic matrix](../en/stable-diagnostics-matrix.md)
- [Current VM contract and history](../design/counter-machine.md)

## Quality gates and verification evidence

- [Release documentation validation](../en/release-doc-validation.md)
- [Documentation validation report (JSON)](../en/release-doc-validation.json)
- [Release documentation parity audit](../en/release-doc-parity-audit.md)
- [CI coverage baseline](../en/ci-coverage-baseline.md)
- [Storage performance baseline](../en/core-performance-baseline.md)
- [Storage benchmark data (JSON)](../en/core-performance-baseline.json)
- [Dependency security audit](../en/dependency-security-audit.md)
- [Dependency evidence (JSON)](../en/dependency-audit.json)
- [Release security review](../en/release-security-review.md)
- [Ruff rule audit](../en/ruff-rule-audit.md)
- [Ruff rule audit data (JSON)](../en/ruff-rule-audit.json)
- [Stable release artifact verification](../en/stable-release-artifact-verification.md)
- [Web and MCP schema validation](../en/stable-web-mcp-schema-validation.md)
- [MCP read smoke evidence](../en/stable-mcp-read-artifact-smoke.md)
- [Remote read smoke evidence](../en/stable-remote-read-smoke.md)
- [Web revision observe mode (#288)](../en/stable-verification-288-web-revision-observe.md)
- [Web client revision preconditions (#289)](../en/stable-verification-289-web-client-revisions.md)
- [Zero-legacy-write observation window (#290)](../en/stable-verification-290-zero-legacy-window.md)
- [Required-revision cutover gate (#291)](../en/stable-verification-291-required-revision-cutover.md)
- [Web revision lifecycle (#292)](../en/stable-verification-292-revision-lifecycle.md)
- [Attachment partial-send recovery (#297)](../en/stable-verification-297-attachment-restart.md)
- [Attachment crash and replay recovery (#298)](../en/stable-verification-298-attachment-replay.md)
- [Attachment authorization and bounds (#299)](../en/stable-verification-299-attachment-bounds.md)
- [Filesystem recovery support matrix (#304)](../en/stable-verification-304-filesystem-support.md)
- [Windows terminal verification (#312)](../en/stable-verification-312-windows-terminals.md)

## Architecture reviews, proposals and historical records

- [Module structure investigation](../design/module-structure.md)
- [Pre-VM counter-machine design snapshot](../design/archive/counter-machine-pre-vm.md)
- [Format 1.0 finalization review](../en/format-1.0-finalization-review.md)
- [lifetxt-mini phase 0 contract and spike](../en/lifetxt-mini-phase-0.md)
- [Native semantic as-of investigation](../en/native-semantic-as-of-investigation.md)
- [CLI decomposition plan](../en/cli-decomposition-plan.md)
- [CUI test decomposition audit](../en/cui-test-decomposition-audit.md)
- [MCP decomposition audit](../en/mcp-decomposition-audit.md)
- [Oversized-file decomposition audit](../en/oversized-file-decomposition-audit.md)
- [Oversized-file responsibility report](../en/oversized-file-report.md)
- [Oversized-file report data (JSON)](../en/oversized-file-report.json)
- [Server-update decomposition audit](../en/server-update-decomposition-audit.md)
- [Server-update review extraction](../en/server-update-review-extraction.md)
- [Archive/config test extraction](../en/test-archive-config-extraction.md)
- [Test-suite decomposition audit](../en/test-suite-decomposition-audit.md)
- [TUI decomposition audit](../en/tui-decomposition-audit.md)
- [Web asset resource migration](../en/web-asset-resource-migration.md)
- [Web/MCP service boundary audit](../en/web-mcp-service-boundary-audit.md)
- [Web route decomposition audit](../en/web-route-decomposition-audit.md)
- [Mutation testing pilot](../mutation-testing-pilot.md)
- [Roadmap archive and retained scope](../roadmap/README.md)
