# Automation and Hooks Standard

Automation should enforce what can be checked mechanically and leave judgment
to named human authorities.

## Required Validation Areas

Projects should add checks for:

- required files
- YAML syntax and schema-like required keys
- task contract fields
- traceability links
- duplicate capability IDs
- scope overlap
- managed snapshot integrity
- adapter consistency
- assurance level rules
- review freshness
- standard evaluation scenarios
- context index metadata
- standard lock version and commit SHA
- change package structure

## GitHub Actions

The common standard repository must run:

- `python scripts/validate-standard.py`
- `python scripts/run-standard-evals.py`

Downstream projects should run their project-specific commands from
`.ai/project/COMMANDS.yml` in addition to standard validation.

## Automation Limits

Automation must not silently rewrite requirements, merge PRs, accept risks, or
approve security exceptions. When automation detects ambiguity, it should report
a blocker or create a follow-up issue.
