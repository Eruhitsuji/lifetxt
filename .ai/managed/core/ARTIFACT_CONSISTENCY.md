# Artifact Consistency Standard

Purpose, requirements, specifications, design, tasks, implementation, tests,
operations documents, and release contents must converge before merge or
release.

## Consistency Viewpoints

Use these minimum viewpoints for every cross-artifact check:

- Completeness: required information exists and no required feature, test, or
  evidence is missing.
- Correctness: artifacts describe behavior that is true, feasible, and aligned
  with the implementation.
- Coherence: artifacts do not contradict each other, duplicate capabilities, or
  imply incompatible scopes.

## Gates

| Gate | When | Required Check |
| --- | --- | --- |
| Clarification Gate | before requirements are accepted | problem, owner, users, scope, and unknowns are clear enough |
| Requirements Checklist Gate | before task decomposition | requirements, acceptance criteria, constraints, and verification are explicit |
| Cross-Artifact Analysis Gate | before implementation or major review | purpose, requirements, design, task, tests, and operations impact agree |
| Implementation Convergence Gate | before merge | code, tests, docs, traceability, review ledger, and release notes are aligned |

## Change Package

Use a change package for medium or higher assurance work, cross-module changes,
public interface changes, operations changes, or any change where artifacts may
drift.

```text
.ai/project/changes/<change-id>/
+-- change.yml
+-- requirements.yml
+-- design.md
+-- traceability.yml
+-- decisions.md
+-- verification.yml
```

The package separates the current living specification from proposed change
diffs.

## Change Kinds

Every affected requirement, capability, interface, test, operation, or release
note is marked as one of:

- ADDED
- MODIFIED
- REMOVED

## Completion Flow

1. Create or update the change package while the issue is active.
2. Keep traceability from requirement to capability, task, PR, test/evidence,
   and release.
3. Run cross-artifact analysis before review.
4. After merge, update living specifications under `.ai/project/**` or project
   documentation.
5. Move the change package to an archive location or close it with a completed
   status.

Do not leave merged behavior only in a temporary change package.
