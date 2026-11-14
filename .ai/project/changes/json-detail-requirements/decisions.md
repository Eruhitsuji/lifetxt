# Decisions

The maintainer approved one array rule for all keys. A top-level JSON array contributes the value list, and one additional nesting level preserves an array as one value. The whitespace-delimited block supports line breaks and ordinary JSON escaping.

Repeated start conditions are ANDed. Structured conditions can use all and any groups. Unresolved references are represented separately from conditions that evaluate false.
