# Runtime Evidence Standard

Runtime evidence is local execution history that shows how humans and AI tools
actually performed development work. It complements static validation and
scenario evaluation by showing whether downstream projects followed the
standard in practice and whether the standard itself caused ambiguity or
operational friction.

## Scope

Runtime evidence may include AI session metadata, tool calls, command results,
file operations, Git operations, approval requests, review evidence, and
verification outcomes.

Runtime evidence must not replace GitHub Issues as the source of truth for
actionable work. It is supporting evidence for project improvement and upstream
standard improvement.

## Local-First Requirement

Collection and analysis are local-first by default.

- Do not upload raw AI transcripts, shell output, source snippets, environment
  values, local paths, or private URLs to GitHub Issues by default.
- Do not enable automatic upstream reporting until a human approves the
  reporting policy for the project.
- Use sanitized findings for sharing outside the local environment.
- Preserve enough source references for human review without exposing private
  history unnecessarily.

## Evidence Pipeline

The standard runtime evidence flow is:

```text
AI tool session history
        |
        v
local archive records
        |
        v
provider-neutral normalized events
        |
        v
deterministic and semantic checks
        |
        v
sanitized findings
        |
        v
downstream project issue or upstream standard issue
```

## Archive Contract

An archive records:

- archive metadata
- selected provider and project association settings
- provider source indexes
- optional embedded raw source records
- normalized events when available

Archives must record the schema version, provider, source identifier, project
directory, matching mode, collection time, and whether raw content is embedded.

Raw preservation is supported for local analysis, but it must be explicit. A
metadata-only archive is safer for routine review and public collaboration.

## Project Association

Associate sessions with a target project using provider-owned metadata such as:

- `cwd`
- `project_path`
- `projectPath`
- `workspace`
- `workspaceFolders`
- `rootPath`
- `repositoryPath`
- `workingDirectory`

Exact project-root matching may be used for strict audits. Child-directory
matching may be used when sessions are started inside a project subdirectory.

Arbitrary full-text matching is a fallback only. When used, the finding report
must mark project association as weak.

## Normalized Events

Analyzers should consume provider-neutral events instead of requiring every
check to understand every provider-specific format.

Event kinds include:

- `session_start`
- `session_end`
- `user_message`
- `assistant_message`
- `tool_call`
- `tool_result`
- `command_start`
- `command_result`
- `file_read`
- `file_create`
- `file_edit`
- `file_delete`
- `patch`
- `git_command`
- `github_operation`
- `test_start`
- `test_result`
- `error`
- `warning`
- `approval_request`
- `approval_result`
- `agent_spawn`
- `agent_result`

Each normalized event must retain a source reference back to the archive record
that produced it.

## Finding Classes

Classify findings before reporting.

### Project or Execution Finding

Use this class when the standard is clear but downstream execution did not
follow it.

Examples:

- work started before the task was Ready
- required human approval was absent
- files were edited outside declared write scope
- repeated command failures were not addressed
- merge, release, deployment, or rollback gates were skipped

These findings normally belong in the downstream project.

### Standard or Upstream Finding

Use this class when evidence suggests the common standard should change.

Examples:

- two standard documents lead to conflicting interpretations
- supported AI tools interpret the same rule differently
- a required workflow has no applicable rule
- context loading is excessive
- a rule is repeatedly misunderstood
- following the standard creates unnecessary repeated work

These findings may become upstream issues in this repository.

## Deterministic and Semantic Checks

Do not make every finding depend on an AI judgment.

Deterministic checks should cover high-confidence conditions such as:

- edit outside declared write scope
- repeated command failure
- protected operation before approval
- absent verification result after a claimed check
- weak project association
- raw evidence exported with unsafe reporting settings
- a configured provider has no matching source files (coverage gap)

### Checks by Collection Mode

Metadata-only archives (`AI_HISTORY.yml`'s `default_mode: metadata_only`, the
recommended default for routine and public collection) contain only archive
metadata and source-file records — no message or tool-call content. Only checks
that read those two record types can run in this mode:

- weak project association
- provider coverage gap

Write-scope violation, repeated command failure, and protected-operation
checks all depend on normalized events, which require raw content
(`--include-raw` when exporting). Treat `metadata_only` collection as an
inventory and association-quality signal, not as a source of behavioral
findings; enable `--include-raw` (with its stricter privacy handling) when
behavioral findings are needed.

Semantic checks may cover lower-confidence conditions such as:

- ambiguous standard wording
- conflicting guidance across documents
- repeated user confusion
- unnecessary context loading
- disproportionate process overhead

Semantic findings must include confidence, evidence references, and human
review status.

## Finding Schema

Findings must include:

- stable finding ID or fingerprint
- category and subtype
- severity
- confidence
- affected standard version and commit when known
- rule IDs or applicable standard documents
- session and evidence references
- expected behavior
- observed behavior
- impact
- suggested action
- human review status

Use `schemas/ai-finding.schema.yml` and `templates/ai-finding-report.md`.

## Deduplication

Automated reporting must deduplicate findings before opening issues.

Generate a stable fingerprint from the finding class, subtype, applicable rule
IDs, root-cause pattern, and relevant standard version compatibility.

Generated issue bodies must include:

```text
ADS-FINDING: <fingerprint>
```

Before creating a new issue, search for an existing open issue with the same
marker. If one exists, append sanitized occurrence information instead of
creating another issue.

## Privacy and Redaction Defaults

Default reporting must:

- exclude raw transcripts
- exclude source code snippets unless explicitly approved
- redact likely secrets, tokens, local home paths, and private URLs
- use stable anonymous session IDs when concrete IDs are unnecessary
- minimize evidence to the smallest context needed for review

Public upstream issues require human approval before any project-identifying or
source-identifying evidence is included.

## Rule ID Strategy

Runtime findings should reference stable rule IDs where they exist and
applicable standard documents where IDs do not yet exist.

Do not assign arbitrary global rule IDs only to satisfy a finding. Add or
change stable rule IDs through a separate standard change after the normative
rule inventory is understood.

Runtime pipeline controls may use local check IDs such as:

- `RUNTIME-COLLECT-001`: collection is local-first
- `RUNTIME-RAW-001`: raw evidence is explicit and protected
- `RUNTIME-NORM-001`: analyzers consume normalized events
- `RUNTIME-FIND-001`: findings separate execution failures from standard gaps
- `RUNTIME-REPORT-001`: upstream reporting is sanitized and deduplicated

## Retention

Projects must define retention expectations before routine collection.

Minimum decisions:

- where local archives are stored
- who may access archives
- how long raw archives are retained
- whether metadata-only archives are retained longer
- how archives are deleted
- whether CI is allowed to collect evidence

Use `.ai/project/AI_HISTORY.yml` for downstream configuration.

## Initial Tooling

The preview tooling is intentionally conservative:

- `scripts/export-ai-history.py` collects local provider evidence.
- `scripts/analyze-ai-history.py` normalizes supported evidence and emits
  deterministic findings.
- `scripts/report-ai-findings.py` renders sanitized finding reports.

The scripts must not create or update GitHub Issues automatically by default.
Issue creation requires a reviewed wrapper or a human-approved workflow.
