# MCP semantic as-of

The read-only `get_semantic_as_of` MCP tool exposes the existing
`semantic-as-of-v1` projection for one item and an explicit offset-aware
timestamp. It preserves known, partial, and unavailable field states,
limitations, and provenance. It never substitutes the current item when
historical evidence is unavailable and does not compose Git history.
