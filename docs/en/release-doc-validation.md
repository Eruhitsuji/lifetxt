# Release Documentation Validation

The release documentation validator checks the bounded English document set
reviewed by #354. It validates internal file links and anchors, then runs only
the documented `python -m lifetxt <command> --help` examples. It never executes
arbitrary shell blocks, opens network connections, or uses provider credentials.

```console
python scripts/validate_release_docs.py --output docs/en/release-doc-validation.json
```

The JSON report names every checked document and records failures by document,
target, anchor, or command. Examples needing secrets or external services are
explicitly reported as not executed. The check is deterministic and suitable
for CI.
