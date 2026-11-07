# JavaScript checker site candidate

Parent #1358 and implementation #1536. The explicit builder calls the existing
static intro builder, adding home links and two checker pages. It copies the
same parser as the Node CLI and includes only the UI, parser, CSS and license
as checker assets. The published build continues to use the default builder.

The UI checks text only after a button action, uses textContent for diagnostics,
clears stale results on edits, and clears the field when the page is left.
The checker-only CSP blocks connections, workers, form submission and inline
scripts. No persistence or data transmission APIs are used.

Review the bilingual result states, project-prefix paths, CSP and output
allowlist. Chromium smoke covers both languages, storage/network observation,
boundaries and no-JS fallback. A normal revert removes the candidate and smoke
integration. Live delivery and deployment approval are separate.
