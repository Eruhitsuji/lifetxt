# Decisions

## D1: Extend temporal-thread-v1 additively

Historical provenance is an optional input/evidence description around the
same lifecycle read model, so it does not justify a second graph engine or a
breaking thread schema version.

## D2: Treat the public contract as High assurance

The feature is read-only but changes CLI and published JSON Schema contracts.
It therefore receives High-assurance verification and review evidence.

## D3: Preserve missing paths as limitations

The current workspace resolver defines the requested path manifest. Paths not
present in the selected tree are listed as missing and never loaded from the
working tree.
