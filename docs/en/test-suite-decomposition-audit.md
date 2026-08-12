# Test Suite Decomposition Audit

Issue: #372  
Implementation follow-up: #388

## Inventory

`tests/test_lifetxt.py` contains parser/serialization, Markdown, CLI command
families, Web behavior, archive/mutation, configuration, and source metadata
tests. Existing focused modules already cover several domains, including
round-trip, completion, archive plans, configuration validation, and Web
contracts. The large file should therefore be split by responsibility rather
than mechanically by line count.

## First Cluster

The first XS/S move is the archive/config command cluster, tracked by #388.
It has clear existing ownership targets and can minimize production-code
changes. The implementation must preserve unittest discovery and test method
names where practical, keep shared temporary-workspace helpers centralized, and
record before/after counts. Redundant tests require a separate evidence-backed
decision and are not deleted during the move.
