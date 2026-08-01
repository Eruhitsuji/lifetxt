# Specification Lifecycle Standard

This standard applies the common AI-driven development rules across the whole
product and software lifecycle. The lifecycle can be lightweight, but every
phase must have an owner, gate, evidence, and next-phase condition.

## Lifecycle Phases

| Phase | Input | Output | Owner | Executable Roles | Required Review | Required Verification | Gate | Evidence | Next Condition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Discovery | idea, problem, incident, request | problem statement, initial issue | Product Owner | Planner, Researcher, Orchestrator | problem framing review | feasibility or evidence check | Clarification Gate | notes, references, decision | purpose and owner are clear |
| Product Requirements | discovery output | user needs, scope, out of scope | Product Owner | Requirements Owner, Planner | requirements review | acceptance criteria check | Requirements Checklist Gate | feature spec or issue | requirements are testable |
| System / Software Requirements | product requirements | system constraints, interfaces, data rules | Requirements Owner | Architect, Contract Owner | requirements and contract review | cross-artifact check | Requirements Checklist Gate | requirements.yml, API notes | downstream contracts are clear |
| Architecture and Design | requirements and constraints | architecture, design, ADRs, contracts | Architect | Architect, Security Reviewer, Performance Reviewer | design review | risk and compatibility check | Cross-Artifact Analysis Gate | design.md, ADRs | design is reviewable |
| Task Decomposition | approved requirements/design | epics, tasks, dependencies, scopes | Task Decomposer | Orchestrator, Integrator | decomposition review | complexity and scope check | task readiness gate | task contracts | tasks are XS/S or justified M |
| Implementation | Ready task | code, docs, tests | Implementer | Implementer, Tester | implementation review | unit/static/targeted checks | implementation gate | commits, test results | acceptance criteria addressed |
| Developer Verification | implementation | local evidence | Implementer | Implementer, Tester | self-review | required project commands | verification gate | command output | no false pass claims |
| Independent Review | PR and evidence | review result | Reviewer | Reviewer, Security Reviewer, Performance Reviewer | independent review | evidence review | review gate | review ledger | blocking findings resolved |
| Integration Verification | reviewed PR | merge-ready result | Integrator | Integrator, Integration Reviewer | integration review | CI, contract, migration checks | integration gate | CI, conflict notes | merge authority can decide |
| Release Approval | integrated changes | release decision | Release Authority | Release Authority, Auditor | release review | release checklist | release gate | release notes, migration notes | release approved |
| Deployment | approved release | deployed change | Operations Owner | Integrator, Operations Owner | deployment review when needed | smoke, rollback readiness | deployment gate | deploy record | system is observable |
| Operations and Monitoring | deployed system | telemetry and operational status | Operations Owner | Operations Owner, Tester | operations review | monitoring and alert checks | operations gate | dashboards, alerts, runbooks | operations are stable |
| Incident and Maintenance | alert, bug, vulnerability, user report | incident or maintenance issue | Incident Commander | Operations Owner, Security Reviewer, Implementer | incident review | reproduction, mitigation, regression check | incident gate | timeline, fix, evidence | issue is mitigated or resolved |
| Evaluation and Improvement | completed work, incidents, metrics | improvement issue or standard change | Accountable Owner | Auditor, Reviewer, Orchestrator | retrospective review | standard evaluation | improvement gate | lessons, eval result | follow-up is tracked |
| Deprecation | product or technical deprecation decision | deprecation plan | Product Owner | Architect, Operations Owner | compatibility and operations review | usage and migration checks | deprecation gate | impact analysis | retirement is approved or deferred |
| Retirement | approved deprecation | removed capability or retired system | Release Authority | Operations Owner, Integrator | retirement review | backup, data retention, rollback/recovery check | retirement gate | removal record | users and operations are safe |

## Change Package Link

For non-trivial changes, create a change package under
`.ai/project/changes/<change-id>/`. The package carries requirements, design,
traceability, decisions, and verification until the change is merged and
reflected into the living specification.

See `ARTIFACT_CONSISTENCY.md` and `TRACEABILITY.md`.

## Phase Escalation

Escalate assurance level when a change has security, data, operations,
compatibility, release, or compliance impact. See `ASSURANCE_LEVELS.md`.
