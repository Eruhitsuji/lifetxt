# Roles and Responsibilities Standard

Humans and AI tools can both be assigned roles, but accountability and final
risk acceptance remain human responsibilities.

## Standard Roles

| Role | Responsibility |
| --- | --- |
| Accountable Owner | owns final outcome, priority, and risk acceptance |
| Product Owner | owns product value, users, scope, and release intent |
| Requirements Owner | owns requirements clarity and acceptance criteria |
| Orchestrator | coordinates task flow, dependencies, and status |
| Task Decomposer | splits work into safe tasks with scopes and dependencies |
| Architect | owns architecture, interfaces, and design tradeoffs |
| Contract Owner | owns API, schema, event, and integration contracts |
| Implementer | changes code/docs within approved scope |
| Tester | creates and runs verification, test plans, and evidence |
| Reviewer | reviews requirements, design, code, tests, and risks |
| Security Reviewer | reviews security-sensitive behavior and exceptions |
| Performance Reviewer | reviews performance-sensitive behavior and measurements |
| Integration Reviewer | reviews shared files, merge order, and integration safety |
| Integrator | resolves approved integration work and shared-file coordination |
| Merge Authority | approves merge readiness for protected branches |
| Release Authority | approves release, deployment, rollback, and retirement |
| Operations Owner | owns monitoring, runbooks, operational readiness, and incidents |
| Incident Commander | owns active incident coordination and final incident decisions |
| Auditor | checks evidence, traceability, approvals, and standard compliance |

## Human-Only Responsibilities

The following responsibilities are limited to a human or approved human team:

- final requirements judgment
- Accountable Owner
- Merge Authority
- Release Authority
- approval of security exceptions
- acceptance of major risk
- Incident Commander
- final decision for data deletion, deprecation, shutdown, rollback, retirement

AI tools may recommend actions, draft artifacts, implement scoped changes, and
perform first-pass review, but they must not claim final authority for these
responsibilities.
