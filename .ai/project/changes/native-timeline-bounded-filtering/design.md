# Design

The shared reader normalizes offset-aware bounds to UTC, validates a closed
event vocabulary, filters the already sorted valid stream with AND semantics,
then applies the existing limit. Invalid evidence and completeness are computed
from the full input so filters cannot hide integrity limitations.
