# Change Packages

Use this directory for non-trivial changes, High or Regulated assurance work,
public API changes, data changes, migrations, operations changes, or any change
where requirements, design, tasks, tests, and release evidence may drift.

Create one directory per change:

```text
.ai/project/changes/<change-id>/
+-- change.yml
+-- requirements.yml
+-- design.md
+-- traceability.yml
+-- decisions.md
+-- verification.yml
```

After the change is merged, update the living project specification and close or
archive the change package. Do not leave merged behavior only in this temporary
package.
