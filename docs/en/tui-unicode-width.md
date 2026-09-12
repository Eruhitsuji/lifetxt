# TUI Unicode width policy

The curses TUI uses one shared cell-width and clipping policy for headers,
rows, panels, prompts, styled spans, and cursor placement. Combining marks,
variation selectors, ZWJ sequences, and flags are kept together when clipping.
Fullwidth, wide, emoji, and non-frame ambiguous symbols use conservative
widths; frame box-drawing characters remain one cell by contract. The active
header marker is ASCII so it remains stable on terminals with different
ambiguous-width settings.

`--glyphs ascii` remains a deterministic fallback for terminal-specific
rendering problems.
