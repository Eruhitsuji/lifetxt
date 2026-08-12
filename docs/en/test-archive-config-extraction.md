# Archive/Config Test Extraction Preparation

Issue: #388

The first move from `tests/test_lifetxt.py` is bounded to archive and config
CLI tests. Before moving, record the discovery count for the source module and
the destination module, keep common temporary-path helpers in one owner, and
run both modules independently. This preparation explicitly excludes deleting
duplicates or changing production code; those require separate evidence.
